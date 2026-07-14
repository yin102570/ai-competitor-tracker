"""
DeepSeek 舆情分析引擎 - 真实AI情感分析
功能: 情感打分 / 主题提取 / 关键事件识别 / 批量分析
Prompt工程: 结构化JSON输出，支持中英文混合分析
"""

import json
import logging
from typing import Any

from app.core.deepseek_client import deepseek_client

logger = logging.getLogger(__name__)


# ============================================================
# Prompt模板
# ============================================================

SENTIMENT_SYSTEM_PROMPT = """你是一个专业的AI产品舆情分析师。你需要对用户提供的文本进行情感分析。

分析要求:
1. 情感打分: -1.0 到 +1.0（-1=极度负面, 0=中性, +1=极度正面）
2. 情感标签: positive / neutral / negative
3. 置信度: 0.0 到 1.0（你对这个判断有多确定）
4. 主题提取: 从文本中提取1-5个关键话题标签（如"价格"、"功能"、"性能"、"安全隐私"、"用户体验"、"技术能力"、"市场表现"等）
5. 情感关键词: 提取3-5个影响情感判断的关键词
6. 摘要: 一句话总结文本核心观点（不超过50字）

你必须返回JSON格式，结构如下:
{
  "score": 0.8,
  "label": "positive",
  "confidence": 0.95,
  "topics": ["功能", "用户体验"],
  "keywords": ["强大", "便捷", "推荐"],
  "summary": "用户对产品功能表示满意并推荐使用"
}"""

BATCH_SENTIMENT_SYSTEM_PROMPT = """你是一个专业的AI产品舆情分析师。你需要对用户提供的多条文本进行批量情感分析。

输入格式: 一个包含多条文本的JSON数组。
输出格式: 一个JSON对象，包含分析结果数组，每条文本对应一个分析结果。

你必须返回JSON格式，结构如下:
{
  "results": [
    {
      "index": 0,
      "score": 0.8,
      "label": "positive",
      "confidence": 0.95,
      "topics": ["功能"],
      "keywords": ["强大"],
      "summary": "用户满意"
    }
  ],
  "overall_sentiment": 0.65,
  "overall_label": "positive",
  "total_analyzed": 3
}"""

COMPETITOR_ANALYSIS_SYSTEM_PROMPT = """你是一个专业的AI竞品分析师。你需要基于提供的舆情数据，生成竞品分析报告。

分析维度:
1. 整体舆情态势: 基于情感分布判断该竞品当前舆论环境
2. 核心优势: 用户/媒体普遍提及的优点
3. 主要痛点: 用户/媒体普遍提及的问题
4. 舆情风险: 是否存在公关危机苗头
5. 趋势预判: 基于近期舆情走向的预判

你必须返回JSON格式，结构如下:
{
  "overall_sentiment": "positive",
  "sentiment_score": 0.65,
  "strengths": ["技术领先", "用户量大"],
  "pain_points": ["定价偏高", "客服响应慢"],
  "risks": ["近期数据隐私争议可能升级"],
  "trend_prediction": "短期内舆情平稳，建议关注隐私相关讨论",
  "confidence": 0.85
}"""


