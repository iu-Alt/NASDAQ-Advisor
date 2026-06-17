"""
数据获取层 — 统一封装所有数据源
=================================
- yfinance: NDX 价格, VIX, DXY, QQQ PE, NDX 成分股
- FRED API: 利率、利差
- CNN 网页: 恐慌贪婪指数
- Nasdaq.com: PE 历史 (补充)
"""

import time
import logging
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

import yfinance as yf
from bs4 import BeautifulSoup

from config import (
    FRED_API_KEY, FRED_SERIES,
    CACHE_NDX_HISTORY, CACHE_PE_HISTORY,
    CACHE_VIX_HISTORY, CACHE_DXY_HISTORY,
)
from .store import (
    load_cache, save_cache, update_cache,
    get_missing_range, get_ndx_history, get_vix_history,
)

logger = logging.getLogger(__name__)

# 全局速率控制
_RATE_LIMIT_DELAY = 5.0  # yfinance 调用间隔 (秒) — 避免限流
_last_yf_call = 0.0


def _create_yf_session() -> requests.Session:
    """创建带浏览器 User-Agent 的 requests session，减少限流概率。"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session


def _rate_limit():
    """确保 yfinance API 调用间隔足够长，避免限流。"""
    global _last_yf_call
    now = time.time()
    elapsed = now - _last_yf_call
    if elapsed < _RATE_LIMIT_DELAY:
        wait = _RATE_LIMIT_DELAY - elapsed
        logger.debug(f"Rate limit: waiting {wait:.1f}s...")
        time.sleep(wait)
    _last_yf_call = time.time()


# ============================================================
# 通用工具
# ============================================================

def _safe_yf_download(ticker: str, start: str, end: str,
                      interval: str = "1d") -> pd.DataFrame:
    """
    安全地从 Yahoo Finance 下载数据，带重试和速率控制。
    优先使用 Ticker.history() 方法。
    返回标准化的 DataFrame (Date index, Close column)。
    """
    for attempt in range(4):
        try:
            _rate_limit()
            # 使用 Ticker API (比 download 更稳定)
            t = yf.Ticker(ticker)
            df = t.history(start=start, end=end, interval=interval,
                           auto_adjust=True)
            if df is not None and not df.empty:
                # 标准化列名
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.columns = [c.lower().replace(" ", "_") for c in df.columns]
                return df
        except Exception as e:
            err_msg = str(e)
            if "rate limit" in err_msg.lower() or "too many" in err_msg.lower():
                wait = min(60, 10 * (2 ** attempt))
                logger.warning(f"Rate limited for {ticker}, "
                               f"waiting {wait}s before retry {attempt + 1}/4...")
                time.sleep(wait)
            else:
                logger.warning(f"yfinance download attempt {attempt + 1}/4 failed "
                               f"for {ticker}: {e}")
                time.sleep(3 + attempt * 2)
    logger.error(f"Failed to download {ticker} after 4 attempts")
    return pd.DataFrame()


def _safe_fred_request(series_id: str) -> Optional[pd.Series]:
    """
    从 FRED API 获取单个时间序列。
    返回 Series (date index) 或 None。
    """
    if not FRED_API_KEY:
        logger.warning("FRED_API_KEY not set, skipping FRED data")
        return None

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 500,  # 足够覆盖多年
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        observations = data.get("observations", [])
        dates, values = [], []
        for obs in observations:
            if obs["value"] == ".":
                continue
            try:
                dates.append(pd.Timestamp(obs["date"]))
                values.append(float(obs["value"]))
            except (ValueError, KeyError):
                continue
        return pd.Series(values, index=dates, name=series_id).sort_index()
    except Exception as e:
        logger.error(f"FRED request failed for {series_id}: {e}")
        return None


# ============================================================
# NDX 核心价格数据
# ============================================================

def fetch_ndx_history(lookback_years: int = 10) -> pd.DataFrame:
    """
    获取纳斯达克 100 指数历史价格数据。
    优先增量更新缓存，减少 API 调用。
    """
    start, end = get_missing_range(CACHE_NDX_HISTORY, lookback_years * 365)

    # 获取现有缓存
    existing = get_ndx_history()

    if start is None:
        logger.info("NDX history cache is up to date")
        return existing

    # 有缓存则增量更新，无缓存则全量获取
    if existing.empty:
        logger.info(f"Fetching full NDX history from {start} to {end}")
    else:
        logger.info(f"Fetching incremental NDX data from {start} to {end}")

    new_df = _safe_yf_download("^NDX", start, end)
    if new_df.empty:
        logger.warning("No new NDX data, returning existing cache")
        return existing

    if existing.empty:
        save_cache(new_df, CACHE_NDX_HISTORY)
        return new_df

    # 合并缓存
    combined = update_cache(CACHE_NDX_HISTORY, new_df)
    return combined


def fetch_ndx_current() -> Dict:
    """获取 NDX 最新的关键数据点。失败时从缓存历史数据推算。"""
    try:
        _rate_limit()
        ndx = yf.Ticker("^NDX")
        info = ndx.info
        fast_info = ndx.fast_info

        # 近两日数据计算涨跌幅
        hist = ndx.history(period="5d", auto_adjust=True)
        if len(hist) >= 2:
            latest_close = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2])
            change_pct = round((latest_close - prev_close) / prev_close * 100, 2)
            change_val = round(latest_close - prev_close, 2)
        else:
            latest_close = float(fast_info.get("lastPrice", 0) or info.get("regularMarketPrice", 0))
            prev_close = float(fast_info.get("previousClose", 0) or info.get("regularMarketPreviousClose", 0))
            change_pct = round((latest_close - prev_close) / prev_close * 100, 2) if prev_close else 0
            change_val = round(latest_close - prev_close, 2)

        return {
            "price": latest_close,
            "prev_close": prev_close,
            "change_pct": change_pct,
            "change_val": change_val,
            "52w_high": float(info.get("fiftyTwoWeekHigh", 0) or 0),
            "52w_low": float(info.get("fiftyTwoWeekLow", 0) or 0),
            "name": info.get("shortName", "NASDAQ-100"),
            "source": "live",
        }
    except Exception as e:
        logger.warning(f"Failed to fetch NDX current data: {e}, "
                       f"falling back to cache")

    # 回退：从缓存历史数据提取
    cached = get_ndx_history()
    if not cached.empty and "close" in cached.columns:
        closes = cached["close"].dropna()
        if len(closes) >= 2:
            latest = float(closes.iloc[-1])
            prev = float(closes.iloc[-2])
            high52 = float(closes.tail(252).max()) if len(closes) >= 252 else latest
            low52 = float(closes.tail(252).min()) if len(closes) >= 252 else latest
            return {
                "price": round(latest, 2),
                "prev_close": round(prev, 2),
                "change_pct": round((latest - prev) / prev * 100, 2),
                "change_val": round(latest - prev, 2),
                "52w_high": round(high52, 2),
                "52w_low": round(low52, 2),
                "name": "NASDAQ-100 (cached)",
                "source": "cache",
            }
    return {}


# ============================================================
# PE 估值数据 (多源)
# ============================================================

def fetch_pe_from_yfinance(ticker: str = "^NDX") -> Optional[float]:
    """从 yfinance 获取当前 PE (trailing PE)。"""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        pe = info.get("trailingPE") or info.get("forwardPE")
        if pe:
            return float(pe)
    except Exception as e:
        logger.warning(f"yfinance PE fetch failed for {ticker}: {e}")
    return None


def fetch_qqq_pe_history(lookback_years: int = 10) -> pd.DataFrame:
    """
    从 QQQ ETF 获取 PE 历史数据作为代理。
    ETF 自身不直接报告 PE，但 yfinance 可能提供。
    备选方案：使用 NASDAQ 官方数据。
    """
    start = (datetime.now() - timedelta(days=lookback_years * 365)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")

    try:
        qqq = yf.Ticker("QQQ")
        # 尝试获取季度 PE 数据（如果可用）
        info = qqq.info
        current_pe = info.get("trailingPE")

        # 下载 QQQ 历史价格作为 fallback 对比
        hist = _safe_yf_download("QQQ", start, end)
        if hist.empty:
            return pd.DataFrame()

        # 构造近似 PE 历史：用价格比例 × 当前 PE 估算
        if current_pe and not hist.empty:
            latest_price = float(hist["close"].iloc[-1])
            hist["estimated_pe"] = hist["close"] / latest_price * current_pe
            hist["pe_source"] = "qqq_estimated"
            return hist[["close", "estimated_pe", "pe_source"]]

        return hist
    except Exception as e:
        logger.warning(f"QQQ PE history fetch failed: {e}")
        return pd.DataFrame()


def fetch_nasdaq_pe_page() -> Optional[float]:
    """
    从 Nasdaq.com 抓取 NDX 的当前 PE。
    页面 URL: https://www.nasdaq.com/market-activity/index/ndx
    """
    url = "https://www.nasdaq.com/market-activity/index/ndx"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # 尝试查找 PE 相关数据
        # Nasdaq 页面结构可能变化，这里是常见模式
        for elem in soup.select("[class*='table'] td, [class*='data'] span"):
            text = elem.get_text(strip=True)
            if "P/E" in text or "Price/Earnings" in text:
                # 尝试从相邻元素提取数字
                parent = elem.parent
                if parent:
                    for child in parent.find_all(["td", "span"]):
                        val = child.get_text(strip=True)
                        try:
                            return float(val.replace(",", ""))
                        except ValueError:
                            continue
    except Exception as e:
        logger.warning(f"Nasdaq.com PE scrape failed: {e}")
    return None


def fetch_ndx_pe_data() -> Dict:
    """
    多源获取 NDX PE 数据，合并比对待。
    返回包含 current_pe、source 等字段的字典。
    """
    results = {
        "current_pe": None,
        "source": None,
        "pe_yfinance": None,
        "pe_nasdaq_web": None,
    }

    # 1. yfinance
    pe_yf = fetch_pe_from_yfinance("^NDX")
    results["pe_yfinance"] = pe_yf

    # 2. Nasdaq 官网
    pe_nasdaq = fetch_nasdaq_pe_page()
    results["pe_nasdaq_web"] = pe_nasdaq

    # 3. QQQ PE (ETF 代理)
    pe_qqq = fetch_pe_from_yfinance("QQQ")
    results["pe_qqq_etf"] = pe_qqq

    # 优先级：Nasdaq 官网 > yfinance NDX > QQQ ETF
    for pe_val in [pe_nasdaq, pe_yf, pe_qqq]:
        if pe_val and pe_val > 0:
            results["current_pe"] = pe_val
            if pe_val == pe_nasdaq:
                results["source"] = "nasdaq.com"
            elif pe_val == pe_yf:
                results["source"] = "yfinance_ndx"
            else:
                results["source"] = "yfinance_qqq_etf"
            break

    # 回退：使用 NDX 历史数据的近似 PE (基于长期均值)
    if results["current_pe"] is None:
        cached = get_ndx_history()
        if not cached.empty and "close" in cached.columns:
            # 纳斯达克 100 长期 PE 大约在 20-35 之间，取中间值 28 作为回退
            results["current_pe"] = 28.0
            results["source"] = "fallback_estimate"
            results["pe_fallback"] = True
            logger.warning("Using fallback PE estimate: 28.0")

    return results


# ============================================================
# VIX 恐慌指数
# ============================================================

def fetch_vix_history(lookback_years: int = 5) -> pd.DataFrame:
    """获取 VIX 历史数据。"""
    start, end = get_missing_range(CACHE_VIX_HISTORY, lookback_years * 365)
    existing = get_vix_history()

    if start is None:
        logger.info("VIX history cache is up to date")
        return existing

    new_df = _safe_yf_download("^VIX", start, end)
    if new_df.empty:
        return existing

    if existing.empty:
        save_cache(new_df, CACHE_VIX_HISTORY)
        return new_df

    return update_cache(CACHE_VIX_HISTORY, new_df)


def fetch_vix_current() -> Optional[float]:
    """获取 VIX 当前值。失败时从缓存提取。"""
    try:
        _rate_limit()
        vix = yf.Ticker("^VIX")
        fast_info = vix.fast_info
        val = float(fast_info.get("lastPrice", 0) or vix.info.get("regularMarketPrice", 0))
        if val > 0:
            return val
    except Exception as e:
        logger.warning(f"Failed to fetch VIX live: {e}, falling back to cache")

    # 回退：从缓存历史提取最新值
    cached = get_vix_history()
    if not cached.empty and "close" in cached.columns:
        closes = cached["close"].dropna()
        if len(closes) > 0:
            return round(float(closes.iloc[-1]), 2)
    return None


# ============================================================
# 恐慌贪婪指数 (CNN)
# ============================================================

def fetch_fear_greed_index() -> Optional[Dict]:
    """
    从 CNN 获取 Fear & Greed Index。
    备选：用替代指标自行计算。

    Returns:
        {"value": int, "rating": str, "timestamp": str} 或 None
    """
    # CNN 的 API 端点 (非官方但稳定)
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "fear_and_greed" in data:
            fg = data["fear_and_greed"]
            return {
                "value": int(fg["score"]),
                "rating": fg["rating"],
                "timestamp": fg.get("timestamp", datetime.now().isoformat()),
            }
    except Exception as e:
        logger.warning(f"CNN Fear & Greed API failed: {e}")

    # Fallback: 尝试从网页解析
    try:
        web_url = "https://www.cnn.com/markets/fear-and-greed"
        resp = requests.get(web_url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")
        # 尝试多种可能的 CSS 选择器
        score_elem = soup.select_one("[class*='market-fng-gauge']") or \
                     soup.select_one("[class*='fear-and-greed']")
        if score_elem:
            text = score_elem.get_text()
            import re
            match = re.search(r'(\d+)', text)
            if match:
                score = int(match.group(1))
                if 0 <= score <= 100:
                    rating = "Extreme Fear" if score <= 25 else \
                             "Fear" if score <= 45 else \
                             "Neutral" if score <= 55 else \
                             "Greed" if score <= 75 else "Extreme Greed"
                    return {"value": score, "rating": rating,
                            "timestamp": datetime.now().isoformat(),
                            "source": "cnn_scrape"}
    except Exception as e:
        logger.warning(f"CNN Fear & Greed scrape fallback failed: {e}")

    return None


# ============================================================
# 宏观利率数据 (FRED)
# ============================================================

def fetch_macro_data() -> Dict:
    """
    从 FRED 获取宏观利率数据。
    返回联邦基金利率、10Y/2Y 收益率及利差。
    """
    result = {
        "fed_funds_rate": None,
        "yield_10y": None,
        "yield_2y": None,
        "spread_10y_2y": None,
        "rate_trend": None,  # "cutting", "holding", "hiking"
    }

    # 优先获取直接利差序列
    spread_series = _safe_fred_request("T10Y2Y")
    if spread_series is not None and not spread_series.empty:
        result["spread_10y_2y"] = float(spread_series.iloc[-1])

    # 10Y
    dgs10 = _safe_fred_request("DGS10")
    if dgs10 is not None and not dgs10.empty:
        result["yield_10y"] = float(dgs10.iloc[-1])

    # 2Y
    dgs2 = _safe_fred_request("DGS2")
    if dgs2 is not None and not dgs2.empty:
        result["yield_2y"] = float(dgs2.iloc[-1])

    # 如果直接利差不可用，自己算
    if result["spread_10y_2y"] is None and \
       result["yield_10y"] is not None and result["yield_2y"] is not None:
        result["spread_10y_2y"] = round(result["yield_10y"] - result["yield_2y"], 4)

    # 联邦基金利率
    dff = _safe_fred_request("DFF")
    if dff is not None and not dff.empty:
        result["fed_funds_rate"] = float(dff.iloc[-1])

        # 判断利率趋势：比较近 3 个月均值
        cutoff = dff.index[-1] - pd.Timedelta(days=90)
        recent = dff[dff.index >= cutoff]
        older = dff[(dff.index < cutoff) & (dff.index >= cutoff - pd.Timedelta(days=90))]
        if not recent.empty and not older.empty:
            recent_mean = recent.mean()
            older_mean = older.mean()
            diff = recent_mean - older_mean
            if diff < -0.15:
                result["rate_trend"] = "cutting"
            elif diff > 0.15:
                result["rate_trend"] = "hiking"
            else:
                result["rate_trend"] = "holding"

    return result


# ============================================================
# 美元指数 DXY
# ============================================================

def fetch_dxy_data(lookback_years: int = 5) -> pd.DataFrame:
    """获取美元指数历史数据。优先使用缓存，失败时返回缓存数据。"""
    # 先检查缓存
    cached = load_cache(CACHE_DXY_HISTORY)
    if not cached.empty:
        logger.info("Using cached DXY data")
        return cached

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=lookback_years * 365)).strftime("%Y-%m-%d")

    # 尝试 DX-Y.NYB
    df = _safe_yf_download("DX-Y.NYB", start, end)
    if not df.empty:
        save_cache(df, CACHE_DXY_HISTORY)
        return df

    # Fallback: UUP ETF
    df = _safe_yf_download("UUP", start, end)
    if not df.empty:
        save_cache(df, CACHE_DXY_HISTORY)
    return df


# ============================================================
# NDX 成分股数据 (市场宽度)
# ============================================================

# NDX 前 20 大权重股 (作为成分股代理，yfinance 获取完整成分列表有局限)
NDX_TOP_COMPONENTS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG",
    "TSLA", "AVGO", "COST", "NFLX", "AMD", "PEP", "ADBE", "CSCO",
    "TMUS", "INTU", "TXN", "QCOM", "AMGN", "HON", "CMCSA", "AMAT",
    "ISRG", "LRCX", "MU", "INTC", "BKNG", "ADI", "REGN", "VRTX",
    "KLAC", "PANW", "ADP", "GILD", "SBUX", "SNPS", "CDNS", "MELI",
    "MDLZ", "ASML", "ABNB", "MRVL", "CTAS", "MAR", "ORLY", "CRWD",
    "FTNT", "DASH", "DDOG", "ZS", "TEAM", "WDAY", "MDB", "PDD",
    "AZN", "CEG", "CCEP", "KDP", "ODFL", "DXCM", "IDXX", "TTD",
    "PAYX", "MNST", "ROST", "FAST", "BIIB", "EXC", "GEHC", "KHC",
    "XEL", "MCHP", "LULU", "PCAR", "CTSH", "CSGP", "EA", "FANG",
    "BKR", "VRSK", "ANSS", "CDW", "CHTR", "CINF", "CPRT", "DLTR",
    "EBAY", "ENPH", "FISV", "ILMN", "JD", "LCID", "NTES", "NXPI",
    "ON", "SGEN", "SIRI", "SPLK", "SWKS", "TTWO", "WBA", "WBD",
    "ZM", "ZSG",
]

# 更全的 NDX 成分股列表 (2024 年)
NDX_FULL_COMPONENTS = NDX_TOP_COMPONENTS  # yfinance 限制，用主要成分股


def fetch_ndx_breadth_data(hist_df: pd.DataFrame) -> Dict:
    """
    计算市场宽度：获取 NDX 主要成分股，计算高于 MA50 的比例。
    使用代表性的前 15 只成分股（减少调用量），带速率控制。
    如果前几只就遇到限流，直接返回回退值。
    """
    components = NDX_FULL_COMPONENTS[:15]
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    above_ma50_counts = []
    rate_limited = False

    for symbol in components:
        try:
            _rate_limit()
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start, end=end, auto_adjust=True)
            if hist.empty or len(hist) < 50:
                continue
            ma50 = hist["Close"].rolling(window=50).mean()
            latest_close = float(hist["Close"].iloc[-1])
            latest_ma50 = float(ma50.iloc[-1])
            if pd.notna(latest_ma50) and latest_ma50 > 0:
                above_ma50_counts.append(1 if latest_close > latest_ma50 else 0)
        except Exception as e:
            if "rate limit" in str(e).lower() or "too many" in str(e).lower():
                rate_limited = True
                break
            continue

    total = len(above_ma50_counts)
    above = sum(above_ma50_counts)
    pct_above_ma50 = round(above / total * 100, 1) if total > 0 else None

    # 如果数据不足或被限流，使用基于 NDX 自身价格与 MA50 关系的近似
    if pct_above_ma50 is None or total < 5:
        if not hist_df.empty and "close" in hist_df.columns:
            closes = hist_df["close"].dropna()
            if len(closes) >= 50:
                ndx_ma50 = float(closes.iloc[-50:].mean())
                ndx_price = float(closes.iloc[-1])
                # 粗略近似：NDX 自身在 MA50 上方 → 假定约 55% 的成分股也在上方
                is_above = ndx_price > ndx_ma50
                pct_above_ma50 = 55.0 if is_above else 40.0
                total = 0  # 标记为近似值
                above = 0
                logger.info(f"Using NDX-based breadth estimate: {pct_above_ma50}%")

    return {
        "pct_above_ma50": pct_above_ma50,
        "stocks_checked": total,
        "stocks_above_ma50": above,
    }


# ============================================================
# 综合数据获取 (一次性拉取所有数据)
# ============================================================

def fetch_all_data() -> Dict:
    """
    主入口：一次性获取所有所需数据。
    返回一个包含所有原始数据的字典，供各指标模块使用。
    """
    logger.info("=" * 60)
    logger.info(f"Starting data fetch at {datetime.now().isoformat()}")
    logger.info("=" * 60)

    data = {
        "timestamp": datetime.now().isoformat(),
        "fetch_date": datetime.now().strftime("%Y-%m-%d"),
    }

    # 1. NDX 历史价格
    logger.info("Fetching NDX history...")
    data["ndx_history"] = fetch_ndx_history(lookback_years=10)

    # 2. NDX 当前数据
    logger.info("Fetching NDX current data...")
    data["ndx_current"] = fetch_ndx_current()

    # 3. PE 数据
    logger.info("Fetching PE data...")
    data["pe_data"] = fetch_ndx_pe_data()

    # 4. VIX
    logger.info("Fetching VIX data...")
    data["vix_history"] = fetch_vix_history(lookback_years=5)
    data["vix_current"] = fetch_vix_current()

    # 5. Fear & Greed
    logger.info("Fetching Fear & Greed index...")
    data["fear_greed"] = fetch_fear_greed_index()

    # 6. 宏观利率
    logger.info("Fetching macro data (FRED)...")
    data["macro"] = fetch_macro_data()

    # 7. DXY
    logger.info("Fetching DXY data...")
    data["dxy_history"] = fetch_dxy_data(lookback_years=2)

    # 8. 市场宽度
    logger.info("Fetching market breadth data...")
    hist_df = data.get("ndx_history", pd.DataFrame())
    data["breadth"] = fetch_ndx_breadth_data(hist_df)

    logger.info("Data fetch complete.")
    return data
