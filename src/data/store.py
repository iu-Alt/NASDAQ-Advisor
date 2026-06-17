"""
数据存储层 — 本地 CSV 缓存的读写操作
======================================
将历史数据缓存到本地，减少 API 调用。
支持增量更新：只获取本地缺失的日期范围。
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from config import (
    CACHE_NDX_HISTORY, CACHE_PE_HISTORY,
    CACHE_VIX_HISTORY, CACHE_DXY_HISTORY, DATA_DIR
)


def ensure_data_dir():
    """确保数据目录存在。"""
    os.makedirs(DATA_DIR, exist_ok=True)


def load_cache(filepath: str, date_col: str = "Date") -> pd.DataFrame:
    """
    加载本地缓存 CSV，返回 DataFrame。
    如果缓存不存在，返回空 DataFrame。
    """
    ensure_data_dir()
    if os.path.exists(filepath):
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col])
        # 确保 index 是 tz-naive (yfinance 可能返回 tz-aware)
        if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df
    return pd.DataFrame()


def save_cache(df: pd.DataFrame, filepath: str):
    """将 DataFrame 保存为 CSV 缓存。"""
    ensure_data_dir()
    df.to_csv(filepath)


def get_missing_range(filepath: str, lookback_days: int = 365 * 5) -> tuple:
    """
    检查本地缓存的最新日期，返回需要从 API 获取的日期范围。

    Returns:
        (start_date: str, end_date: str) 或 (None, None) 如果不需要更新
    """
    df = load_cache(filepath)
    end_date = datetime.now()

    if df.empty:
        start_date = end_date - timedelta(days=lookback_days)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 假设 index 是日期
    if isinstance(df.index, pd.DatetimeIndex):
        last_date = df.index.max()
    else:
        last_date = end_date - timedelta(days=lookback_days)

    # 如果最后数据是昨天或更早，需要更新
    if last_date.date() < end_date.date() - timedelta(days=1):
        start_date = (last_date - timedelta(days=5)).strftime("%Y-%m-%d")
        return start_date, end_date.strftime("%Y-%m-%d")

    return None, None


def update_cache(filepath: str, new_df: pd.DataFrame, date_col: str = "Date") -> pd.DataFrame:
    """
    将新数据合并到缓存中，去重后保存。
    返回合并后的完整 DataFrame。
    """
    existing = load_cache(filepath)

    if existing.empty:
        save_cache(new_df, filepath)
        return new_df

    # 合并并去重（基于日期索引）
    if isinstance(existing.index, pd.DatetimeIndex) and isinstance(new_df.index, pd.DatetimeIndex):
        combined = pd.concat([existing, new_df])
        combined = combined[~combined.index.duplicated(keep='last')]
        combined = combined.sort_index()
    else:
        combined = new_df

    save_cache(combined, filepath)
    return combined


def get_ndx_history() -> pd.DataFrame:
    """获取缓存的 NDX 历史价格数据。"""
    df = load_cache(CACHE_NDX_HISTORY)
    if not df.empty and not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date")
    return df


def get_vix_history() -> pd.DataFrame:
    """获取缓存的 VIX 历史数据。"""
    df = load_cache(CACHE_VIX_HISTORY)
    if not df.empty and not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date")
    return df


def get_pe_history() -> pd.DataFrame:
    """获取缓存的 PE 历史数据。"""
    df = load_cache(CACHE_PE_HISTORY)
    return df
