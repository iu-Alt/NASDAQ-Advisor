"""
恐慌贪婪指数指标 (权重 10%)
===============================
从 CNN Fear & Greed Index 获取市场情绪数据，
备选方案：用 VIX + 市场宽度合成近似值。
"""

import logging
import numpy as np
from typing import Dict

from config import FEAR_GREED_THRESHOLDS

logger = logging.getLogger(__name__)


def calculate_fear_greed(data: Dict) -> Dict:
    """
    分析恐慌贪婪指数并评分。
    如果 CNN 数据不可用，用 VIX 水平估算。

    输出：
        {"score": int, "value": float, "rating": str,
         "source": str, "assessment": str}
    """
    result = {
        "score": 0,
        "value": None,
        "rating": "unknown",
        "source": None,
        "assessment": "无法计算",
    }

    fg_data = data.get("fear_greed")

    # ---- 方案 A：使用 CNN 数据 ----
    if fg_data and fg_data.get("value") is not None:
        value = fg_data["value"]
        rating = fg_data.get("rating", "")

        result["value"] = value
        result["rating"] = rating
        result["source"] = fg_data.get("source", "cnn_api")

        if value <= FEAR_GREED_THRESHOLDS["extreme_fear"]:
            result["score"] = 2
            result["assessment"] = "市场极度恐慌，历史上恐慌期往往是最佳买入时机"
        elif value <= FEAR_GREED_THRESHOLDS["fear"]:
            result["score"] = 1
            result["assessment"] = "市场偏恐慌，逆向投资者可考虑加仓"
        elif value <= FEAR_GREED_THRESHOLDS["neutral"]:
            result["score"] = 0
            result["assessment"] = "市场情绪中性，无明确情绪面信号"
        elif value <= FEAR_GREED_THRESHOLDS["greed"]:
            result["score"] = -1
            result["assessment"] = "市场偏贪婪，追涨风险上升"
        else:
            result["score"] = -2
            result["assessment"] = "市场极度贪婪，当别人贪婪时应当恐惧"

        logger.info(f"Fear & Greed: {value} ({rating}), score: {result['score']}")
        return result

    # ---- 方案 B：用 VIX 近似估计 ----
    vix_current = data.get("vix_current")
    if vix_current is not None and vix_current > 0:
        # 近似映射 VIX → Fear & Greed
        # VIX < 12 → Greed 75+
        # VIX 12-18 → Greed 55-75
        # VIX 18-25 → Neutral 45-55
        # VIX 25-35 → Fear 25-45
        # VIX > 35 → Extreme Fear 0-25
        if vix_current < 12:
            est_value = 80
            est_rating = "Greed (estimated)"
        elif vix_current < 18:
            est_value = 65
            est_rating = "Greed (estimated)"
        elif vix_current < 25:
            est_value = 50
            est_rating = "Neutral (estimated)"
        elif vix_current < 35:
            est_value = 35
            est_rating = "Fear (estimated)"
        else:
            est_value = 15
            est_rating = "Extreme Fear (estimated)"

        result["value"] = est_value
        result["rating"] = est_rating
        result["source"] = "vix_derived"

        # 评分逻辑同上
        if est_value <= FEAR_GREED_THRESHOLDS["extreme_fear"]:
            result["score"] = 2
            result["assessment"] = f"VIX 推算市场极度恐慌 (VIX={vix_current:.1f})"
        elif est_value <= FEAR_GREED_THRESHOLDS["fear"]:
            result["score"] = 1
            result["assessment"] = f"VIX 推算市场偏恐慌 (VIX={vix_current:.1f})"
        elif est_value <= FEAR_GREED_THRESHOLDS["neutral"]:
            result["score"] = 0
            result["assessment"] = f"VIX 推算市场情绪中性 (VIX={vix_current:.1f})"
        elif est_value <= FEAR_GREED_THRESHOLDS["greed"]:
            result["score"] = -1
            result["assessment"] = f"VIX 推算市场偏贪婪 (VIX={vix_current:.1f})"
        else:
            result["score"] = -2
            result["assessment"] = f"VIX 推算市场极度贪婪 (VIX={vix_current:.1f})"

        logger.info(f"Fear & Greed (VIX-derived): {est_value}, score: {result['score']}")
        return result

    logger.warning("No Fear & Greed data available (CNN unavailable, VIX also missing)")
    return result
