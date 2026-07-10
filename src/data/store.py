"""
数据存储层 — 本地 CSV 缓存的读写操作
======================================
将历史数据缓存到本地，减少 API 调用。
支持增量更新：只获取本地缺失的日期范围。

日期处理：
  - yfinance 的 end 参数是排他的 (exclusive)，因此传入 tomorrow
    才能获取到今天的数据。
  - 缓存更新检查使用交易日历近似 (跳过周末)。
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
from config import (
    CACHE_NDX_HISTORY, CACHE_PE_HISTORY,
    CACHE_VIX_HISTORY, CACHE_DXY_HISTORY, DATA_DIR
)


def ensure_data_dir():
    """确保数据目录存在。"""
    os.makedirs(DATA_DIR, exist_ok=True)


def _provenance_path(filepath: str) -> str:
    """返回给定 CSV 缓存文件的溯源 JSON 路径。"""
    return filepath.replace(".csv", "_provenance.json")


def load_cache(filepath: str, date_col: str = "Date") -> pd.DataFrame:
    """
    加载本地缓存 CSV，返回 DataFrame。
    如果缓存不存在，返回空 DataFrame。
    同时加载并附加 provenance 元数据到 df.attrs。
    """
    ensure_data_dir()
    if os.path.exists(filepath):
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col])
        # 确保 index 是 tz-naive
        if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        # 加载溯源元数据
        prov = load_provenance(filepath)
        if prov:
            df.attrs["provenance"] = prov
        return df
    return pd.DataFrame()


def load_provenance(filepath: str) -> dict:
    """加载数据溯源 JSON sidecar。"""
    prov_path = _provenance_path(filepath)
    if os.path.exists(prov_path):
        with open(prov_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_provenance(filepath: str, provenance: dict):
    """保存数据溯源 JSON sidecar。"""
    prov_path = _provenance_path(filepath)
    with open(prov_path, "w", encoding="utf-8") as f:
        json.dump(provenance, f, indent=2, default=str)


def save_cache(df: pd.DataFrame, filepath: str, provenance: dict = None):
    """将 DataFrame 保存为 CSV 缓存，附带溯源信息。"""
    ensure_data_dir()
    df.to_csv(filepath)
    if provenance is None:
        provenance = {}
    provenance.setdefault("last_saved", datetime.now().isoformat())
    provenance.setdefault("row_count", len(df))
    save_provenance(filepath, provenance)


def get_missing_range(filepath: str, lookback_days: int = 365 * 5) -> tuple:
    """
    检查本地缓存的最新日期，返回需要从 API 获取的日期范围。

    yfinance 的 end 参数是排他的 (exclusive)，因此 end 设为明天
    以确保能获取到今天的数据。

    Returns:
        (start_date: str, end_date: str) 或 (None, None) 如果不需要更新
    """
    df = load_cache(filepath)

    # end 设为明天，因为 yfinance end 是排他的
    end_date = datetime.now() + timedelta(days=1)

    if df.empty:
        start_date = end_date - timedelta(days=lookback_days)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 检查缓存最新日期
    if isinstance(df.index, pd.DatetimeIndex):
        last_date = df.index.max()
    else:
        last_date = end_date - timedelta(days=lookback_days)

    # 检查 provenance 中的 is_synthetic 标记
    prov = df.attrs.get("provenance", {}) or load_provenance(filepath)
    is_synthetic = prov.get("is_synthetic", False)
    if is_synthetic:
        # 模拟数据：全量重新下载
        start_date = end_date - timedelta(days=lookback_days)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    # 如果缓存最后日期早于今天 (非周末)，则需要更新
    today = datetime.now().date()
    if last_date.date() < today:
        # 周末不强制要求更新（周五数据在周一早上仍然是最新的）
        if today.weekday() >= 5:  # Saturday=5, Sunday=6
            if last_date.date() >= today - timedelta(days=3):
                return None, None
        # 需要更新：从缓存最后日期前 5 天开始（避免缺口）
        start_date = (last_date - timedelta(days=5)).strftime("%Y-%m-%d")
        return start_date, end_date.strftime("%Y-%m-%d")

    return None, None


def update_cache(filepath: str, new_df: pd.DataFrame,
                 provenance: dict = None) -> pd.DataFrame:
    """
    将新数据合并到缓存中，去重后保存。
    返回合并后的完整 DataFrame。
    """
    existing = load_cache(filepath)

    if existing.empty:
        save_cache(new_df, filepath, provenance)
        return new_df

    # 合并并去重（基于日期索引）
    if isinstance(existing.index, pd.DatetimeIndex) and \
       isinstance(new_df.index, pd.DatetimeIndex):
        combined = pd.concat([existing, new_df])
        combined = combined[~combined.index.duplicated(keep='last')]
        combined = combined.sort_index()
    else:
        combined = new_df

    # 合并 provenance
    merged_prov = (existing.attrs.get("provenance", {}) or {}).copy()
    if provenance:
        merged_prov.update(provenance)
    merged_prov["last_updated"] = datetime.now().isoformat()
    merged_prov["row_count"] = len(combined)
    merged_prov["is_synthetic"] = False

    save_cache(combined, filepath, merged_prov)
    return combined


def get_data_quality_report() -> dict:
    """
    检查所有缓存数据的质量：是否模拟、是否过期。
    返回质量报告字典。
    """
    caches = {
        "ndx_history": CACHE_NDX_HISTORY,
        "vix_history": CACHE_VIX_HISTORY,
        "dxy_history": CACHE_DXY_HISTORY,
    }
    issues = []
    is_synthetic = False

    for name, path in caches.items():
        prov = load_provenance(path)
        if prov.get("is_synthetic"):
            is_synthetic = True
            issues.append(f"{name}: 模拟数据")
        else:
            df = load_cache(path)
            if df.empty:
                issues.append(f"{name}: 无数据")
            elif isinstance(df.index, pd.DatetimeIndex):
                last_date = df.index.max().date()
                days_ago = (datetime.now().date() - last_date).days
                if days_ago > 3:
                    issues.append(f"{name}: 数据过期 ({days_ago}天前, 最后日期={last_date})")

    return {
        "is_synthetic": is_synthetic,
        "has_issues": len(issues) > 0,
        "issues": issues,
        "checked_at": datetime.now().isoformat(),
    }


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
