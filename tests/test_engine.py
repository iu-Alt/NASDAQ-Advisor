"""测试引擎和决策模块 — 匹配 2026-07-10 修订后的权重与约束。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config import WEIGHTS, CORE_INDICATORS
from src.engine.decision import make_decision
from src.engine.scoring import calculate_total_score


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _full_scores(score):
    """所有 7 个活跃指标设为同一分数。"""
    return {key: {"score": score, "assessment": "test"} for key in WEIGHTS}


def _scores_except(missing_keys):
    """除指定指标外全设为 +2。"""
    scores = {key: {"score": 2, "assessment": "test"} for key in WEIGHTS}
    for k in missing_keys:
        scores[k] = {"score": None, "assessment": "missing"}
    return scores


def _decision(score, reliable=True, coverage=1.0):
    return make_decision({
        "total_score": score,
        "score_pct": 50,
        "coverage_weight": coverage,
        "signal_reliable": reliable,
    })


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

class ScoringTests(unittest.TestCase):
    """加权评分引擎。"""

    # -- total_score = weighted_sum (不做除法放大) --

    def test_total_score_equals_weighted_sum_when_all_present(self):
        """7 个指标全部 +2 → weighted_sum = 2.0, total_score = 2.0。"""
        result = calculate_total_score(_full_scores(2))
        self.assertAlmostEqual(result["weighted_sum"], 2.0)
        self.assertAlmostEqual(result["total_score"], 2.0)
        self.assertTrue(result["signal_reliable"])

    def test_missing_noncore_does_not_amplify(self):
        """缺失非核心指标 fear_greed (0.15) 时 total_score 不放大。"""
        scores = _full_scores(2)
        scores["fear_greed"] = {"score": None, "assessment": "missing"}
        result = calculate_total_score(scores)
        # weighted_sum = 2.0 - 2*0.15 = 1.70
        self.assertAlmostEqual(result["weighted_sum"], 1.70)
        # total_score = weighted_sum (不做除法)
        self.assertAlmostEqual(result["total_score"], 1.70)
        self.assertTrue(result["signal_reliable"])

    def test_missing_noncore_shrinks_naturally(self):
        """缺失非核心指标时得分自然偏低（不放大）。"""
        scores = _full_scores(0)
        scores["dxy"] = {"score": None, "assessment": "missing"}
        result = calculate_total_score(scores)
        # weighted_sum = 0 - 0*0.08 = 0.0
        self.assertAlmostEqual(result["total_score"], 0.0)

    # -- 核心指标门控 --

    def test_single_core_missing_suppresses_signal(self):
        """任一核心指标缺失 → signal_reliable=False。"""
        result = calculate_total_score(_scores_except(["vix"]))
        self.assertFalse(result["signal_reliable"])
        self.assertIsNone(result["total_score"])
        self.assertIn("vix", result["core_missing"])

    def test_two_core_missing_suppresses_signal(self):
        """两个核心指标缺失 → signal_reliable=False。"""
        result = calculate_total_score(_scores_except(["vix", "rsi"]))
        self.assertFalse(result["signal_reliable"])
        self.assertIsNone(result["total_score"])

    def test_all_core_missing_suppresses_signal(self):
        """三个核心指标全缺 → signal_reliable=False。"""
        result = calculate_total_score(_scores_except(CORE_INDICATORS))
        self.assertFalse(result["signal_reliable"])
        self.assertIsNone(result["total_score"])

    def test_all_cores_present_signal_reliable(self):
        """所有核心指标有效 → signal_reliable=True。"""
        # 仅缺失非核心 (dxy)
        result = calculate_total_score(_scores_except(["dxy"]))
        self.assertTrue(result["signal_reliable"])
        self.assertIsNotNone(result["total_score"])

    # -- 全部缺失 --

    def test_all_missing_suppresses_signal(self):
        result = calculate_total_score({})
        self.assertFalse(result["signal_reliable"])
        self.assertIsNone(result["total_score"])
        self.assertEqual(result["coverage_weight"], 0.0)

    # -- 缺失指标记录 --

    def test_missing_indicators_tracked(self):
        result = calculate_total_score(_scores_except(["vix", "dxy"]))
        self.assertIn("vix", result["missing_indicators"])
        self.assertIn("dxy", result["missing_indicators"])

    # -- PE 已不在权重中 --

    def test_pe_weight_removed(self):
        self.assertNotIn("pe_percentile", WEIGHTS)

    # -- breadth 已不在权重中 --

    def test_breadth_weight_removed(self):
        self.assertNotIn("breadth", WEIGHTS)


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

class DecisionTests(unittest.TestCase):
    """决策映射。"""

    # -- 阈值 --

    def test_aggressive_buy(self):
        r = _decision(1.2)
        self.assertEqual(r["level"], "aggressive_buy")
        self.assertTrue(r["base_dca"])
        self.assertGreater(r["extra_allocation_pct"], 0)

    def test_increase_dca(self):
        r = _decision(0.4)
        self.assertEqual(r["level"], "increase_dca")
        self.assertTrue(r["base_dca"])

    def test_maintain_dca(self):
        r = _decision(-0.4)
        self.assertEqual(r["level"], "maintain_dca")
        self.assertTrue(r["base_dca"])
        self.assertEqual(r["extra_allocation_pct"], 0.0)

    def test_reduce_extra(self):
        r = _decision(-1.2)
        self.assertEqual(r["level"], "reduce_extra")
        self.assertTrue(r["base_dca"])

    def test_cautious(self):
        r = _decision(-1.21)
        self.assertEqual(r["level"], "cautious")
        self.assertTrue(r["base_dca"])

    # -- 旧决策名已消除 --

    def test_pause_no_longer_exists(self):
        """基础定投永不暂停 — 最差为 cautious。"""
        r = _decision(-2.0)
        self.assertNotEqual(r["level"], "pause")
        self.assertEqual(r["level"], "cautious")

    def test_reduce_dca_no_longer_exists(self):
        """旧 reduce_dca 被 reduce_extra 替代。"""
        r = _decision(-1.2)
        self.assertNotEqual(r["level"], "reduce_dca")
        self.assertEqual(r["level"], "reduce_extra")

    # -- 信号不可靠 --

    def test_unreliable_signal_returns_base_dca(self):
        r = _decision(2.0, reliable=False)
        self.assertEqual(r["level"], "maintain_dca")
        self.assertEqual(r["extra_allocation_pct"], 0.0)
        self.assertTrue(r["base_dca"])

    def test_total_score_none_with_reliable_false(self):
        """signal_reliable=False 时 total_score=None 也能正确处理。"""
        r = make_decision({
            "total_score": None,
            "score_pct": None,
            "coverage_weight": 0.3,
            "signal_reliable": False,
        })
        self.assertEqual(r["level"], "maintain_dca")
        self.assertIsNone(r["total_score"])

    # -- 低覆盖 --

    def test_low_coverage_returns_base_dca(self):
        r = _decision(2.0, coverage=0.5)
        self.assertEqual(r["level"], "maintain_dca")
        self.assertTrue(r["base_dca"])

    # -- 趋势保护 --

    def test_strong_uptrend_softens_cautious(self):
        """强上升趋势中 cautious → reduce_extra（趋势保护）。"""
        r = make_decision(
            {
                "total_score": -1.5,
                "score_pct": 12.5,
                "coverage_weight": 1.0,
                "signal_reliable": True,
            },
            {
                "ma_deviation": {
                    "score": 1,
                    "strong_uptrend": True,
                    "trend_regime": "strong_uptrend",
                },
                "vix": {"score": 0},
                "rsi": {"score": -2},  # -2 算严重风险
            },
        )
        # 强趋势 + 不够 3 个严重风险 → 应该从 cautious 升级到 reduce_extra
        self.assertEqual(r["level"], "reduce_extra")
        self.assertGreater(r["extra_allocation_pct"], 0)

    def test_strong_uptrend_with_many_severe_risks_stays_cautious(self):
        """强趋势但 ≥3 个严重风险 → 保持 cautious。"""
        r = make_decision(
            {
                "total_score": -1.5,
                "score_pct": 12.5,
                "coverage_weight": 1.0,
                "signal_reliable": True,
            },
            {
                "ma_deviation": {
                    "score": 1,
                    "strong_uptrend": True,
                    "trend_regime": "strong_uptrend",
                },
                "vix": {"score": -2},
                "rsi": {"score": -2},
                "macd": {"score": -2},
                "fear_greed": {"score": 0},
            },
        )
        self.assertEqual(r["level"], "cautious")


if __name__ == "__main__":
    unittest.main()
