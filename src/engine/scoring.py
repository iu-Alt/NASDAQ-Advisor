"""
加权评分引擎
================
汇总所有 7 个活跃指标的分数，按配置权重计算加权总分。

关键约束:
  - 核心指标 (vix, rsi, ma_deviation) 缺一即抑制信号。
    这与 config.CORE_INDICATORS 的注释一致："这些指标缺失时，
    系统不得发出增减仓信号"。
  - total_score = weighted_sum（不做除法放大）。
    缺失指标的权重直接贡献 0，让总分会因数据缺失而自然偏低。
  - 信号被抑制时 total_score 为 None，报告显示 "N/A"。
"""

import logging
from typing import Dict, List

from config import WEIGHTS, CORE_INDICATORS

logger = logging.getLogger(__name__)


def calculate_total_score(indicator_results: Dict[str, Dict]) -> Dict:
    """
    输入：所有指标计算结果的字典
    输出：
      {
        "total_score": float | None,  # None = 信号被抑制, 报告显示 N/A
        "weighted_sum": float,
        "max_possible": float,
        "coverage_weight": float,
        "weighted_breakdown": [...],
        "score_pct": float | None,
        "missing_indicators": [str, ...],
        "core_missing": list[str],    # 缺失的核心指标列表
        "signal_reliable": bool,
      }
    """
    result = {
        "total_score": None,
        "weighted_sum": 0.0,
        "max_possible": 2.0,
        "coverage_weight": 0.0,
        "weighted_breakdown": [],
        "score_pct": None,
        "missing_indicators": [],
        "core_missing": [],
        "signal_reliable": True,
    }

    breakdown = []
    total_weighted = 0.0
    total_weight_used = 0.0
    missing_core = []

    for indicator_key, weight in WEIGHTS.items():
        ind_result = indicator_results.get(indicator_key, {})

        if not ind_result or ind_result.get("score") is None:
            result["missing_indicators"].append(indicator_key)
            if indicator_key in CORE_INDICATORS:
                missing_core.append(indicator_key)
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
    result["weighted_sum"] = round(total_weighted, 2)
    result["coverage_weight"] = round(total_weight_used, 2)

    # 核心指标缺一不可
    #   — 任何一个核心指标缺失即抑制信号
    #   — 这与 config.CORE_INDICATORS 注释 "不得发出增减仓信号" 一致
    result["core_missing"] = missing_core
    if len(missing_core) > 0:
        result["signal_reliable"] = False
        logger.error(
            f"Core indicator(s) missing: {missing_core}. "
            f"Signal suppressed — config requires all core indicators present."
        )

    # 全部指标缺失时也抑制
    if total_weight_used == 0:
        result["signal_reliable"] = False
        logger.error("No indicators available. Signal suppressed.")

    # total_score = weighted_sum（不做除法）
    #   缺失指标的权重贡献 0，让总分自然偏低/偏中性。
    #   之前的 total_weighted / total_weight_used 会放大剩余信号，
    #   导致 30% 覆盖下的 0.15 变成 0.3，造成误读。
    if result["signal_reliable"]:
        result["total_score"] = round(total_weighted, 2)
        result["score_pct"] = round((total_weighted + 2) / 4 * 100, 1)
    else:
        # 信号不可靠时 total_score 为 None，报告显示 N/A
        result["total_score"] = None
        result["score_pct"] = None

    logger.info(
        f"Weighted sum: {total_weighted:.2f}, "
        f"total_score: {result['total_score']}, "
        f"coverage: {total_weight_used:.2f}, "
        f"reliable: {result['signal_reliable']}"
    )
    return result


def _get_display_name(key: str) -> str:
    """指标键名 → 中文显示名。"""
    names = {
        "vix": "VIX/VXN 波动率",
        "rsi": "RSI 相对强弱",
        "macd": "MACD 趋势动能",
        "ma_deviation": "均线偏离度",
        "fear_greed": "恐慌贪婪指数",
        "macro": "宏观利率",
        "dxy": "美元指数",
    }
    return names.get(key, key)
