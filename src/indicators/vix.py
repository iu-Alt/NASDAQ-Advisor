"""
VIX 恐慌指数指标 (权重 15%)
===============================
VIX (CBOE Volatility Index) 衡量标普 500 期权隐含波动率，
是市场恐慌/贪婪情绪的"恐惧指数"。
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional

from config import VIX_THRESHOLDS

logger = logging.getLogger(__name__)


def calculate_vix(data: Dict) -> Dict:
    """
    分析当前 VIX 水平并评分。

    输出：
        {"score": int, "current_vix": float,
         "percentile_1y": float, "vix_20d_avg": float,
         "assessment": str, "zone": str}
    """
    result = {
        "score": 0,
        "current_vix": None,
        "percentile_1y": None,
        "vix_20d_avg": None,
        "vix_50d_avg": None,
        "assessment": "无法计算",
        "zone": "unknown",
    }

    # 当前 VIX
    vix_current = data.get("vix_current")
    if vix_current is None or vix_current <= 0:
        logger.warning("No valid VIX current value")
        return result

    result["current_vix"] = round(vix_current, 2)

    # 计算历史分位
    vix_history = data.get("vix_history", pd.DataFrame())
    if not vix_history.empty and "close" in vix_history.columns:
        vix_close = vix_history["close"].dropna()

        # 1 年分位
        cutoff_1y = vix_close.index[-1] - pd.DateOffset(years=1)
        vix_1y = vix_close[vix_close.index >= cutoff_1y]
        if len(vix_1y) > 20:
            result["percentile_1y"] = round((vix_1y < vix_current).mean() * 100, 1)

        # 20 日和 50 日均值
        if len(vix_close) >= 20:
            result["vix_20d_avg"] = round(float(vix_close.iloc[-20:].mean()), 2)
        if len(vix_close) >= 50:
            result["vix_50d_avg"] = round(float(vix_close.iloc[-50:].mean()), 2)

    # 评分逻辑
    v = vix_current

    if v < VIX_THRESHOLDS["extreme_calm"]:
        result["score"] = -1
        result["zone"] = "极度平静"
        result["assessment"] = "市场极度平静，可能酝酿自满情绪，警惕尾部风险"
    elif v < VIX_THRESHOLDS["calm"]:
        result["score"] = 0
        result["zone"] = "正常偏低"
        result["assessment"] = "VIX 处正常偏低水平，市场情绪稳定"
    elif v < VIX_THRESHOLDS["moderate_fear"]:
        result["score"] = 1
        result["zone"] = "适度恐慌"
        result["assessment"] = "市场出现适度恐慌，定投者可适度加仓"
    elif v < VIX_THRESHOLDS["high_fear"]:
        result["score"] = 2
        result["zone"] = "高度恐慌"
        result["assessment"] = "市场高度恐慌，恐慌时往往是买入良机"
    else:
        result["score"] = -1
        result["zone"] = "极端恐慌/危机"
        result["assessment"] = "市场极端恐慌，波动剧烈，建议观望等待企稳"

    logger.info(f"VIX: {v}, score: {result['score']}, zone: {result['zone']}")
    return result
