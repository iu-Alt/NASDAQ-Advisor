"""
生成示例数据用于本地测试（当 yfinance 被限流时）。
数据为模拟数据，仅用于验证分析管道是否正常工作。

⚠️ 此脚本输出到 tests/fixtures/，不会覆盖生产 data/ 目录。
   生产环境运行前请确保 data/ 中有真实数据。
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 输出到 tests/fixtures/，不污染生产 data/
FIXTURE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(FIXTURE_DIR, exist_ok=True)

CACHE_NDX_HISTORY = os.path.join(FIXTURE_DIR, "ndx_history.csv")
CACHE_VIX_HISTORY = os.path.join(FIXTURE_DIR, "vix_history.csv")
CACHE_DXY_HISTORY = os.path.join(FIXTURE_DIR, "dxy_history.csv")

# 安全守卫：禁止写入生产 data/ 目录
PROD_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
if os.path.abspath(FIXTURE_DIR) == os.path.abspath(PROD_DATA_DIR):
    raise RuntimeError(
        "SAFETY GUARD: generate_sample_data.py must write to tests/fixtures/, "
        "not the production data/ directory."
    )


def generate_ndx_history(days: int = 252 * 5):
    """生成模拟 NDX 历史价格数据 (近 5 年)。"""
    end = datetime.now()
    dates = pd.date_range(start=end - timedelta(days=days), end=end, freq="B")

    np.random.seed(42)
    base = 14000.0
    annual_return = 0.12
    annual_vol = 0.22

    daily_return = annual_return / 252
    daily_vol = annual_vol / np.sqrt(252)

    returns = np.random.normal(daily_return, daily_vol, len(dates))
    returns = pd.Series(returns).rolling(5).mean().fillna(0).values

    prices = base * np.exp(np.cumsum(returns))
    prices = np.clip(prices, 8000, 25000)

    mid_point = len(dates) // 2
    dip = np.linspace(0, -0.25, 60)
    recovery = np.linspace(-0.25, 0.15, 120)
    for i in range(len(dip)):
        prices[mid_point + i] *= (1 + dip[i])
    for i in range(len(recovery)):
        if mid_point + 60 + i < len(prices):
            prices[mid_point + 60 + i] *= (1 + recovery[i])

    df = pd.DataFrame({
        "close": prices,
        "open": prices * (1 + np.random.normal(0, 0.005, len(dates))),
        "high": prices * (1 + np.abs(np.random.normal(0, 0.01, len(dates)))),
        "low": prices * (1 - np.abs(np.random.normal(0, 0.01, len(dates)))),
        "volume": np.random.randint(10_000_000, 50_000_000, len(dates)),
    }, index=dates)

    # 标记为模拟数据
    df.attrs["is_synthetic"] = True
    df.attrs["source"] = "generate_sample_data.py"
    df.attrs["generated_at"] = datetime.now().isoformat()

    df.to_csv(CACHE_NDX_HISTORY)
    print(f"Generated NDX history: {len(df)} rows → {CACHE_NDX_HISTORY}")
    return df


def generate_vix_history(days: int = 252 * 3):
    """生成模拟 VIX 历史数据。"""
    end = datetime.now()
    dates = pd.date_range(start=end - timedelta(days=days), end=end, freq="B")

    np.random.seed(123)
    vix_mean = 20
    vix_vol = 0.5

    vix = [vix_mean]
    for i in range(1, len(dates)):
        innovation = np.random.normal(0, vix_vol)
        vix.append(max(8, vix[-1] + 0.02 * (vix_mean - vix[-1]) + innovation))

    for spike_start in [100, 500, 700]:
        for j in range(20):
            if spike_start + j < len(vix):
                vix[spike_start + j] += 35 * np.exp(-j / 5)

    vix = np.clip(vix, 8, 45)

    df = pd.DataFrame({
        "close": vix,
        "open": vix + np.random.normal(0, 0.3, len(dates)),
        "high": vix + np.abs(np.random.normal(0, 0.5, len(dates))),
        "low": vix - np.abs(np.random.normal(0, 0.5, len(dates))),
        "volume": np.random.randint(5_000_000, 20_000_000, len(dates)),
    }, index=dates)

    df.attrs["is_synthetic"] = True
    df.attrs["source"] = "generate_sample_data.py"
    df.attrs["generated_at"] = datetime.now().isoformat()

    df.to_csv(CACHE_VIX_HISTORY)
    print(f"Generated VIX history: {len(df)} rows → {CACHE_VIX_HISTORY}")
    return df


def generate_dxy_history(days: int = 252 * 2):
    """生成模拟 DXY 历史数据。"""
    end = datetime.now()
    dates = pd.date_range(start=end - timedelta(days=days), end=end, freq="B")

    np.random.seed(456)
    base = 100.0
    returns = np.random.normal(0.0001, 0.005, len(dates))
    prices = base * np.exp(np.cumsum(returns))
    prices = np.clip(prices, 90, 115)

    df = pd.DataFrame({
        "close": prices,
        "open": prices * (1 + np.random.normal(0, 0.002, len(dates))),
        "high": prices * (1 + np.abs(np.random.normal(0, 0.005, len(dates)))),
        "low": prices * (1 - np.abs(np.random.normal(0, 0.005, len(dates)))),
    }, index=dates)

    df.attrs["is_synthetic"] = True
    df.attrs["source"] = "generate_sample_data.py"
    df.attrs["generated_at"] = datetime.now().isoformat()

    df.to_csv(CACHE_DXY_HISTORY)
    print(f"Generated DXY history: {len(df)} rows → {CACHE_DXY_HISTORY}")
    return df


def main():
    print("Generating sample data for testing...")
    print(f"Output directory: {FIXTURE_DIR}")
    print("=" * 50)
    generate_ndx_history()
    generate_vix_history()
    generate_dxy_history()
    print("=" * 50)
    print("Done! Copy these CSVs to data/ for local testing, or run with real yfinance data.")
    print("WARNING: These are SYNTHETIC data. Production reports will refuse recommendations on them.")


if __name__ == "__main__":
    main()
