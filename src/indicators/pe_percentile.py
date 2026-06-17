"""
PE 估值分位指标 (权重 25%)
================================
计算纳斯达克 100 当前 PE 在历史中的分位数。
多数据源策略：
  1. yfinance NDX trailingPE
  2. Nasdaq.com 官方页面
  3. QQQ ETF PE 作为代理
  4. 用价格/当前PE 缩放估算历史 PE（近似）
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional

from config import PE_PERCENTILE_THRESHOLDS, PE_LOOKBACK_YEARS

logger = logging.getLogger(__name__)


def calculate_pe_percentile(data: Dict) -> Dict:
    """
    输入：fetch_all_data() 返回的 data 字典
    输出：{"score": int, "percentile": float, "current_pe": float,
           "pe_5yr_percentile": float, "pe_10yr_percentile": float,
           "pe_alltime_percentile": float, "source": str, "assessment": str}
    """
    result = {
        "score": 0,
        "percentile": None,
        "current_pe": None,
        "pe_5yr_percentile": None,
        "pe_10yr_percentile": None,
        "pe_alltime_percentile": None,
        "source": None,
        "assessment": "无法计算",
    }

    # ---------- 第 1 步：获取当前 PE ----------
    pe_data = data.get("pe_data", {})
    current_pe = pe_data.get("current_pe")
    source = pe_data.get("source", "unknown")

    if current_pe is None or current_pe <= 0:
        logger.warning("No valid current PE found")
        result["assessment"] = "PE 数据不可用"
        return result

    result["current_pe"] = round(current_pe, 2)
    result["source"] = source

    # ---------- 第 2 步：构建历史 PE 估算序列 ----------
    # 策略：利用 NDX 历史价格 + 当前 PE + 收益增长假设来估算历史 PE
    # PE_t = Price_t / Earnings_t
    # 假设 Earnings 以恒定速率增长（约 8%/年），则：
    # Earnings_t ≈ current_Earnings × (1 - growth_rate)^(years_ago)
    # PE_t ≈ Price_t / (current_Earnings × (1 - 0.08)^(years_ago))
    #      = Price_t / current_Earnings / growth_discount

    ndx_history = data.get("ndx_history", pd.DataFrame())
    if ndx_history.empty:
        logger.warning("No NDX history for PE percentile calculation")
        result["assessment"] = "缺少历史价格数据"
        return result

    # 确保 close 列存在
    if "close" not in ndx_history.columns:
        logger.warning("NDX history missing 'close' column")
        return result

    prices = ndx_history["close"].dropna()
    # 统一去除时区 — yfinance 可能返回 tz-aware datetime
    if prices.index.tz is not None:
        prices.index = prices.index.tz_localize(None)
    if len(prices) < 252:  # 至少 1 年数据
        logger.warning(f"Not enough NDX history: {len(prices)} days")
        return result

    # 当前价格和当前收益
    latest_price = float(prices.iloc[-1])
    current_earnings = latest_price / current_pe  # E = P / PE

    # 估算历史 PE：PE_t = Price_t / Earnings_t
    # 假设收益年增长 8%（纳斯达克长期平均）
    annual_earnings_growth = 0.08

    # 计算每个历史日期距今天数
    date_diffs_years = (prices.index[-1] - prices.index).days / 365.25

    # 估算历史收益：从当前收益回推
    estimated_earnings = current_earnings * (1 + annual_earnings_growth) ** (-date_diffs_years)
    estimated_earnings = pd.Series(estimated_earnings, index=prices.index)

    # 历史 PE 估算
    estimated_pe = prices / estimated_earnings

    # 过滤异常值 (PE < 0 或 PE > 100)
    estimated_pe = estimated_pe[(estimated_pe > 0) & (estimated_pe < 100)]

    if len(estimated_pe) < 252:
        logger.warning("Not enough valid estimated PE data")
        return result

    # ---------- 第 3 步：计算各时间窗口的分位数 ----------
    now = pd.Timestamp.now()

    def calc_percentile(series, years_lookback):
        cutoff = now - pd.DateOffset(years=years_lookback)
        window = series[series.index >= cutoff]
        if len(window) < 63:  # 至少 1 季度
            return None
        # 分位数 = 有多少历史值比当前值低
        return round((window < current_pe).mean() * 100, 1)

    result["pe_alltime_percentile"] = calc_percentile(estimated_pe, 100)
    result["pe_10yr_percentile"] = calc_percentile(estimated_pe, 10)
    result["pe_5yr_percentile"] = calc_percentile(estimated_pe, 5)

    # 主分位数：优先10年，其次5年，再次全历史
    pe_percentile = result["pe_10yr_percentile"] or \
                    result["pe_5yr_percentile"] or \
                    result["pe_alltime_percentile"]

    if pe_percentile is None:
        return result

    result["percentile"] = pe_percentile

    # ---------- 第 4 步：评分 ----------
    if pe_percentile <= PE_PERCENTILE_THRESHOLDS["extremely_undervalued"]:
        result["score"] = 2
        result["assessment"] = "极度低估"
    elif pe_percentile <= PE_PERCENTILE_THRESHOLDS["undervalued"]:
        result["score"] = 1
        result["assessment"] = "偏低"
    elif pe_percentile <= PE_PERCENTILE_THRESHOLDS["fair"]:
        result["score"] = 0
        result["assessment"] = "合理"
    elif pe_percentile <= PE_PERCENTILE_THRESHOLDS["overvalued"]:
        result["score"] = -1
        result["assessment"] = "偏高"
    else:
        result["score"] = -2
        result["assessment"] = "极度高估"

    logger.info(f"PE percentile: {pe_percentile}%, score: {result['score']}, "
                f"current PE: {current_pe}, assessment: {result['assessment']}")
    return result
