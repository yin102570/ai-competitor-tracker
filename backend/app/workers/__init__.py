"""
Celery 应用配置
消息代理: Redis
任务队列: spiders（爬虫）, default（通用）
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "ai-competitor-tracker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.spider_tasks",
        "app.workers.maintenance_tasks",
    ],
)

# Celery配置
celery_app.conf.update(
    # 序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,

    # 任务结果过期（1小时）
    result_expires=3600,

    # 任务限流
    task_annotations={
        "app.workers.spider_tasks.run_spider_job": {
            "rate_limit": f"{settings.spider_rate_limit_per_sec}/s",
        },
    },

    # Worker配置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,

    # Beat定时任务调度
    beat_schedule={
        # 每6小时执行全量竞品数据抓取
        "spider-full-crawl": {
            "task": "app.workers.spider_tasks.schedule_full_crawl",
            "schedule": 21600.0,  # 6小时 = 21600秒
            "args": (),
        },
        # 每30分钟执行舆情增量采集
        "spider-sentiment-incremental": {
            "task": "app.workers.spider_tasks.schedule_sentiment_crawl",
            "schedule": 1800.0,  # 30分钟
            "args": (),
        },
        # 每日凌晨重置用户配额
        "reset-daily-quota": {
            "task": "app.workers.maintenance_tasks.reset_daily_quota",
            "schedule": 86400.0,  # 24小时
            "args": (),
        },
        # 每日凌晨3点执行数据备份
        "daily-backup": {
            "task": "app.workers.maintenance_tasks.daily_backup",
            "schedule": 10800.0,  # 3AM（通过crontab风格更精确，但此处简化）
            "args": (),
        },
        # 每小时清理过期审计日志（可选扩展）
        "cleanup-old-audit-logs": {
            "task": "app.workers.maintenance_tasks.cleanup_old_logs",
            "schedule": 3600.0,  # 1小时
            "args": (),
        },
    },

    # 任务路由
    task_routes={
        "app.workers.spider_tasks.*": {"queue": "spiders"},
        "app.workers.maintenance_tasks.*": {"queue": "default"},
    },

    # 队列定义
    task_default_queue="default",
    task_queues={
        "default": {},
        "spiders": {},
    },
)

# 显式导入任务模块，确保所有 @celery_app.task 装饰器在 Worker 启动前执行
from app.workers import spider_tasks  # noqa: E402, F401
from app.workers import maintenance_tasks  # noqa: E402, F401


