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
"""

import sys
import os
import logging
from datetime import datetime

# 确保项目根目录在 Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import GITHUB_PAGES_URL, REPORT_FILE

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

    # ============================================================
    # Step 2: 计算所有指标
    # ============================================================
    logger.info("[2/6] Computing indicators...")
    indicator_results = {}

    # PE 估值分位
    from src.indicators.pe_percentile import calculate_pe_percentile
    indicator_results["pe_percentile"] = calculate_pe_percentile(all_data)

    # VIX
    from src.indicators.vix import calculate_vix
    indicator_results["vix"] = calculate_vix(all_data)

    # RSI
    from src.indicators.rsi import calculate_rsi
    indicator_results["rsi"] = calculate_rsi(all_data)

    # MACD
    from src.indicators.macd import calculate_macd
    indicator_results["macd"] = calculate_macd(all_data)

    # 均线偏离度
    from src.indicators.ma_deviation import calculate_ma_deviation
    indicator_results["ma_deviation"] = calculate_ma_deviation(all_data)

    # 恐慌贪婪
    from src.indicators.fear_greed import calculate_fear_greed
    indicator_results["fear_greed"] = calculate_fear_greed(all_data)

    # 宏观利率
    from src.indicators.macro import calculate_macro
    indicator_results["macro"] = calculate_macro(all_data)

    # 美元指数
    from src.indicators.macro import calculate_dxy
    indicator_results["dxy"] = calculate_dxy(all_data)

    # 市场宽度
    from src.indicators.breadth import calculate_breadth
    indicator_results["breadth"] = calculate_breadth(all_data)

    # 打印指标摘要
    logger.info("-" * 40)
    for key, result in indicator_results.items():
        score = result.get("score", "N/A")
        logger.info(f"  {key:20s}: score={score:>3d}  | {result.get('assessment', 'N/A')}")
    logger.info("-" * 40)

    # ============================================================
    # Step 3: 加权评分
    # ============================================================
    logger.info("[3/6] Computing weighted score...")
    from src.engine.scoring import calculate_total_score
    scoring_result = calculate_total_score(indicator_results)
    logger.info(f"  Total Score: {scoring_result['total_score']:.2f} / {scoring_result['max_possible']:.1f}")

    # ============================================================
    # Step 4: 决策映射
    # ============================================================
    logger.info("[4/6] Making investment decision...")
    from src.engine.decision import make_decision
    decision_result = make_decision(scoring_result)
    logger.info(f"  Decision: {decision_result['emoji']} {decision_result['decision']}")
    logger.info(f"  Action: {decision_result['action']}")

    # ============================================================
    # Step 5: 生成 HTML 报告
    # ============================================================
    logger.info("[5/6] Generating HTML report...")
    from src.output.report import generate_report
    report_path = generate_report(all_data, indicator_results, scoring_result, decision_result)
    logger.info(f"  Report: {report_path}")

    # ============================================================
    # Step 6: 推送通知 (仅需操作时)
    # ============================================================
    logger.info("[6/6] Sending notifications...")
    report_url = GITHUB_PAGES_URL or f"file://{os.path.abspath(report_path)}"
    from src.output.notifier import send_notification
    notify_result = send_notification(decision_result, report_url)

    if notify_result["sent"]:
        logger.info(f"  Notification sent via: {', '.join(notify_result['channels'])}")
    else:
        if decision_result.get("need_notify"):
            logger.warning("  No notification channels configured, skipping push")
        else:
            logger.info("  Decision is '保持定投', no notification needed")

    # ============================================================
    # Summary
    # ============================================================
    logger.info("=" * 60)
    logger.info(f"Analysis complete at {datetime.now().isoformat()}")
    logger.info(f"Recommendation: {decision_result['emoji']} {decision_result['decision']}")
    logger.info(f"Score: {scoring_result['total_score']:.2f}/{scoring_result['max_possible']:.1f}")
    logger.info("=" * 60)

    return {
        "decision": decision_result,
        "scoring": scoring_result,
        "indicators": indicator_results,
        "report_path": report_path,
    }


if __name__ == "__main__":
    main()