class SentimentAnalysisEngine:
    """DeepSeek驱动的舆情分析引擎"""

    # ============================================================
    # 单条文本情感分析
    # ============================================================

    async def analyze_text(self, text: str) -> dict[str, Any]:
        """
        对单条文本进行深度情感分析

        参数:
            text: 待分析文本（支持中英文）

        返回:
            {
                "score": float,        # -1.0 ~ +1.0
                "label": str,          # positive/neutral/negative
                "confidence": float,   # 0.0 ~ 1.0
                "topics": list[str],   # 主题标签
                "keywords": list[str], # 情感关键词
                "summary": str,        # 一句话摘要
            }
        """
        # 文本预处理
        text = text.strip()[:2000]  # 限制长度，控制token消耗
        if not text:
            return {
                "score": 0.0,
                "label": "neutral",
                "confidence": 0.0,
                "topics": [],
                "keywords": [],
                "summary": "空文本",
            }

        messages = [
            {"role": "system", "content": SENTIMENT_SYSTEM_PROMPT},
            {"role": "user", "content": f"请分析以下文本的情感:\n\n{text}"},
        ]

        try:
            result = await deepseek_client.chat_completion_json(
                messages=messages,
                temperature=0.1,  # 低温度保证一致性
                max_tokens=512,
            )
            data = result["data"]

            # 数据校验和规范化
            score = float(data.get("score", 0.0))
            score = max(-1.0, min(1.0, score))

            label = data.get("label", "neutral")
            if label not in ("positive", "neutral", "negative"):
                label = "neutral" if abs(score) < 0.2 else ("positive" if score > 0 else "negative")

            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            topics = data.get("topics", [])
            if not isinstance(topics, list):
                topics = [str(topics)] if topics else []

            keywords = data.get("keywords", [])
            if not isinstance(keywords, list):
                keywords = [str(keywords)] if keywords else []

            summary = str(data.get("summary", ""))[:100]

            return {
                "score": round(score, 2),
                "label": label,
                "confidence": round(confidence, 2),
                "topics": topics[:5],
                "keywords": keywords[:5],
                "summary": summary,
            }

        except Exception as exc:
            logger.error(f"DeepSeek sentiment analysis failed: {exc}")
            # 降级到规则引擎
            return self._fallback_analysis(text)

    # ============================================================
    # 批量文本情感分析
    # ============================================================

    async def analyze_batch(self, texts: list[str]) -> dict[str, Any]:
        """
        批量分析多条文本（减少API调用次数）

        参数:
            texts: 文本列表（最多20条/次）

        返回:
            {
                "results": [...],       # 每条文本的分析结果
                "overall_sentiment": float,
                "overall_label": str,
                "total_analyzed": int,
            }
        """
        if not texts:
            return {
                "results": [],
                "overall_sentiment": 0.0,
                "overall_label": "neutral",
                "total_analyzed": 0,
            }

        # 限制批量大小
        texts = texts[:20]
        # 每条文本限制长度
        texts = [t.strip()[:500] for t in texts]

        messages = [
            {"role": "system", "content": BATCH_SENTIMENT_SYSTEM_PROMPT},
            {"role": "user", "content": f"请分析以下{len(texts)}条文本的情感:\n\n{json.dumps(texts, ensure_ascii=False)}"},
        ]

        try:
            result = await deepseek_client.chat_completion_json(
                messages=messages,
                temperature=0.1,
                max_tokens=2048,
            )
            data = result["data"]

            # 规范化结果
            results = data.get("results", [])
            for r in results:
                r["score"] = max(-1.0, min(1.0, float(r.get("score", 0.0))))
                r["confidence"] = max(0.0, min(1.0, float(r.get("confidence", 0.5))))

            overall = float(data.get("overall_sentiment", 0.0))

            return {
                "results": results,
                "overall_sentiment": round(overall, 2),
                "overall_label": data.get("overall_label", "neutral"),
                "total_analyzed": len(results),
            }

        except Exception as exc:
            logger.error(f"DeepSeek batch analysis failed: {exc}")
            # 降级: 逐条分析
            results = []
            for i, text in enumerate(texts):
                r = await self.analyze_text(text)
                r["index"] = i
                results.append(r)

            scores = [r["score"] for r in results]
            overall = sum(scores) / len(scores) if scores else 0.0

            return {
                "results": results,
                "overall_sentiment": round(overall, 2),
                "overall_label": "positive" if overall > 0.2 else ("negative" if overall < -0.2 else "neutral"),
                "total_analyzed": len(results),
            }

    # ============================================================
    # 竞品综合分析报告
    # ============================================================

    async def generate_competitor_report(
        self,
        competitor_name: str,
        sentiment_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        基于舆情数据生成竞品分析报告

        参数:
            competitor_name: 竞品名称
            sentiment_data: 舆情记录列表 [{"content": "...", "score": 0.8, "label": "positive"}]

        返回:
            {
                "overall_sentiment": str,
                "sentiment_score": float,
                "strengths": list[str],
                "pain_points": list[str],
                "risks": list[str],
                "trend_prediction": str,
                "confidence": float,
            }
        """
        # 准备数据摘要（避免token过多）
        data_summary = []
        for item in sentiment_data[:50]:  # 最多50条
            data_summary.append({
                "text": item.get("content", "")[:200],
                "score": item.get("score", 0),
                "label": item.get("label", "neutral"),
            })

        messages = [
            {"role": "system", "content": COMPETITOR_ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": f"竞品: {competitor_name}\n\n舆情数据:\n{json.dumps(data_summary, ensure_ascii=False)}"},
        ]

        try:
            result = await deepseek_client.chat_completion_json(
                messages=messages,
                temperature=0.3,
                max_tokens=1024,
            )
            return result["data"]

        except Exception as exc:
            logger.error(f"DeepSeek competitor report failed: {exc}")
            return {
                "overall_sentiment": "neutral",
                "sentiment_score": 0.0,
                "strengths": [],
                "pain_points": [],
                "risks": ["分析服务暂时不可用"],
                "trend_prediction": "无法生成预判",
                "confidence": 0.0,
            }

    # ============================================================
    # 降级方案: 规则引擎
    # ============================================================

    def _fallback_analysis(self, text: str) -> dict[str, Any]:
        """API不可用时的规则引擎降级"""
        positive_words = {
            "好", "棒", "优秀", "推荐", "喜欢", "满意", "强大", "领先", "创新",
            "突破", "惊艳", "高效", "智能", "便捷", "完美", "出色", "赞", "爱",
            "great", "excellent", "amazing", "love", "best", "perfect", "awesome",
        }
        negative_words = {
            "差", "烂", "垃圾", "失望", "后悔", "糟糕", "卡顿", "bug", "崩溃",
            "慢", "贵", "坑", "骗", "难用", "恶心", "讨厌", "烦",
            "bad", "terrible", "awful", "hate", "worst", "horrible", "disappointing",
        }

        text_lower = text.lower()
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        total = pos_count + neg_count

        if total == 0:
            score, label, confidence = 0.0, "neutral", 0.3
        else:
            score = (pos_count - neg_count) / max(total, 1)
            score = max(-1.0, min(1.0, score))
            if score > 0.2:
                label, confidence = "positive", 0.6
            elif score < -0.2:
                label, confidence = "negative", 0.6
            else:
                label, confidence = "neutral", 0.5

        topics = ["综合评价"]

        return {
            "score": round(score, 2),
            "label": label,
            "confidence": round(confidence, 2),
            "topics": topics,
            "keywords": [],
            "summary": "规则引擎分析（API降级模式）",
        }


# 全局单例
sentiment_engine = SentimentAnalysisEngine()
