"""
宏观利率指标 (权重 10%) + 美元指数 DXY (权重 5%)
====================================================
分析联邦基金利率趋势、10Y-2Y 利差、美元指数走势。
利率环境对科技股（纳斯达克）估值影响显著。
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict

from config import SPREAD_THRESHOLDS, DXY_THRESHOLDS

logger = logging.getLogger(__name__)


def calculate_macro(data: Dict) -> Dict:
    """
    分析宏观利率数据并评分。

    输出：
        {"score": int, "spread_10y_2y": float, "fed_funds_rate": float,
         "rate_trend": str, "assessment": str}
    """
    result = {
        "score": 0,
        "spread_10y_2y": None,
        "fed_funds_rate": None,
        "yield_10y": None,
        "yield_2y": None,
        "rate_trend": None,
        "assessment": "无法计算",
    }

    macro_data = data.get("macro", {})
    if not macro_data:
        logger.warning("No macro data available")
        return result

    spread = macro_data.get("spread_10y_2y")
    fed_rate = macro_data.get("fed_funds_rate")
    rate_trend = macro_data.get("rate_trend")

    result["spread_10y_2y"] = round(spread, 4) if spread is not None else None
    result["fed_funds_rate"] = round(fed_rate, 2) if fed_rate is not None else None
    result["yield_10y"] = macro_data.get("yield_10y")
    result["yield_2y"] = macro_data.get("yield_2y")
    result["rate_trend"] = rate_trend

    if spread is None:
        logger.warning("No spread data for macro scoring")
        # 尝试只用利率趋势评分
        if rate_trend == "cutting":
            result["score"] = 2
            result["assessment"] = "美联储降息周期中，利好科技股估值"
        elif rate_trend == "hiking":
            result["score"] = -2
            result["assessment"] = "美联储加息周期中，压制科技股估值"
        else:
            result["score"] = 0
            result["assessment"] = "利率趋势不明，宏观面中性"
        return result

    # 综合利差与利率趋势评分
    score = 0
    parts = []

    # 利差评分
    if spread < SPREAD_THRESHOLDS["deep_inversion"]:
        score += 2
        parts.append("利差深度倒挂")
    elif spread < SPREAD_THRESHOLDS["inversion"]:
        score += 1
        parts.append("利差倒挂")
    elif spread < SPREAD_THRESHOLDS["normal_low"]:
        score += 0
        parts.append("利差正常偏低")
    else:
        score -= 1
        parts.append("利差正常偏高")

    # 利率趋势调整
    if rate_trend == "cutting":
        score = max(score, 1)  # 降息至少是正面
        parts.append("降息趋势")
    elif rate_trend == "hiking":
        score = min(score, -1)  # 加息至少是负面
        parts.append("加息趋势")

    # 限制分数范围
    result["score"] = max(-2, min(2, score))
    result["assessment"] = "；".join(parts) if parts else "宏观面信号中性"

    logger.info(f"Macro: spread={spread:.2f}%, rate_trend={rate_trend}, "
                f"score: {result['score']}")
    return result


def calculate_dxy(data: Dict) -> Dict:
    """
    分析美元指数走势并评分。

    输出：
        {"score": int, "current_dxy": float, "dxy_20d_change_pct": float,
         "dxy_50d_avg": float, "assessment": str}
    """
    result = {
        "score": 0,
        "current_dxy": None,
        "dxy_20d_change_pct": None,
        "dxy_50d_avg": None,
        "assessment": "无法计算",
    }

    dxy_history = data.get("dxy_history", pd.DataFrame())
    if dxy_history.empty or "close" not in dxy_history.columns:
        logger.warning("No DXY history data")
        return result

    dxy_close = dxy_history["close"].dropna()
    if len(dxy_close) < 50:
        logger.warning(f"Not enough DXY data: {len(dxy_close)} days")
        return result

    current_dxy = float(dxy_close.iloc[-1])
    result["current_dxy"] = round(current_dxy, 2)

    # 50 日均值
    result["dxy_50d_avg"] = round(float(dxy_close.iloc[-50:].mean()), 2)

    # 20 日涨跌幅
    if len(dxy_close) >= 20:
        dxy_20d_ago = float(dxy_close.iloc[-20])
        result["dxy_20d_change_pct"] = round(
            (current_dxy - dxy_20d_ago) / dxy_20d_ago * 100, 2
        )

    change = result["dxy_20d_change_pct"]
    if change is None:
        return result

    if change > DXY_THRESHOLDS["strong_up"]:
        result["score"] = -1
        result["assessment"] = f"美元近 20 日走强 {change:.1f}%，不利美股（尤其是科技股）"
    elif change < DXY_THRESHOLDS["strong_down"]:
        result["score"] = 1
        result["assessment"] = f"美元近 20 日走弱 {abs(change):.1f}%，有利美股流动性"
    else:
        result["score"] = 0
        direction = "走强" if change > 0 else "走弱"
        result["assessment"] = f"美元近 20 日小幅{direction} ({change:.1f}%)，影响有限"

    logger.info(f"DXY: {current_dxy:.2f}, 20d change: {change:.1f}%, "
                f"score: {result['score']}")
    return result
