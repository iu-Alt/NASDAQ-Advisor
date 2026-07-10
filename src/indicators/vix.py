"""
VIX 恐慌指数指标 (权重 20%)
===============================
VIX (CBOE Volatility Index) 衡量标普 500 期权隐含波动率。
优先使用 VXN (Nasdaq-100 波动率指数) 作为纳指策略的主指标。

评分使用连续区间，消除 VIX > 35 的悬崖跳变 (原 +2 → -1)。
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional

from config import VIX_THRESHOLDS, VXN_THRESHOLDS

logger = logging.getLogger(__name__)


def calculate_vix(data: Dict) -> Dict:
    """
    分析当前 VIX/VXN 水平并评分。

    优先使用 VXN (Nasdaq-100 波动率)，VIX 作为 fallback。
    连续评分：> 35 不再跳到 -1，而是平滑过渡。

    输出：
        {"score": int, "current_vix": float, "current_vxn": float,
         "vol_index_used": str, "percentile_1y": float,
         "vix_20d_avg": float, "assessment": str, "zone": str}
    """
    result = {
        "score": None,
        "current_vix": None,
        "current_vxn": None,
        "vol_index_used": "unknown",
        "percentile_1y": None,
        "vix_20d_avg": None,
        "vix_50d_avg": None,
        "assessment": "无法计算",
        "zone": "unknown",
    }

    # 优先使用 VXN
    vxn = data.get("vxn_current")
    vix = data.get("vix_current")

    # 选择波动率指数和对应阈值
    if vxn is not None and vxn > 0:
        vol_value = vxn
        thresholds = VXN_THRESHOLDS
        result["vol_index_used"] = "VXN"
        result["current_vxn"] = round(vxn, 2)
    elif vix is not None and vix > 0:
        vol_value = vix
        thresholds = VIX_THRESHOLDS
        result["vol_index_used"] = "VIX"
    else:
        logger.warning("No VIX or VXN data available")
        return result

    result["current_vix"] = round(vol_value, 2)

    # 计算历史分位
    vix_history = data.get("vix_history", pd.DataFrame())
    if not vix_history.empty and "close" in vix_history.columns:
        vix_close = vix_history["close"].dropna()

        # 1 年分位
        cutoff_1y = vix_close.index[-1] - pd.DateOffset(years=1)
        vix_1y = vix_close[vix_close.index >= cutoff_1y]
        if len(vix_1y) > 20:
            result["percentile_1y"] = round(
                (vix_1y < vol_value).mean() * 100, 1
            )

        # 20 日和 50 日均值
        if len(vix_close) >= 20:
            result["vix_20d_avg"] = round(float(vix_close.iloc[-20:].mean()), 2)
        if len(vix_close) >= 50:
            result["vix_50d_avg"] = round(float(vix_close.iloc[-50:].mean()), 2)

    # 连续评分 — 无悬崖跳变
    v = vol_value

    # 使用缓坡过渡代替原来的 >35 → -1 悬崖
    if v < thresholds["extreme_calm"]:
        result["score"] = -1
        result["zone"] = "极度平静"
        result["assessment"] = "市场极度平静，可能酝酿自满情绪，警惕尾部风险"
    elif v < thresholds["calm"]:
        result["score"] = 0
        result["zone"] = "正常偏低"
        result["assessment"] = "波动率处正常偏低水平，市场情绪稳定"
    elif v < thresholds["moderate_fear"]:
        result["score"] = 1
        result["zone"] = "适度恐慌"
        result["assessment"] = "市场出现适度恐慌，定投者可适度加仓"
    elif v < thresholds["high_fear"]:
        result["score"] = 2
        result["zone"] = "高度恐慌"
        result["assessment"] = "市场高度恐慌，恐慌时往往是买入良机"
    elif v < thresholds["extreme_fear"]:
        # 35-50 (VIX) / 38-55 (VXN): 仍然偏高，但降级到 +1
        result["score"] = 1
        result["zone"] = "深度恐慌"
        result["assessment"] = "波动率很高，仍可能是机会但风险加大，适度参与"
    else:
        # > 50 (VIX) / > 55 (VXN): 极端波动，保持中性
        result["score"] = 0
        result["zone"] = "极端恐慌/危机"
        result["assessment"] = "市场极端恐慌，波动剧烈，建议观望等待企稳"

    logger.info(
        f"{result['vol_index_used']}: {v}, score: {result['score']}, "
        f"zone: {result['zone']}"
    )
    return result
