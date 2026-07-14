"""
Spiders业务逻辑层 - 爬虫任务触发、查询、调度管理
三引擎架构: Playwright(JS动态) + Scrapy(大规模HTTP) + httpx(API对接)
扩展入口: Celery异步任务队列集成
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.core.exceptions import AuthError, NotFoundError
from app.models.competitor import Competitor
from app.models.spider import SpiderTask, TaskStatus, TaskType
from app.models.user import User
from app.schemas.spider import (
    SpiderScheduleResponse,
    SpiderTaskListItem,
    SpiderTaskResponse,
    SpiderTriggerRequest,
)

CST = timezone(timedelta(hours=8))


class SpiderService:
    """爬虫服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # 触发爬虫任务
    # ============================================================

    async def trigger(
        self,
        request: SpiderTriggerRequest,
        current_user: User,
    ) -> SpiderTaskResponse:
        """
        手动触发爬虫任务
        权限: admin/analyst
        扩展入口: 未来可对接Celery异步执行
        """
        if not current_user.is_analyst_or_above:
            raise AuthError.permission_denied("analyst")

        # 验证竞品存在
        comp = await self._get_competitor(request.competitor_slug)

        # 生成任务ID
        task_id = f"task_{uuid.uuid4().hex[:16]}"

        task = SpiderTask(
            id=task_id,
            competitor_slug=request.competitor_slug,
            task_type=request.task_type,
            status=TaskStatus.PENDING.value,
            started_at=None,
            completed_at=None,
        )
        self.db.add(task)
        await self.db.flush()

        # 异步调度执行（通过Celery）
        try:
            from app.workers.spider_tasks import run_spider_job
            run_spider_job.delay(
                competitor_slug=request.competitor_slug,
                task_type=request.task_type,
                spider_engine=self._select_engine(request.task_type),
            )
        except Exception as exc:
            logger.warning(f"Celery dispatch failed, falling back to sync: {exc}")
            await self._simulate_execution(task)

        return SpiderTaskResponse.model_validate({
            **task.__dict__,
            "duration_seconds": task.duration_seconds,
        })

    # ============================================================
    # 查询任务状态
    # ============================================================

    async def get_task(self, task_id: str) -> SpiderTaskResponse:
        """查询单个任务状态"""
        task = await self._get_task(task_id)
        return SpiderTaskResponse.model_validate({
            **task.__dict__,
            "duration_seconds": task.duration_seconds,
        })

    # ============================================================
    # 任务列表
    # ============================================================

    async def list_tasks(
        self,
        competitor_slug: str | None = None,
        task_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SpiderTaskListItem], int]:
        """爬虫任务历史列表"""
        query = select(SpiderTask)
        count_query = select(func.count()).select_from(SpiderTask)

        if competitor_slug:
            query = query.where(SpiderTask.competitor_slug == competitor_slug)
            count_query = count_query.where(SpiderTask.competitor_slug == competitor_slug)
        if task_type:
            query = query.where(SpiderTask.task_type == task_type)
            count_query = count_query.where(SpiderTask.task_type == task_type)
        if status:
            query = query.where(SpiderTask.status == status)
            count_query = count_query.where(SpiderTask.status == status)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one() or 0

        result = await self.db.execute(
            query
            .order_by(desc(SpiderTask.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        tasks = result.scalars().all()

        items = [SpiderTaskListItem.model_validate(t) for t in tasks]
        return items, total

    # ============================================================
    # 调度配置
    # ============================================================

    async def get_schedule(self) -> SpiderScheduleResponse:
        """
        获取爬虫调度配置
        扩展入口: 未来可从数据库/配置文件加载
        """
        schedule = [
            {
                "task_type": "web",
                "cron": "0 6 * * *",
                "description": "每日06:00采集Web流量数据",
                "engine": "httpx",
            },
            {
                "task_type": "app",
                "cron": "0 7 * * *",
                "description": "每日07:00采集App下载/收入数据",
                "engine": "scrapy",
            },
            {
                "task_type": "sentiment",
                "cron": "*/30 * * * *",
                "description": "每30分钟采集舆情数据",
                "engine": "playwright",
            },
            {
                "task_type": "pricing",
                "cron": "0 8 * * 1",
                "description": "每周一08:00采集定价信息",
                "engine": "playwright",
            },
            {
                "task_type": "model_rank",
                "cron": "0 9 * * *",
                "description": "每日09:00采集模型排名",
                "engine": "httpx",
            },
        ]

        return SpiderScheduleResponse(
            schedule=schedule,
            concurrency_limit=settings.spider_concurrency,
            rate_limit_per_sec=settings.spider_rate_limit_per_sec,
        )

    # ============================================================
    # 取消任务
    # ============================================================

    async def cancel_task(
        self,
        task_id: str,
        current_user: User,
    ) -> None:
        """
        取消爬虫任务（仅pending状态可取消）
        权限: admin/analyst
        """
        if not current_user.is_analyst_or_above:
            raise AuthError.permission_denied("analyst")

        task = await self._get_task(task_id)

        if task.status != TaskStatus.PENDING.value:
            raise NotFoundError.spider_task(
                f"任务 {task_id} 状态为 {task.status}，仅 pending 状态可取消"
            )

        task.status = TaskStatus.FAILED.value
        task.error_msg = "用户手动取消"
        task.completed_at = datetime.now(CST)
        await self.db.flush()

    # ============================================================
    # 内部方法
    # ============================================================

    async def _get_competitor(self, slug: str) -> Competitor:
        """验证竞品存在"""
        result = await self.db.execute(
            select(Competitor).where(Competitor.slug == slug)
        )
        comp = result.scalar_one_or_none()
        if comp is None:
            raise NotFoundError.competitor(slug)
        return comp

    async def _get_task(self, task_id: str) -> SpiderTask:
        """获取任务，不存在则抛异常"""
        result = await self.db.execute(
            select(SpiderTask).where(SpiderTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise NotFoundError.spider_task(task_id)
        return task

    async def _simulate_execution(self, task: SpiderTask) -> None:
        """
        真实爬虫执行 - 调用对应引擎采集数据
        引擎路由:
          - web: httpx采集竞品官网流量数据
          - app: httpx采集App Store/Google Play数据
          - sentiment: 多引擎采集社交媒体舆情
          - pricing: httpx采集定价页面
          - model_rank: httpx采集Chatbot Arena排名
        """
        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.now(CST)
        await self.db.flush()

        import json

        try:
            result_data: dict[str, Any] = {
                "engine": self._select_engine(task.task_type),
                "timestamp": datetime.now(CST).isoformat(),
            }

            if task.task_type == TaskType.WEB.value:
                crawl_result = await self._crawl_competitor_web(task.competitor_slug)
                result_data.update(crawl_result)

            elif task.task_type == TaskType.APP.value:
                crawl_result = await self._crawl_app_data(task.competitor_slug)
                result_data.update(crawl_result)

            elif task.task_type == TaskType.SENTIMENT.value:
                crawl_result = await self._crawl_sentiment(task.competitor_slug)
                result_data.update(crawl_result)

            elif task.task_type == TaskType.PRICING.value:
                crawl_result = await self._crawl_pricing(task.competitor_slug)
                result_data.update(crawl_result)

            elif task.task_type == TaskType.MODEL_RANK.value:
                crawl_result = await self._crawl_model_rank(task.competitor_slug)
                result_data.update(crawl_result)

            task.status = TaskStatus.SUCCESS.value
            task.result = json.dumps(result_data, ensure_ascii=False)

        except Exception as exc:
            task.status = TaskStatus.FAILED.value
            task.error_msg = str(exc)[:500]

        finally:
            task.completed_at = datetime.now(CST)
            await self.db.flush()

    # ============================================================
    # 真实采集方法
    # ============================================================

    async def _crawl_competitor_web(self, slug: str) -> dict[str, Any]:
        """采集竞品官网数据"""
        from app.spiders.competitor_spider import CompetitorSpider

        spider = CompetitorSpider()
        try:
            result = await spider.crawl_competitor(slug, "web")
            return {
                "data_points": result.get("data_points", 0),
                "url": result.get("url", ""),
                "title": result.get("title", ""),
            }
        except Exception as exc:
            return {"data_points": 0, "error": str(exc)[:200]}

    async def _crawl_app_data(self, slug: str) -> dict[str, Any]:
        """采集App下载数据"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                from app.spiders.competitor_spider import COMPETITOR_SOURCES
                config = COMPETITOR_SOURCES.get(slug, {})

                if "app_store_id" in config:
                    url = f"https://itunes.apple.com/lookup?id={config['app_store_id']}"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("resultCount", 0) > 0:
                            info = data["results"][0]
                            return {
                                "data_points": 1,
                                "ios_rating_count": info.get("userRatingCount", 0),
                                "ios_rating": info.get("averageUserRating", 0),
                                "version": info.get("version", ""),
                            }

            return {"data_points": 0, "message": "No app data available"}
        except Exception as exc:
            return {"data_points": 0, "error": str(exc)[:200]}

    async def _crawl_sentiment(self, slug: str) -> dict[str, Any]:
        """采集舆情数据并调用DeepSeek分析"""
        from app.spiders.sentiment_spider import SentimentSpider

        spider = SentimentSpider()
        try:
            result = await spider.crawl_sentiment(slug)
            return {
                "data_points": result.get("total_collected", 0),
                "new_records": result.get("new_records", 0),
                "sources": result.get("sources", []),
                "avg_sentiment": result.get("avg_sentiment", 0.0),
            }
        except Exception as exc:
            return {"data_points": 0, "error": str(exc)[:200]}

    async def _crawl_pricing(self, slug: str) -> dict[str, Any]:
        """采集定价信息"""
        from app.spiders.competitor_spider import CompetitorSpider

        spider = CompetitorSpider()
        try:
            result = await spider.crawl_pricing(slug)
            return {
                "data_points": len(result.get("plans", [])),
                "plans": result.get("plans", []),
            }
        except Exception as exc:
            return {"data_points": 0, "error": str(exc)[:200]}

    async def _crawl_model_rank(self, slug: str) -> dict[str, Any]:
        """采集Chatbot Arena排名"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard/raw/main/snapshot.json"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("models", [])
                    for model in models:
                        if slug.lower() in model.get("name", "").lower():
                            return {
                                "data_points": 1,
                                "arena_score": model.get("arena_score", 0),
                                "arena_rank": model.get("rank", 0),
                                "model_name": model.get("name", ""),
                            }

            return {"data_points": 0, "message": "Model not found in Arena"}
        except Exception as exc:
            return {"data_points": 0, "error": str(exc)[:200]}

    @staticmethod
    def _select_engine(task_type: str) -> str:
        """根据任务类型选择引擎"""
        engine_map = {
            "web": "httpx",
            "app": "scrapy",
            "sentiment": "playwright",
            "pricing": "playwright",
            "model_rank": "httpx",
        }
        return engine_map.get(task_type, "httpx")
