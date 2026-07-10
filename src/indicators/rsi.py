"""
RSI 相对强弱指标 (权重 15%)
===============================
使用 Wilder's RSI 计算 14 日相对强弱，判断超买/超卖状态。

Wilder's smoothing: 初始值用 SMA，之后用 EMA 递推。
评分和图表计算现已统一。
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict

from config import RSI_PERIOD, RSI_THRESHOLDS

logger = logging.getLogger(__name__)


def _wilder_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI 计算 (评分和图表统一使用此函数)。

    Wilder's smoothing:
      初始 avg_gain/avg_loss = SMA(period)
      之后 avg_gain = (prev_avg_gain * (period-1) + current_gain) / period
      即 EMA with alpha = 1/period, adjust=False。
    """
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    # Wilder's smoothing: EMA with span=period, adjust=False
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def calculate_rsi(data: Dict) -> Dict:
    """
    基于 NDX 收盘价计算 Wilder's RSI(14) 并评分。

    输出：
        {"score": int, "rsi": float, "rsi_5d_ago": float,
         "assessment": str, "zone": str}
    """
    result = {
        "score": None,
        "rsi": None,
        "rsi_5d_ago": None,
        "assessment": "无法计算",
        "zone": "unknown",
    }

    ndx_history = data.get("ndx_history", pd.DataFrame())
    if ndx_history.empty or "close" not in ndx_history.columns:
        logger.warning("No NDX history for RSI calculation")
        return result

    closes = ndx_history["close"].dropna()
    if len(closes) < RSI_PERIOD + 1:
        logger.warning(f"Not enough data for RSI: {len(closes)} days")
        return result

    # 使用 Wilder's RSI
    rsi_series = _wilder_rsi(closes, RSI_PERIOD)
    rsi_series = rsi_series.dropna()

    if rsi_series.empty:
        return result

    current_rsi = float(rsi_series.iloc[-1])
    result["rsi"] = round(current_rsi, 1)

    # 5 天前 RSI（判断趋势）
    if len(rsi_series) >= 6:
        result["rsi_5d_ago"] = round(float(rsi_series.iloc[-6]), 1)

    # 评分
    if current_rsi < RSI_THRESHOLDS["oversold"]:
        result["score"] = 2
        result["zone"] = "超卖"
        result["assessment"] = "RSI 低于 30，处于超卖区域，反弹概率较高"
    elif current_rsi < RSI_THRESHOLDS["weak"]:
        result["score"] = 1
        result["zone"] = "偏弱"
        result["assessment"] = "RSI 偏弱，短期动能不足但有修复空间"
    elif current_rsi < RSI_THRESHOLDS["neutral_high"]:
        result["score"] = 0
        result["zone"] = "中性"
        result["assessment"] = "RSI 处中性区间，无明确方向信号"
    elif current_rsi < RSI_THRESHOLDS["strong"]:
        result["score"] = -1
        result["zone"] = "偏强"
        result["assessment"] = "RSI 偏高，短期可能超买，追高需谨慎"
    else:
        result["score"] = -2
        result["zone"] = "超买"
        result["assessment"] = "RSI 高于 70，处于超买区域，回调风险增加"

    logger.info(
        f"RSI(Wilder): {current_rsi:.1f}, score: {result['score']}, "
        f"zone: {result['zone']}"
    )
    return result
