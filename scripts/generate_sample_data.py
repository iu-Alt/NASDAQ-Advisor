"""
生成示例数据用于本地测试（当 yfinance 被限流时）。
数据为模拟数据，仅用于验证分析管道是否正常工作。
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config import (
    CACHE_NDX_HISTORY, CACHE_VIX_HISTORY,
    CACHE_DXY_HISTORY, CACHE_PE_HISTORY, DATA_DIR,
)

os.makedirs(DATA_DIR, exist_ok=True)


def generate_ndx_history(days: int = 252 * 5):
    """生成模拟 NDX 历史价格数据 (近 5 年)。"""
    end = datetime.now()
    dates = pd.date_range(start=end - timedelta(days=days), end=end, freq="B")

    # 从 14000 附近起步，模拟趋势上行 + 波动
    np.random.seed(42)
    base = 14000.0
    annual_return = 0.12
    annual_vol = 0.22

    daily_return = annual_return / 252
    daily_vol = annual_vol / np.sqrt(252)

    returns = np.random.normal(daily_return, daily_vol, len(dates))
    # 加入一些自相关 (趋势)
    returns = pd.Series(returns).rolling(5).mean().fillna(0).values

    prices = base * np.exp(np.cumsum(returns))
    # 确保价格不过于偏离
    prices = np.clip(prices, 8000, 25000)

    # 加入一些关键价格形态 (回调和反弹)
    # 模拟 2022 年的回调
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

    # 模拟 VIX 均值回归过程
    vix = [vix_mean]
    for i in range(1, len(dates)):
        innovation = np.random.normal(0, vix_vol)
        vix.append(max(8, vix[-1] + 0.02 * (vix_mean - vix[-1]) + innovation))

    # 添加一些恐慌事件
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

    df.to_csv(CACHE_DXY_HISTORY)
    print(f"Generated DXY history: {len(df)} rows → {CACHE_DXY_HISTORY}")
    return df


def main():
    print("Generating sample data for testing...")
    print("=" * 50)
    generate_ndx_history()
    generate_vix_history()
    generate_dxy_history()
    print("=" * 50)
    print("Done! You can now run: python src/main.py")


if __name__ == "__main__":
    main()
