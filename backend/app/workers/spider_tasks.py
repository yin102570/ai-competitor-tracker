"""
Celery 爬虫任务定义
三引擎调度: Playwright(JS动态) / Scrapy(大规模HTTP) / httpx(API对接)
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta

from app.workers import celery_app
from app.db.session import async_session_factory

logger = logging.getLogger(__name__)
CST = timezone(timedelta(hours=8))


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def run_spider_job(
    self,
    competitor_slug: str,
    task_type: str,
    spider_engine: str = "httpx",
):
    """
    执行爬虫任务（Celery异步包装）

    参数:
        competitor_slug: 竞品标识
        task_type: 任务类型 (web/app/sentiment/pricing/model_rank)
        spider_engine: 爬虫引擎 (playwright/scrapy/httpx)
    """
    try:
        result = asyncio.run(_execute_spider(
            task_id=self.request.id if hasattr(self, 'request') else f"manual_{datetime.now(CST).strftime('%Y%m%d%H%M%S')}",
            competitor_slug=competitor_slug,
            task_type=task_type,
            spider_engine=spider_engine,
        ))
        return {"status": "success", "data": result}
    except Exception as exc:
        logger.error(f"Spider task failed: {competitor_slug}/{task_type}: {exc}")
        raise self.retry(exc=exc)


async def _execute_spider(
    task_id: str,
    competitor_slug: str,
    task_type: str,
    spider_engine: str,
) -> dict:
    """实际爬虫执行逻辑（异步）"""
    from sqlalchemy import select, text
    from app.models.spider import SpiderTask, TaskStatus
    from app.services.spider_service import SpiderService

    async with async_session_factory() as session:
        try:
            # 创建任务记录
            db_task_id = f"task_{uuid.uuid4().hex[:16]}"
            task = SpiderTask(
                id=db_task_id,
                competitor_slug=competitor_slug,
                task_type=task_type,
                status=TaskStatus.RUNNING.value,
                started_at=datetime.now(CST),
            )
            session.add(task)
            await session.flush()

            # 调用 SpiderService 的真实采集逻辑
            service = SpiderService(session)
            result_data: dict = {
                "engine": spider_engine,
                "task_id": task_id,
                "timestamp": datetime.now(CST).isoformat(),
            }

            if task_type == "web":
                crawl_result = await service._crawl_competitor_web(competitor_slug)
                result_data.update(crawl_result)
            elif task_type == "app":
                crawl_result = await service._crawl_app_data(competitor_slug)
                result_data.update(crawl_result)
            elif task_type == "sentiment":
                crawl_result = await service._crawl_sentiment(competitor_slug)
                result_data.update(crawl_result)
            elif task_type == "pricing":
                crawl_result = await service._crawl_pricing(competitor_slug)
                result_data.update(crawl_result)
            elif task_type == "model_rank":
                crawl_result = await service._crawl_model_rank(competitor_slug)
                result_data.update(crawl_result)

            # 更新任务状态为成功
            import json
            task.status = TaskStatus.SUCCESS.value
            task.result = json.dumps(result_data, ensure_ascii=False)
            task.completed_at = datetime.now(CST)
            await session.flush()

            return result_data

        except Exception as exc:
            # 更新任务状态为失败
            try:
                task.status = TaskStatus.FAILED.value
                task.error_msg = str(exc)[:500]
                task.completed_at = datetime.now(CST)
                await session.flush()
            except Exception:
                pass
            raise
        finally:
            await session.close()


# ============================================================
# 定时调度任务
# ============================================================

@celery_app.task
def schedule_full_crawl():
    """全量竞品数据抓取调度 - 每6小时执行"""
    logger.info("Starting full crawl schedule...")

    async def _dispatch():
        from sqlalchemy import select
        from app.models.competitor import Competitor

        async with async_session_factory() as session:
            result = await session.execute(select(Competitor.slug))
            slugs = [row[0] for row in result.fetchall()]

        # 为每个竞品创建 pricing + web 采集任务
        task_count = 0
        for slug in slugs:
            for task_type in ["pricing", "web"]:
                run_spider_job.delay(
                    competitor_slug=slug,
                    task_type=task_type,
                    spider_engine="httpx",
                )
                task_count += 1

        logger.info(f"Full crawl dispatched: {task_count} tasks for {len(slugs)} competitors")
        return {"dispatched_tasks": task_count, "competitors": len(slugs)}

    return asyncio.run(_dispatch())


@celery_app.task
def schedule_sentiment_crawl():
    """舆情增量采集调度 - 每30分钟执行"""
    logger.info("Starting sentiment crawl schedule...")

    async def _dispatch():
        from sqlalchemy import select
        from app.models.competitor import Competitor

        async with async_session_factory() as session:
            result = await session.execute(select(Competitor.slug))
            slugs = [row[0] for row in result.fetchall()]

        task_count = 0
        for slug in slugs:
            run_spider_job.delay(
                competitor_slug=slug,
                task_type="sentiment",
                spider_engine="httpx",
            )
            task_count += 1

        logger.info(f"Sentiment crawl dispatched: {task_count} tasks")
        return {"dispatched_tasks": task_count}

    return asyncio.run(_dispatch())
