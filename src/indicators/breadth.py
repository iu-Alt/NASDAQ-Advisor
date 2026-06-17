"""
市场宽度指标 (权重 5%)
==========================
计算 NDX 成分股中价格高于 MA50 的比例。
衡量市场参与度和广度——少数权重股拉抬 vs 全面上涨。
"""

import logging
from typing import Dict

from config import BREADTH_THRESHOLDS

logger = logging.getLogger(__name__)


def calculate_breadth(data: Dict) -> Dict:
    """
    分析市场宽度数据并评分。

    输出：
        {"score": int, "pct_above_ma50": float,
         "stocks_checked": int, "stocks_above_ma50": int,
         "assessment": str}
    """
    result = {
        "score": 0,
        "pct_above_ma50": None,
        "stocks_checked": 0,
        "stocks_above_ma50": 0,
        "assessment": "无法计算",
    }

    breadth_data = data.get("breadth", {})
    if not breadth_data:
        logger.warning("No breadth data available")
        return result

    pct = breadth_data.get("pct_above_ma50")
    total = breadth_data.get("stocks_checked", 0)
    above = breadth_data.get("stocks_above_ma50", 0)

    result["pct_above_ma50"] = pct
    result["stocks_checked"] = total
    result["stocks_above_ma50"] = above

    if pct is None:
        logger.warning("Breadth data incomplete")
        return result

    # 如果 total=0，说明是近似估算值，仍然可以评分
    is_estimated = (total == 0)

    # 评分
    note = " (估算)" if is_estimated else ""
    if pct < BREADTH_THRESHOLDS["extreme_pessimism"]:
        result["score"] = 2
        result["assessment"] = f"仅 {pct:.0f}% 成分股在 MA50 上方{note}，市场极度悲观，往往是底部信号"
    elif pct < BREADTH_THRESHOLDS["pessimism"]:
        result["score"] = 1
        result["assessment"] = f"{pct:.0f}% 成分股在 MA50 上方{note}，市场宽度偏弱，反弹潜力"
    elif pct < BREADTH_THRESHOLDS["neutral"]:
        result["score"] = 0
        result["assessment"] = f"{pct:.0f}% 成分股在 MA50 上方{note}，市场宽度中性"
    elif pct < BREADTH_THRESHOLDS["optimism"]:
        result["score"] = -1
        result["assessment"] = f"{pct:.0f}% 成分股在 MA50 上方{note}，市场偏乐观"
    else:
        result["score"] = -2
        result["assessment"] = f"{pct:.0f}% 成分股在 MA50 上方{note}，过度乐观，警惕回调"

    logger.info(f"Breadth: {pct:.1f}% above MA50, score: {result['score']}")
    return result
