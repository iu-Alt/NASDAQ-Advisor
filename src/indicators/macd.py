"""
MACD 趋势动能指标 (权重 10%)
================================
计算 MACD(12,26,9)，判断金叉/死叉及趋势强度。
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict

from config import MACD_FAST, MACD_SLOW, MACD_SIGNAL

logger = logging.getLogger(__name__)


def calculate_macd(data: Dict) -> Dict:
    """
    基于 NDX 收盘价计算 MACD 并评分。

    输出：
        {"score": int, "macd_line": float, "signal_line": float,
         "histogram": float, "histogram_prev": float,
         "crossover": str, "assessment": str}
    """
    result = {
        "score": 0,
        "macd_line": None,
        "signal_line": None,
        "histogram": None,
        "histogram_prev": None,
        "crossover": "none",
        "assessment": "无法计算",
    }

    ndx_history = data.get("ndx_history", pd.DataFrame())
    if ndx_history.empty or "close" not in ndx_history.columns:
        logger.warning("No NDX history for MACD calculation")
        return result

    closes = ndx_history["close"].dropna()
    if len(closes) < MACD_SLOW + MACD_SIGNAL + 2:
        logger.warning(f"Not enough data for MACD: {len(closes)} days")
        return result

    # 计算 EMA
    ema_fast = closes.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = closes.ewm(span=MACD_SLOW, adjust=False).mean()

    # MACD 线
    macd_line = ema_fast - ema_slow

    # 信号线
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()

    # 柱状线 (histogram)
    histogram = macd_line - signal_line

    result["macd_line"] = round(float(macd_line.iloc[-1]), 4)
    result["signal_line"] = round(float(signal_line.iloc[-1]), 4)
    result["histogram"] = round(float(histogram.iloc[-1]), 4)
    result["histogram_prev"] = round(float(histogram.iloc[-2]), 4)

    macd_now = result["histogram"]
    macd_prev = result["histogram_prev"]

    # 判断金叉/死叉
    hist_was_negative = macd_prev < 0
    hist_is_positive = macd_now > 0
    hist_was_positive = macd_prev > 0
    hist_is_negative = macd_now < 0

    # 柱状线是否在扩大 (绝对值变大)
    histogram_expanding = abs(macd_now) > abs(macd_prev)

    if hist_was_negative and hist_is_positive:
        result["crossover"] = "golden_cross"
        if histogram_expanding:
            result["score"] = 2
            result["assessment"] = "MACD 金叉 + 动能扩大，强力看涨信号"
        else:
            result["score"] = 1
            result["assessment"] = "MACD 金叉，趋势转为看涨"
    elif hist_was_positive and hist_is_negative:
        result["crossover"] = "death_cross"
        if histogram_expanding:
            result["score"] = -2
            result["assessment"] = "MACD 死叉 + 动能扩大，强力看跌信号"
        else:
            result["score"] = -1
            result["assessment"] = "MACD 死叉，趋势转为看跌"
    elif hist_is_positive:
        # 仍在多方区域
        if histogram_expanding:
            result["score"] = 1
            result["assessment"] = "MACD 多方动能增强"
        else:
            result["score"] = 0
            result["assessment"] = "MACD 多方动能减弱中"
    elif hist_is_negative:
        # 仍在空方区域
        if histogram_expanding:
            result["score"] = -1
            result["assessment"] = "MACD 空方动能增强"
        else:
            result["score"] = 0
            result["assessment"] = "MACD 空方动能减弱，可能筑底"
    else:
        result["score"] = 0
        result["assessment"] = "MACD 中性"

    logger.info(f"MACD hist: {macd_now:.4f}, crossover: {result['crossover']}, "
                f"score: {result['score']}")
    return result
