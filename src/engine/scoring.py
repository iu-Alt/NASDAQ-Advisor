"""
加权评分引擎
================
汇总所有 9 个指标的分数，按配置权重计算加权总分。
"""

import logging
from typing import Dict, List

from config import WEIGHTS

logger = logging.getLogger(__name__)


def calculate_total_score(indicator_results: Dict[str, Dict]) -> Dict:
    """
    输入：所有指标计算结果的字典
      {
        "pe_percentile": {"score": int, ...},
        "vix": {"score": int, ...},
        ...
      }
    输出：
      {
        "total_score": float,
        "max_possible": float,
        "weighted_breakdown": [{"indicator": str, "score": int, "weight": float,
                                 "weighted": float, "assessment": str}, ...],
        "score_pct": float,  # 相对满分百分比
        "missing_indicators": [str, ...],
      }
    """
    result = {
        "total_score": 0.0,
        "max_possible": 0.0,
        "weighted_breakdown": [],
        "score_pct": 0.0,
        "missing_indicators": [],
    }

    breakdown = []
    total_weighted = 0.0
    total_weight_used = 0.0

    for indicator_key, weight in WEIGHTS.items():
        ind_result = indicator_results.get(indicator_key, {})

        if not ind_result or ind_result.get("score") is None:
            result["missing_indicators"].append(indicator_key)
            logger.warning(f"Missing indicator: {indicator_key}")
            continue

        score = ind_result["score"]
        weighted = score * weight
        total_weighted += weighted
        total_weight_used += weight

        breakdown.append({
            "indicator": indicator_key,
            "display_name": _get_display_name(indicator_key),
            "score": score,
            "weight": round(weight * 100, 1),
            "weighted": round(weighted, 2),
            "assessment": ind_result.get("assessment", "N/A"),
        })

    result["weighted_breakdown"] = breakdown
    result["total_score"] = round(total_weighted, 2)
    result["max_possible"] = round(total_weight_used * 2, 2)

    # 按使用的权重比例调整总分（防止缺失指标拉低总分的偏误）
    if total_weight_used > 0:
        # 将总分缩放到完整权重体系下
        scaled_score = total_weighted / total_weight_used  # 满分 2.0
        result["score_pct"] = round((scaled_score + 2) / 4 * 100, 1)  # 映射到 0-100
    else:
        result["score_pct"] = 50.0

    logger.info(f"Weighted total score: {total_weighted:.2f} "
                f"(scaled: {result['score_pct']:.1f}%)")
    return result


def _get_display_name(key: str) -> str:
    """指标键名 → 中文显示名。"""
    names = {
        "pe_percentile": "PE 估值分位",
        "vix": "VIX 恐慌指数",
        "rsi": "RSI 相对强弱",
        "macd": "MACD 趋势动能",
        "ma_deviation": "均线偏离度",
        "fear_greed": "恐慌贪婪指数",
        "macro": "宏观利率",
        "dxy": "美元指数",
        "breadth": "市场宽度",
    }
    return names.get(key, key)
