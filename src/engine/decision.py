"""
决策映射模块
================
将加权总分映射为具体的投资建议。
"""

import logging
from typing import Dict

from config import DECISION_THRESHOLDS

logger = logging.getLogger(__name__)


def make_decision(scoring_result: Dict) -> Dict:
    """
    输入：scoring.calculate_total_score() 的结果
    输出：
      {
        "decision": str,        # 建议标签
        "action": str,          # 具体操作说明
        "level": str,           # "aggressive_buy" | "increase_dca" | ... | "pause"
        "emoji": str,           # 对应 emoji
        "color": str,           # 对应颜色 hex
        "need_notify": bool,    # 是否需要推送通知
        "total_score": float,
      }
    """
    total_score = scoring_result.get("total_score", 0)
    score_pct = scoring_result.get("score_pct", 50)

    result = {
        "total_score": total_score,
        "score_pct": score_pct,
    }

    if total_score >= DECISION_THRESHOLDS["aggressive_buy"]:
        result.update({
            "decision": "大幅加仓",
            "action": "在定投基础上额外追加 50-100% 资金，抓住低估机会",
            "level": "aggressive_buy",
            "emoji": "🟢",
            "color": "#22c55e",
            "need_notify": True,
        })
    elif total_score >= DECISION_THRESHOLDS["increase_dca"]:
        result.update({
            "decision": "加大定投",
            "action": "在定投基础上追加 20-50% 资金",
            "level": "increase_dca",
            "emoji": "🟢",
            "color": "#4ade80",
            "need_notify": True,
        })
    elif total_score >= DECISION_THRESHOLDS["maintain_dca"]:
        result.update({
            "decision": "保持定投",
            "action": "按原计划执行定投，无需额外操作",
            "level": "maintain_dca",
            "emoji": "🟡",
            "color": "#facc15",
            "need_notify": False,
        })
    elif total_score >= DECISION_THRESHOLDS["reduce_dca"]:
        result.update({
            "decision": "减少定投",
            "action": "定投金额减半，保留现金等待更好时机",
            "level": "reduce_dca",
            "emoji": "🟠",
            "color": "#f97316",
            "need_notify": True,
        })
    else:
        result.update({
            "decision": "暂停观望",
            "action": "暂停定投，持有现金观望，等待市场调整后再入场",
            "level": "pause",
            "emoji": "🔴",
            "color": "#ef4444",
            "need_notify": True,
        })

    logger.info(f"Decision: {result['decision']} (score={total_score:.2f}, "
                f"notify={result['need_notify']})")
    return result
