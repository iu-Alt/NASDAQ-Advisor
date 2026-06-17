"""
RSI 相对强弱指标 (权重 10%)
===============================
计算 14 日 RSI，判断超买/超卖状态。
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict

from config import RSI_PERIOD, RSI_THRESHOLDS

logger = logging.getLogger(__name__)


def calculate_rsi(data: Dict) -> Dict:
    """
    基于 NDX 收盘价计算 RSI(14) 并评分。

    输出：
        {"score": int, "rsi": float, "rsi_5d_ago": float,
         "assessment": str, "zone": str}
    """
    result = {
        "score": 0,
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

    # 手动计算 RSI（避免依赖 ta 库版本问题）
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.rolling(window=RSI_PERIOD, min_periods=RSI_PERIOD).mean()
    avg_loss = loss.rolling(window=RSI_PERIOD, min_periods=RSI_PERIOD).mean()

    # 使用 Wilder's smoothing（EMA of gains/losses）
    # 简化版：直接用 SMA 近似
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
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

    logger.info(f"RSI: {current_rsi:.1f}, score: {result['score']}, zone: {result['zone']}")
    return result
