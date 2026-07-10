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
         "trend_regime": str, "strong_uptrend": bool, "assessment": str}
    """
    result = {
        "score": None,
        "current_price": None,
        "ma50": None,
        "ma200": None,
        "deviation_ma50_pct": None,
        "deviation_ma200_pct": None,
        "price_above_ma50": None,
        "ma50_above_ma200": None,
        "ma200_slope_6m_pct": None,
        "momentum_6m_pct": None,
        "momentum_12m_pct": None,
        "drawdown_from_52w_high_pct": None,
        "trend_regime": "unknown",
        "strong_uptrend": False,
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

    ma50 = result["ma50"]
    result["price_above_ma50"] = current_price > ma50 if ma50 else None
    result["ma50_above_ma200"] = ma50 > ma200 if ma50 else None

    if len(closes) >= 326:
        ma200_6m_ago = float(closes.iloc[-326:-126].mean())
        result["ma200_slope_6m_pct"] = round((ma200 - ma200_6m_ago) / ma200_6m_ago * 100, 2)

    if len(closes) >= 127:
        price_6m_ago = float(closes.iloc[-127])
        result["momentum_6m_pct"] = round((current_price - price_6m_ago) / price_6m_ago * 100, 2)

    if len(closes) >= 253:
        price_12m_ago = float(closes.iloc[-253])
        result["momentum_12m_pct"] = round((current_price - price_12m_ago) / price_12m_ago * 100, 2)

    high_52w = float(closes.tail(252).max()) if len(closes) >= 252 else float(closes.max())
    result["drawdown_from_52w_high_pct"] = round((current_price - high_52w) / high_52w * 100, 2)

    dev_200 = result["deviation_ma200_pct"]
    dev_50 = result["deviation_ma50_pct"] or 0
    ma200_slope = result["ma200_slope_6m_pct"]
    momentum_6m = result["momentum_6m_pct"]
    drawdown_52w = result["drawdown_from_52w_high_pct"]

    is_aligned_up = bool(result["price_above_ma50"] and result["ma50_above_ma200"])
    ma200_rising = ma200_slope is not None and ma200_slope > 0
    momentum_positive = momentum_6m is not None and momentum_6m > 0
    shallow_drawdown = drawdown_52w is not None and drawdown_52w > -15

    if is_aligned_up and ma200_rising and momentum_positive and shallow_drawdown:
        result["trend_regime"] = "strong_uptrend"
        result["strong_uptrend"] = True
    elif current_price > ma200 and result["ma50_above_ma200"]:
        result["trend_regime"] = "uptrend"
    elif current_price < ma200 and ma50 and ma50 < ma200:
        result["trend_regime"] = "downtrend"
    elif ma50 and current_price < ma50 and ma50 > ma200:
        result["trend_regime"] = "correction_in_uptrend"
    else:
        result["trend_regime"] = "neutral"

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
        if result["strong_uptrend"]:
            result["score"] = -1
            result["assessment"] = (
                f"强上升趋势但高于 MA200 {dev_200:.1f}%，不追高但不轻易暂停"
            )
        else:
            result["score"] = -2
            result["assessment"] = f"严重超涨：高于 MA200 {dev_200:.1f}%，回调风险极大"
    elif dev_50 > MA_DEVIATION_THRESHOLDS["above_ma50"]:
        if result["strong_uptrend"]:
            result["score"] = 0
            result["assessment"] = (
                f"强上升趋势中高于 MA50 {dev_50:.1f}%，暂停追加但保持基础定投"
            )
        else:
            result["score"] = -1
            result["assessment"] = f"偏高：高于 MA50 {dev_50:.1f}%，短期追高需谨慎"
    else:
        if result["strong_uptrend"]:
            result["score"] = 1
            result["assessment"] = "价格、均线、动量共振上行，趋势质量较强"
        elif current_price > ma200 and ma50 and ma50 > ma200:
            result["score"] = 1
            result["assessment"] = "价格在 MA200 上方且均线多头排列，趋势健康"
        elif result["trend_regime"] == "downtrend":
            result["score"] = -1
            result["assessment"] = "价格与均线结构偏弱，趋势保护失效"
        else:
            result["score"] = 0
            result["assessment"] = "价格在均线附近整理"

    logger.info(f"MA deviation: MA200={dev_200:.1f}%, MA50={dev_50:.1f}%, "
                f"trend={result['trend_regime']}, score: {result['score']}")
    return result
