"""
均线偏离度指标 (权重 10%)
=============================
计算 NDX 收盘价相对于 MA50 和 MA200 的偏离百分比。
结合两个均线判断趋势强度与均值回归信号。
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict

from config import MA_DEVIATION_THRESHOLDS

logger = logging.getLogger(__name__)


def calculate_ma_deviation(data: Dict) -> Dict:
    """
    计算 NDX 价格相对 MA50/MA200 的偏离度并评分。

    输出：
        {"score": int, "current_price": float, "ma50": float, "ma200": float,
         "deviation_ma50_pct": float, "deviation_ma200_pct": float,
         "assessment": str}
    """
    result = {
        "score": 0,
        "current_price": None,
        "ma50": None,
        "ma200": None,
        "deviation_ma50_pct": None,
        "deviation_ma200_pct": None,
        "assessment": "无法计算",
    }

    ndx_history = data.get("ndx_history", pd.DataFrame())
    if ndx_history.empty or "close" not in ndx_history.columns:
        logger.warning("No NDX history for MA deviation calculation")
        return result

    closes = ndx_history["close"].dropna()
    if len(closes) < 200:
        logger.warning(f"Not enough data for MA200: {len(closes)} days")
        return result

    current_price = float(closes.iloc[-1])
    result["current_price"] = round(current_price, 2)

    # MA50
    if len(closes) >= 50:
        ma50 = float(closes.iloc[-50:].mean())
        result["ma50"] = round(ma50, 2)
        result["deviation_ma50_pct"] = round((current_price - ma50) / ma50 * 100, 2)

    # MA200
    ma200 = float(closes.iloc[-200:].mean())
    result["ma200"] = round(ma200, 2)
    result["deviation_ma200_pct"] = round((current_price - ma200) / ma200 * 100, 2)

    dev_200 = result["deviation_ma200_pct"]
    dev_50 = result["deviation_ma50_pct"] or 0

    # 评分逻辑（以 MA200 偏离为主，MA50 作为辅助）
    if dev_200 is None:
        return result

    if dev_200 < MA_DEVIATION_THRESHOLDS["deep_below_ma200"]:
        result["score"] = 2
        result["assessment"] = f"极端超跌：低于 MA200 {abs(dev_200):.1f}%，强烈均值回归信号"
    elif dev_200 < MA_DEVIATION_THRESHOLDS["below_ma200"]:
        result["score"] = 1
        result["assessment"] = f"偏低：低于 MA200 {abs(dev_200):.1f}%，有一定回归动力"
    elif dev_200 > MA_DEVIATION_THRESHOLDS["above_ma200_extreme"]:
        result["score"] = -2
        result["assessment"] = f"严重超涨：高于 MA200 {dev_200:.1f}%，回调风险极大"
    elif dev_50 > MA_DEVIATION_THRESHOLDS["above_ma50"]:
        result["score"] = -1
        result["assessment"] = f"偏高：高于 MA50 {dev_50:.1f}%，短期追高需谨慎"
    else:
        result["score"] = 0
        if current_price > ma200:
            result["assessment"] = "价格在均线上方运行，趋势健康"
        else:
            result["assessment"] = "价格在均线附近整理"

    logger.info(f"MA deviation: MA200={dev_200:.1f}%, MA50={dev_50:.1f}%, "
                f"score: {result['score']}")
    return result
