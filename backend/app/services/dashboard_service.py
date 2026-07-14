"""
Dashboard业务逻辑层 - 综合看板聚合 + WebSocket连接管理
职责: 聚合competitors/sentiment/spiders数据，提供统一看板视图
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor, CompetitorHistory
from app.models.sentiment import SentimentRecord
from app.models.spider import SpiderTask, TaskStatus
from app.schemas.dashboard import (
    CompetitorOverview,
    DashboardOverviewResponse,
    SentimentSummary,
    SpiderStatus,
)

CST = timezone(timedelta(hours=8))


class DashboardService:
    """Dashboard服务 - 数据聚合"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # 综合看板
    # ============================================================

    async def get_overview(self) -> DashboardOverviewResponse:
        """
        综合看板数据聚合
        聚合competitors/sentiment/spiders数据，提供统一视图
        """
        now = datetime.now(CST)

        # 1. 竞品概览
        competitors = await self._get_competitor_overviews()

        # 2. 舆情总览
        sentiment = await self._get_sentiment_summary()

        # 3. 爬虫状态
        spiders = await self._get_spider_status()

        # 4. 系统状态
        system = {
            "version": "1.0.0",
            "uptime_seconds": 0,  # 扩展入口: 从应用启动时间计算
            "api_requests_24h": 0,  # 扩展入口: 从audit_logs统计
        }

        return DashboardOverviewResponse(
            competitors=competitors,
            sentiment=sentiment,
            spiders=spiders,
            system=system,
            updated_at=now,
        )

    # ============================================================
    # 竞品概览聚合
    # ============================================================

    async def _get_competitor_overviews(self) -> list[CompetitorOverview]:
        """获取竞品概览列表"""
        result = await self.db.execute(
            select(Competitor).order_by(Competitor.updated_at.desc())
        )
        comps = result.scalars().all()

        overviews = []
        for comp in comps:
            # 最新历史快照
            latest = await self._get_latest_snapshot(comp.slug)

            # 舆情统计
            sentiment_result = await self.db.execute(
                select(func.avg(SentimentRecord.sentiment_score)).where(
                    SentimentRecord.competitor_slug == comp.slug
                )
            )
            avg_sentiment = sentiment_result.scalar_one() or 0.0
            sentiment_score = int((avg_sentiment + 1) / 2 * 100)

            # 热点事件
            hot_events = await self._get_hot_events(comp.slug)

            # 趋势
            trend = await self._calc_trend(comp.slug)

            overviews.append(CompetitorOverview(
                slug=comp.slug,
                name=comp.name,
                category=comp.category,
                monthly_visits=latest.monthly_visits if latest else None,
                ios_downloads=latest.ios_downloads if latest else None,
                android_downloads=latest.android_downloads if latest else None,
                arena_score=latest.arena_score if latest else None,
                arena_rank=latest.arena_rank if latest else None,
                sentiment_score=sentiment_score,
                trend=trend,
                hot_events=hot_events,
            ))

        return overviews

    # ============================================================
    # 舆情总览
    # ============================================================

    async def _get_sentiment_summary(self) -> SentimentSummary:
        """获取舆情总览统计"""
        total = await self._count_sentiment()
        positive = await self._count_sentiment("positive")
        neutral = await self._count_sentiment("neutral")
        negative = await self._count_sentiment("negative")

        if total > 0:
            positive_pct = round(positive / total * 100)
            neutral_pct = round(neutral / total * 100)
            negative_pct = round(negative / total * 100)
        else:
            positive_pct = neutral_pct = negative_pct = 0

        # 预警数量（最近1小时负面激增）
        alert_count = await self._count_recent_alerts()

        # 热门话题
        trending_topics = await self._get_trending_topics()

        return SentimentSummary(
            total_mentions=total,
            positive_pct=positive_pct,
            neutral_pct=neutral_pct,
            negative_pct=negative_pct,
            trending_topics=trending_topics,
            alert_count=alert_count,
        )

    # ============================================================
    # 爬虫状态
    # ============================================================

    async def _get_spider_status(self) -> SpiderStatus:
        """获取爬虫运行状态"""
        total_result = await self.db.execute(
            select(func.count()).select_from(SpiderTask)
        )
        total_tasks = total_result.scalar_one() or 0

        running_result = await self.db.execute(
            select(func.count()).select_from(SpiderTask).where(
                SpiderTask.status == TaskStatus.RUNNING.value
            )
        )
        running_tasks = running_result.scalar_one() or 0

        # 24小时统计
        day_ago = datetime.now(CST) - timedelta(hours=24)
        success_result = await self.db.execute(
            select(func.count()).select_from(SpiderTask).where(
                SpiderTask.status == TaskStatus.SUCCESS.value,
                SpiderTask.completed_at >= day_ago,
            )
        )
        success_24h = success_result.scalar_one() or 0

        failed_result = await self.db.execute(
            select(func.count()).select_from(SpiderTask).where(
                SpiderTask.status == TaskStatus.FAILED.value,
                SpiderTask.completed_at >= day_ago,
            )
        )
        failed_24h = failed_result.scalar_one() or 0

        return SpiderStatus(
            total_tasks=total_tasks,
            running_tasks=running_tasks,
            success_tasks_24h=success_24h,
            failed_tasks_24h=failed_24h,
            next_scheduled="*/30 * * * *",  # 扩展入口: 从调度配置加载
        )

    # ============================================================
    # 内部方法
    # ============================================================

    async def _get_latest_snapshot(self, slug: str) -> CompetitorHistory | None:
        """获取最新历史快照"""
        result = await self.db.execute(
            select(CompetitorHistory)
            .where(CompetitorHistory.competitor_slug == slug)
            .order_by(desc(CompetitorHistory.date))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_hot_events(self, slug: str, limit: int = 3) -> list[str]:
        """获取热点事件标题"""
        result = await self.db.execute(
            select(SentimentRecord)
            .where(SentimentRecord.competitor_slug == slug)
            .order_by(desc(func.abs(SentimentRecord.sentiment_score)))
            .limit(limit)
        )
        records = result.scalars().all()
        return [
            r.content[:50] + "..." if len(r.content) > 50 else r.content
            for r in records
        ]

    async def _calc_trend(self, slug: str) -> str | None:
        """计算流量趋势"""
        result = await self.db.execute(
            select(CompetitorHistory)
            .where(CompetitorHistory.competitor_slug == slug)
            .order_by(desc(CompetitorHistory.date))
            .limit(2)
        )
        snapshots = result.scalars().all()
        if len(snapshots) < 2:
            return None

        current = snapshots[0].monthly_visits or 0
        previous = snapshots[1].monthly_visits or 0
        if previous == 0:
            return "up" if current > 0 else None

        change = (current - previous) / previous * 100
        if change > 5:
            return "up"
        elif change < -5:
            return "down"
        return "stable"

    async def _count_sentiment(self, label: str | None = None) -> int:
        """按标签计数舆情记录"""
        query = select(func.count()).select_from(SentimentRecord)
        if label:
            query = query.where(SentimentRecord.sentiment_label == label)
        result = await self.db.execute(query)
        return result.scalar_one() or 0

    async def _count_recent_alerts(self) -> int:
        """计算最近1小时的预警数量"""
        hour_ago = datetime.now(CST) - timedelta(hours=1)
        result = await self.db.execute(
            select(func.count()).select_from(SentimentRecord).where(
                SentimentRecord.sentiment_label == "negative",
                SentimentRecord.published_at >= hour_ago,
            )
        )
        return result.scalar_one() or 0

    async def _get_trending_topics(self, limit: int = 10) -> list[str]:
        """提取热门话题"""
        result = await self.db.execute(
            select(SentimentRecord.topics)
            .where(SentimentRecord.topics.isnot(None))
            .order_by(desc(SentimentRecord.published_at))
            .limit(100)
        )
        topics_list = result.scalars().all()

        topic_counts: dict[str, int] = {}
        for topics_json in topics_list:
            try:
                topics = json.loads(topics_json)
                if isinstance(topics, list):
                    for t in topics:
                        topic_counts[t] = topic_counts.get(t, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue

        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_topics[:limit]]
