"""
Sentiment业务逻辑层 - 舆情面板、趋势分析、情感分析、热点事件
集成DeepSeek API进行情感分析（按量计费 ¥0.5/次）
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.models.competitor import Competitor
from app.models.sentiment import SentimentRecord
from app.models.user import User
from app.schemas.sentiment import (
    CompetitorSentiment,
    HotEvent,
    SentimentAnalyzeRequest,
    SentimentAnalyzeResponse,
    SentimentDashboardResponse,
    SentimentDistribution,
    SentimentEventResponse,
    SentimentTrendsResponse,
    TrendPoint,
)
from app.services.auth_service import AuthService
from app.services.sentiment_engine import sentiment_engine

CST = timezone(timedelta(hours=8))

# 情感分析单价（¥/次）
ANALYZE_COST_PER_REQUEST = 0.5


class SentimentService:
    """舆情服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_service = AuthService(db)

    # ============================================================
    # 舆情面板
    # ============================================================

    async def get_dashboard(self) -> SentimentDashboardResponse:
        """
        舆情面板聚合数据
        返回: 总览统计 + 各竞品舆情概览 + 热点事件
        """
        # 1. 总览统计
        total_result = await self.db.execute(
            select(func.count()).select_from(SentimentRecord)
        )
        total_mentions = total_result.scalar_one() or 0

        # 情感分布
        positive_count = await self._count_by_label("positive")
        neutral_count = await self._count_by_label("neutral")
        negative_count = await self._count_by_label("negative")

        total = positive_count + neutral_count + negative_count
        if total > 0:
            distribution = SentimentDistribution(
                positive=round(positive_count / total * 100),
                neutral=round(neutral_count / total * 100),
                negative=round(negative_count / total * 100),
            )
        else:
            distribution = SentimentDistribution(positive=0, neutral=0, negative=0)

        # 热门话题（从最近100条记录中提取）
        trending_topics = await self._get_trending_topics(limit=100, top_n=10)

        overview = {
            "total_mentions": total_mentions,
            "sentiment_distribution": distribution.model_dump(),
            "trending_topics": trending_topics,
        }

        # 2. 各竞品舆情概览
        competitor_sentiments = await self._get_competitor_sentiments()

        return SentimentDashboardResponse(
            overview=overview,
            competitors=competitor_sentiments,
            updated_at=datetime.now(CST),
        )

    # ============================================================
    # 趋势分析
    # ============================================================

    async def get_trends(
        self,
        days: int = 30,
        competitor_slug: str | None = None,
    ) -> SentimentTrendsResponse:
        """
        热点追踪趋势图数据
        返回最近N天每日的情感分布
        """
        end_date = datetime.now(CST).date()
        start_date = end_date - timedelta(days=days)

        # 构建日期范围查询
        query = select(SentimentRecord).where(
            and_(
                SentimentRecord.published_at >= start_date,
                SentimentRecord.published_at <= end_date,
            )
        )
        if competitor_slug:
            query = query.where(SentimentRecord.competitor_slug == competitor_slug)

        result = await self.db.execute(query.order_by(SentimentRecord.published_at))
        records = result.scalars().all()

        # 按日期聚合
        daily_data: dict[str, dict[str, int]] = {}
        for r in records:
            date_key = r.published_at.strftime("%Y-%m-%d")
            if date_key not in daily_data:
                daily_data[date_key] = {"positive": 0, "neutral": 0, "negative": 0, "total": 0}
            daily_data[date_key][r.sentiment_label] += 1
            daily_data[date_key]["total"] += 1

        # 补齐缺失日期
        trend_points = []
        for i in range(days + 1):
            d = start_date + timedelta(days=i)
            date_key = d.strftime("%Y-%m-%d")
            data = daily_data.get(date_key, {"positive": 0, "neutral": 0, "negative": 0, "total": 0})
            trend_points.append(TrendPoint(
                date=d,
                positive=data["positive"],
                neutral=data["neutral"],
                negative=data["negative"],
                total=data["total"],
            ))

        # 热门话题
        topics = await self._get_trending_topics(limit=50, top_n=5)

        return SentimentTrendsResponse(
            time_range=f"{days}d",
            data=trend_points,
            topics=topics,
        )

    # ============================================================
    # 情感分析（按量计费）
    # ============================================================

    async def analyze(
        self,
        request: SentimentAnalyzeRequest,
        current_user: User,
    ) -> SentimentAnalyzeResponse:
        """
        对输入文本进行情感分析
        按量计费: ¥0.5/次
        扩展入口: 未来可对接DeepSeek API进行更精确的分析
        """
        # 1. 消耗配额
        await self.auth_service.check_and_consume_quota(current_user.id, cost=1)

        # 2. 调用情感分析引擎（当前使用规则引擎，未来可替换为DeepSeek API）
        result = await self._analyze_text(request.text)

        # 3. 如果有关联竞品，保存到数据库
        if request.competitor_slug:
            content_hash = hashlib.sha256(request.text.encode()).hexdigest()
            record = SentimentRecord(
                competitor_slug=request.competitor_slug,
                source="manual",
                content=request.text[:500],  # 脱敏截断
                content_hash=content_hash,
                sentiment_score=result["score"],
                sentiment_label=result["label"],
                topics=json.dumps(result["topics"]) if result["topics"] else None,
                published_at=datetime.now(CST),
            )
            self.db.add(record)
            await self.db.flush()

        return SentimentAnalyzeResponse(
            sentiment_score=result["score"],
            sentiment_label=result["label"],
            confidence=result["confidence"],
            topics=result["topics"],
            cost=ANALYZE_COST_PER_REQUEST,
        )

    # ============================================================
    # 热点事件
    # ============================================================

    async def get_events(
        self,
        slug: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SentimentEventResponse], int]:
        """获取指定竞品的热点事件列表"""
        # 验证竞品存在
        result = await self.db.execute(
            select(Competitor).where(Competitor.slug == slug)
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundError.competitor(slug)

        # 查询总数
        count_result = await self.db.execute(
            select(func.count()).select_from(SentimentRecord).where(
                SentimentRecord.competitor_slug == slug
            )
        )
        total = count_result.scalar_one() or 0

        # 分页查询（按情感强度排序，负面优先）
        result = await self.db.execute(
            select(SentimentRecord)
            .where(SentimentRecord.competitor_slug == slug)
            .order_by(
                desc(func.abs(SentimentRecord.sentiment_score)),
                desc(SentimentRecord.published_at),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        records = result.scalars().all()

        items = []
        for r in records:
            topics = None
            if r.topics:
                try:
                    topics = json.loads(r.topics)
                except (json.JSONDecodeError, TypeError):
                    topics = None
            items.append(SentimentEventResponse(
                id=r.id,
                competitor_slug=r.competitor_slug,
                source=r.source,
                content=r.content,
                sentiment_score=r.sentiment_score,
                sentiment_label=r.sentiment_label,
                topics=topics,
                published_at=r.published_at,
                created_at=r.created_at,
            ))

        return items, total

    # ============================================================
    # 舆情记录列表
    # ============================================================

    async def list_records(
        self,
        competitor_slug: str | None = None,
        source: str | None = None,
        sentiment_label: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SentimentRecord], int]:
        """舆情记录列表查询"""
        query = select(SentimentRecord)
        count_query = select(func.count()).select_from(SentimentRecord)

        filters = []
        if competitor_slug:
            filters.append(SentimentRecord.competitor_slug == competitor_slug)
        if source:
            filters.append(SentimentRecord.source == source)
        if sentiment_label:
            filters.append(SentimentRecord.sentiment_label == sentiment_label)

        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one() or 0

        result = await self.db.execute(
            query
            .order_by(desc(SentimentRecord.published_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        records = result.scalars().all()

        return list(records), total

    # ============================================================
    # 内部方法
    # ============================================================

    async def _count_by_label(self, label: str) -> int:
        """按情感标签计数"""
        result = await self.db.execute(
            select(func.count()).select_from(SentimentRecord).where(
                SentimentRecord.sentiment_label == label
            )
        )
        return result.scalar_one() or 0

    async def _get_trending_topics(self, limit: int, top_n: int) -> list[str]:
        """
        提取热门话题
        从最近N条记录的topics字段中提取频率最高的话题
        """
        result = await self.db.execute(
            select(SentimentRecord.topics)
            .where(SentimentRecord.topics.isnot(None))
            .order_by(desc(SentimentRecord.published_at))
            .limit(limit)
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

        # 按频率排序取前N
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_topics[:top_n]]

    async def _get_competitor_sentiments(self) -> list[CompetitorSentiment]:
        """获取各竞品的舆情概览"""
        # 获取所有竞品
        comp_result = await self.db.execute(select(Competitor))
        competitors = comp_result.scalars().all()

        sentiments = []
        for comp in competitors:
            # 查询该竞品的舆情统计
            mention_result = await self.db.execute(
                select(func.count()).select_from(SentimentRecord).where(
                    SentimentRecord.competitor_slug == comp.slug
                )
            )
            mention_count = mention_result.scalar_one() or 0

            # 计算平均情感得分（映射到0-100）
            avg_result = await self.db.execute(
                select(func.avg(SentimentRecord.sentiment_score)).where(
                    SentimentRecord.competitor_slug == comp.slug
                )
            )
            avg_score = avg_result.scalar_one() or 0.0
            sentiment_score = int((avg_score + 1) / 2 * 100)  # -1~+1 → 0~100

            # 热点事件（最近3条高分记录）
            event_result = await self.db.execute(
                select(SentimentRecord)
                .where(SentimentRecord.competitor_slug == comp.slug)
                .order_by(desc(func.abs(SentimentRecord.sentiment_score)))
                .limit(3)
            )
            events = event_result.scalars().all()
            hot_events = [
                HotEvent(
                    title=e.content[:50] + "..." if len(e.content) > 50 else e.content,
                    impact="high" if abs(e.sentiment_score) > 0.7 else "medium",
                )
                for e in events
            ]

            sentiments.append(CompetitorSentiment(
                slug=comp.slug,
                sentiment_score=sentiment_score,
                mention_count=mention_count,
                hot_events=hot_events,
            ))

        # 按提及次数排序
        sentiments.sort(key=lambda x: x.mention_count, reverse=True)
        return sentiments

    async def _analyze_text(self, text: str) -> dict[str, Any]:
        """
        文本情感分析引擎 - 调用DeepSeek API进行真实AI分析
        降级策略: API不可用时自动切换到规则引擎
        """
        result = await sentiment_engine.analyze_text(text)

        # 补充topics字段以兼容原有调用方
        if "topics" not in result:
            result["topics"] = ["综合评价"]

        return result
