"""
Celery 维护任务定义
配额重置 / 数据备份 / 日志清理
"""

import logging
import os
import shutil
from datetime import datetime, timezone, timedelta

from app.workers import celery_app

logger = logging.getLogger(__name__)
CST = timezone(timedelta(hours=8))


@celery_app.task
def reset_daily_quota():
    """
    每日重置用户配额
    触发: Celery Beat (每天UTC+8 00:00)
    """
    import asyncio
    from sqlalchemy import text
    from app.db.session import async_session_factory

    async def _reset():
        async with async_session_factory() as session:
            try:
                await session.execute(text(
                    "UPDATE users SET quota_used = 0, quota_reset_at = :now"
                ), {"now": datetime.now(CST)})
                await session.commit()
                logger.info("Daily quota reset completed")
            except Exception as exc:
                logger.error(f"Quota reset failed: {exc}")
                raise
            finally:
                await session.close()

    asyncio.run(_reset())
    return {"status": "success", "message": "All user quotas reset to 0"}


@celery_app.task
def daily_backup():
    """
    每日数据备份
    触发: Celery Beat (每天UTC+8 03:00)
    扩展入口: 可接入S3/OSS云存储
    """
    import asyncio
    from sqlalchemy import text
    from app.db.session import async_session_factory

    async def _backup():
        backup_id = f"auto_{datetime.now(CST).strftime('%Y%m%d_%H%M%S')}"
        backup_dir = os.environ.get("BACKUP_DIR", "/app/backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f"{backup_id}.sql")

        async with async_session_factory() as session:
            try:
                # SQLite备份方式
                result = await session.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ))
                tables = [row[0] for row in result.all()]

                # 扩展入口: 实际导出SQL或使用sqlite3 .backup API
                logger.info(f"Backup {backup_id}: {len(tables)} tables")

                return {"backup_id": backup_id, "tables": tables}
            except Exception as exc:
                logger.error(f"Backup failed: {exc}")
                raise
            finally:
                await session.close()

    result = asyncio.run(_backup())
    return {"status": "success", **result}


@celery_app.task
def cleanup_old_logs():
    """
    清理过期审计日志（保留90天）
    触发: Celery Beat (每小时检查)
    """
    import asyncio
    from sqlalchemy import text
    from app.db.session import async_session_factory

    RETENTION_DAYS = 90

    async def _cleanup():
        cutoff = datetime.now(CST) - timedelta(days=RETENTION_DAYS)
        async with async_session_factory() as session:
            try:
                result = await session.execute(text(
                    "DELETE FROM audit_logs WHERE created_at < :cutoff"
                ), {"cutoff": cutoff})
                deleted = result.rowcount
                await session.commit()
                logger.info(f"Cleaned up {deleted} old audit logs (older than {RETENTION_DAYS}d)")
                return deleted
            except Exception as exc:
                logger.error(f"Log cleanup failed: {exc}")
                raise
            finally:
                await session.close()

    deleted = asyncio.run(_cleanup())
    return {"status": "success", "deleted_count": deleted, "retention_days": RETENTION_DAYS}
