"""
决策映射模块
================
将加权总分映射为具体的投资建议。

核心原则:
  - 基础定投永不暂停。模型只控制额外加仓资金的分配。
  - 所有级别都保持基础定投执行。
  - 额外资金必须来自预先限定的储备池，单月有上限。
  - 信号不可靠时 (核心指标缺失 / 数据质量差)，回退到基础定投。
"""

import logging
from typing import Dict, Optional

from config import DECISION_THRESHOLDS

logger = logging.getLogger(__name__)


def make_decision(
    scoring_result: Dict,
    indicator_results: Optional[Dict[str, Dict]] = None,
) -> Dict:
    """
    输入：scoring.calculate_total_score() 的结果
    输出：
      {
        "decision": str,        # 建议标签
        "action": str,          # 具体操作说明
        "level": str,           # level key
        "emoji": str,
        "color": str,
        "need_notify": bool,
        "total_score": float,
        "base_dca": bool,       # 基础定投是否保持 (始终 True)
        "extra_allocation_pct": float,  # 额外资金比例 (0.0 ~ 1.0)
      }
    """
    total_score = scoring_result.get("total_score")  # may be None
    score_pct = scoring_result.get("score_pct")  # may be None
    coverage_weight = scoring_result.get("coverage_weight", 1.0)
    signal_reliable = scoring_result.get("signal_reliable", True)
    indicator_results = indicator_results or {}

    result = {
        "total_score": total_score,  # None → template shows N/A
        "score_pct": score_pct,
        "coverage_weight": coverage_weight,
        "base_dca": True,
        "extra_allocation_pct": 0.0,
    }

    # 信号不可靠时回退
    if not signal_reliable:
        result.update({
            "decision": "基础定投 (信号不足)",
            "action": (
                "核心指标缺失，信号不可靠。按原计划执行基础定投，"
                "不追加额外资金。"
            ),
            "level": "maintain_dca",
            "emoji": "🟡",
            "color": "#facc15",
            "need_notify": False,
            "extra_allocation_pct": 0.0,
        })
        logger.warning("Signal unreliable, falling back to base DCA only")
        return result

    # 覆盖不足时回退
    if coverage_weight < 0.6:
        result.update({
            "decision": "基础定投 (覆盖不足)",
            "action": (
                "有效指标覆盖不足，暂不根据自动信号调整额外资金，"
                "按原计划执行基础定投。"
            ),
            "level": "maintain_dca",
            "emoji": "🟡",
            "color": "#facc15",
            "need_notify": False,
            "extra_allocation_pct": 0.0,
        })
        logger.warning(f"Insufficient data coverage: {coverage_weight:.2f}")
        return result

    # 正常决策：基础定投 + 额外资金比例
    # 安全守卫：total_score 为 None 时不应到达此处
    if total_score is None:
        logger.warning("total_score is None in decision forest, falling back")
        result.update({
            "decision": "基础定投",
            "action": "评分不可用，按原计划执行基础定投。",
            "level": "maintain_dca",
            "emoji": "🟡",
            "color": "#facc15",
            "need_notify": False,
            "extra_allocation_pct": 0.0,
        })
        return result
    if total_score >= DECISION_THRESHOLDS["aggressive_buy"]:
        result.update({
            "decision": "基础定投 + 大幅追加",
            "action": (
                "保持基础定投，额外追加 50-100% 储备资金。"
                "额外资金有单月上限，不可超过储备池余额。"
            ),
            "level": "aggressive_buy",
            "emoji": "🟢",
            "color": "#22c55e",
            "need_notify": True,
            "extra_allocation_pct": 0.75,
        })
    elif total_score >= DECISION_THRESHOLDS["increase_dca"]:
        result.update({
            "decision": "基础定投 + 适度追加",
            "action": (
                "保持基础定投，额外追加 20-50% 储备资金。"
            ),
            "level": "increase_dca",
            "emoji": "🟢",
            "color": "#4ade80",
            "need_notify": True,
            "extra_allocation_pct": 0.35,
        })
    elif total_score >= DECISION_THRESHOLDS["maintain_dca"]:
        result.update({
            "decision": "基础定投",
            "action": (
                "按原计划执行基础定投，不追加额外资金。"
                "信号中性，等待更好的入场时机。"
            ),
            "level": "maintain_dca",
            "emoji": "🟡",
            "color": "#facc15",
            "need_notify": False,
            "extra_allocation_pct": 0.0,
        })
    elif total_score >= DECISION_THRESHOLDS["reduce_extra"]:
        result.update({
            "decision": "基础定投 (暂停追加)",
            "action": (
                "保持基础定投，暂停额外资金追加。"
                "之前已追加的资金可保留，但不新增。"
            ),
            "level": "reduce_extra",
            "emoji": "🟠",
            "color": "#f97316",
            "need_notify": True,
            "extra_allocation_pct": 0.0,
        })
    else:
        result.update({
            "decision": "基础定投 (储备观望)",
            "action": (
                "保持基础定投，额外资金转入储备池。"
                "市场估值偏高或风险信号较多，等待回调后再动用储备。"
            ),
            "level": "cautious",
            "emoji": "🟠",
            "color": "#f97316",
            "need_notify": True,
            "extra_allocation_pct": 0.0,
        })

    # 趋势保护：在强上升趋势中，不在当前价位暂停额外资金
    _apply_trend_guardrail(result, indicator_results)

    logger.info(
        f"Decision: {result['decision']} (score={total_score:.2f}, "
        f"extra={result['extra_allocation_pct']:.0%}, "
        f"notify={result['need_notify']})"
    )
    return result


def _apply_trend_guardrail(
    result: Dict, indicator_results: Dict[str, Dict]
) -> None:
    """
    趋势保护：在确认的强上升趋势中，将 cautious 升级为 reduce_extra。
    基础定投始终保持，只调整额外资金建议。
    """
    if result.get("level") not in ("cautious", "reduce_extra"):
        return

    ma_result = indicator_results.get("ma_deviation", {})
    strong_uptrend = (
        bool(ma_result.get("strong_uptrend"))
        or ma_result.get("trend_regime") == "strong_uptrend"
    )
    if not strong_uptrend:
        return

    # 检查是否有多个严重风险
    severe_risks = 0
    for key, value in indicator_results.items():
        if key == "ma_deviation":
            continue
        score = value.get("score") if value else None
        if score is not None and score <= -2:
            severe_risks += 1

    if severe_risks >= 3:
        # 多项风险共振，保持 cautious
        result["action"] = (
            "保持基础定投。虽处强趋势，但估值、情绪、技术或宏观"
            "风险多项共振，额外资金保持观望。"
        )
    else:
        # 趋势健康，不需要完全停止额外资金
        if result.get("level") == "cautious":
            result.update({
                "decision": "基础定投 (趋势保护)",
                "action": (
                    "保持基础定投。趋势健康，估值偏高但不宜完全停止"
                    "额外资金。可保留小额追加 (不超过储备池 10%)。"
                ),
                "level": "reduce_extra",
                "emoji": "🟡",
                "color": "#facc15",
                "need_notify": False,
                "extra_allocation_pct": 0.1,
            })
