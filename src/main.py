"""
纳指投资建议系统 — 主入口
============================
编排整个流程：
  1. 获取数据 (fetcher)
  2. 计算指标 (indicators)
  3. 汇总评分 (scoring)
  4. 生成决策 (decision)
  5. 输出报告 (report)
  6. 推送通知 (notifier)

注意：
  - 基础定投永不暂停，模型只控制额外加仓资金。
  - PE 估值和成分股宽度已暂时移除 (见 config.py 注释)。
  - 数据质量检查：模拟/过期数据会触发警告并抑制信号。
"""

import sys
import os
import logging
from datetime import datetime

# 确保项目根目录在 Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import GITHUB_PAGES_URL, REPORT_FILE, MAX_DATA_STALENESS_DAYS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nasdaq_advisor")


def main():
    logger.info("=" * 60)
    logger.info("NASDAQ-100 Investment Advisor - Starting analysis")
    logger.info("=" * 60)

    # ============================================================
    # Step 1: 获取数据
    # ============================================================
    logger.info("[1/6] Fetching all data...")
    from src.data.fetcher import fetch_all_data
    all_data = fetch_all_data()

    # ---- 数据质量检查 ----
    quality = all_data.get("data_quality", {})
    if quality.get("is_synthetic"):
        logger.critical("=" * 60)
        logger.critical("DATA QUALITY ERROR: Synthetic data detected!")
        logger.critical("The data cache contains simulated data from")
        logger.critical("generate_sample_data.py. Recommendations based on")
        logger.critical("synthetic data are NOT valid for real-money decisions.")
        logger.critical("")
        logger.critical("To fix: delete data/*.csv and re-run to download")
        logger.critical("real data from yfinance/FRED/CBOE.")
        logger.critical("=" * 60)
        # 继续执行但标记为不可靠 — 报告会显示警告
    if quality.get("issues"):
        for issue in quality["issues"]:
            logger.warning(f"Data issue: {issue}")

    # 收集数据质量问题 — 用于后续覆盖 signal_reliable
    data_quality_issues = []

    # 检查数据新鲜度 — 过期数据直接标记为信号不可靠
    data_as_of = all_data.get("data_as_of", {})
    for source, date_str in data_as_of.items():
        try:
            as_of = datetime.strptime(date_str, "%Y-%m-%d").date()
            days_ago = (datetime.now().date() - as_of).days
            if days_ago > MAX_DATA_STALENESS_DAYS:
                msg = f"Stale: {source} as_of={date_str} ({days_ago}d ago)"
                logger.warning(msg)
                data_quality_issues.append(msg)
        except (ValueError, TypeError):
            pass

    if quality.get("is_synthetic"):
        data_quality_issues.append("synthetic_data")
    if quality.get("issues"):
        data_quality_issues.extend(quality["issues"])

    # ============================================================
    # Step 2: 计算所有指标
    # ============================================================
    logger.info("[2/6] Computing indicators...")
    indicator_results = {}

    # PE 估值分位 — 仅作信息参考，不计入评分
    # (算法当前为同义反复，权重已从 WEIGHTS 中移除)
    from src.indicators.pe_percentile import calculate_pe_percentile
    indicator_results["pe_percentile"] = calculate_pe_percentile(all_data)

    # VIX / VXN — 权重 20%
    from src.indicators.vix import calculate_vix
    indicator_results["vix"] = calculate_vix(all_data)

    # RSI — 权重 15%
    from src.indicators.rsi import calculate_rsi
    indicator_results["rsi"] = calculate_rsi(all_data)

    # MACD — 权重 12%
    from src.indicators.macd import calculate_macd
    indicator_results["macd"] = calculate_macd(all_data)

    # 均线偏离度 — 权重 15%
    from src.indicators.ma_deviation import calculate_ma_deviation
    indicator_results["ma_deviation"] = calculate_ma_deviation(all_data)

    # 恐慌贪婪 — 权重 15%
    from src.indicators.fear_greed import calculate_fear_greed
    indicator_results["fear_greed"] = calculate_fear_greed(all_data)

    # 宏观利率 — 权重 15%
    from src.indicators.macro import calculate_macro
    indicator_results["macro"] = calculate_macro(all_data)

    # 美元指数 — 权重 8%
    from src.indicators.macro import calculate_dxy
    indicator_results["dxy"] = calculate_dxy(all_data)

    # 市场宽度已移除 (伪代理，与 MA 偏离度重复)
    # 真实成分股宽度待后续实现

    # 打印指标摘要
    logger.info("-" * 40)
    for key, result in indicator_results.items():
        score = result.get("score", "N/A")
        score_text = "N/A" if score is None else str(score)
        logger.info(
            f"  {key:20s}: score={score_text:>3s}  | "
            f"{result.get('assessment', 'N/A')}"
        )
    logger.info("-" * 40)

    # ============================================================
    # Step 3: 加权评分
    # ============================================================
    logger.info("[3/6] Computing weighted score...")
    from src.engine.scoring import calculate_total_score
    scoring_result = calculate_total_score(indicator_results)

    # 数据层面问题覆盖 signal_reliable
    #   — 过期 / 模拟 / 无缓存数据 → 信号不可靠
    if data_quality_issues:
        scoring_result["signal_reliable"] = False
        scoring_result["total_score"] = None
        scoring_result["score_pct"] = None
        scoring_result["data_quality_issues"] = data_quality_issues
        logger.warning(
            f"Data quality issues override signal_reliable=False: "
            f"{data_quality_issues}"
        )

    logger.info(
        f"  Total Score: {scoring_result['total_score']} / "
        f"{scoring_result['max_possible']:.1f} "
        f"(reliable: {scoring_result['signal_reliable']})"
    )

    # ============================================================
    # Step 4: 决策映射
    # ============================================================
    logger.info("[4/6] Making investment decision...")
    from src.engine.decision import make_decision
    decision_result = make_decision(scoring_result, indicator_results)
    logger.info(
        f"  Decision: {decision_result['emoji']} {decision_result['decision']}"
    )
    logger.info(f"  Action: {decision_result['action']}")
    logger.info(
        f"  Base DCA: {'✅' if decision_result.get('base_dca') else '❌'}, "
        f"Extra: {decision_result.get('extra_allocation_pct', 0):.0%}"
    )

    # 数据质量标记
    if quality.get("is_synthetic"):
        decision_result["data_warning"] = (
            "⚠️ 当前数据为模拟数据，此建议仅供测试参考，不可用于实盘决策！"
        )

    # ============================================================
    # Step 5: 生成 HTML 报告
    # ============================================================
    logger.info("[5/6] Generating HTML report...")
    from src.output.report import generate_report
    report_path = generate_report(
        all_data, indicator_results, scoring_result, decision_result
    )
    logger.info(f"  Report: {report_path}")

    # ============================================================
    # Step 6: 推送通知 (仅需操作时)
    # ============================================================
    logger.info("[6/6] Sending notifications...")
    report_url = GITHUB_PAGES_URL or f"file://{os.path.abspath(report_path)}"
    from src.output.notifier import send_notification
    notify_result = send_notification(decision_result, report_url)

    if notify_result["sent"]:
        logger.info(
            f"  Notification sent via: {', '.join(notify_result['channels'])}"
        )
    else:
        if decision_result.get("need_notify"):
            logger.warning(
                "  No notification channels configured, skipping push"
            )
        else:
            logger.info(
                "  No action needed (base DCA only), no notification required"
            )

    # ============================================================
    # Summary
    # ============================================================
    logger.info("=" * 60)
    logger.info(f"Analysis complete at {datetime.now().isoformat()}")
    logger.info(
        f"Recommendation: {decision_result['emoji']} "
        f"{decision_result['decision']}"
    )
    ts = scoring_result['total_score']
    score_str = f"{ts:.2f}" if ts is not None else "N/A"
    logger.info(
        f"Score: {score_str}/"
        f"{scoring_result['max_possible']:.1f}"
    )
    if quality.get("is_synthetic"):
        logger.warning(
            "⚠️  DATA IS SYNTHETIC — DO NOT USE FOR REAL TRADING DECISIONS"
        )
    logger.info("=" * 60)

    return {
        "decision": decision_result,
        "scoring": scoring_result,
        "indicators": indicator_results,
        "report_path": report_path,
    }


if __name__ == "__main__":
    main()
