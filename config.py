"""
纳指投资建议系统 — 全局配置
==============================
所有可调整的权重、阈值、API keys 集中管理。
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# API Keys (从环境变量读取，GitHub Actions 中通过 secrets 注入)
# ============================================================
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
SERVER_CHAN_KEY = os.getenv("SERVER_CHAN_KEY", "")  # Server酱 SendKey
EMAIL_SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")

# ============================================================
# 指标权重 (总和 100%)
# ============================================================
WEIGHTS = {
    "pe_percentile":   0.25,  # PE 估值分位
    "vix":             0.15,  # VIX 恐慌指数
    "rsi":             0.10,  # RSI 相对强弱
    "macd":            0.10,  # MACD 趋势动能
    "ma_deviation":    0.10,  # 均线偏离度
    "fear_greed":      0.10,  # 恐慌贪婪指数
    "macro":           0.10,  # 宏观利率
    "dxy":             0.05,  # 美元指数
    "breadth":         0.05,  # 市场宽度
}

# ============================================================
# PE 估值分位 - 阈值 (百分位 %)
# ============================================================
PE_PERCENTILE_THRESHOLDS = {
    "extremely_undervalued": 20,   # < 20% → +2
    "undervalued":           40,   # 20-40% → +1
    "fair":                  60,   # 40-60% → 0
    "overvalued":            80,   # 60-80% → -1
    # > 80% → -2
}

# PE 分位计算参考窗口
PE_LOOKBACK_YEARS = 10  # 优先用 10 年，数据不足则用全部

# ============================================================
# VIX 恐慌指数 - 阈值
# ============================================================
VIX_THRESHOLDS = {
    "extreme_calm":  12,   # < 12 → -1
    "calm":          18,   # 12-18 → 0
    "moderate_fear": 25,   # 18-25 → +1
    "high_fear":     35,   # 25-35 → +2
    # > 35 → -1
}

# ============================================================
# RSI 相对强弱 - 阈值
# ============================================================
RSI_PERIOD = 14
RSI_THRESHOLDS = {
    "oversold":          30,   # < 30 → +2
    "weak":              40,   # 30-40 → +1
    "neutral_low":       50,   # 40-50 → 0
    "neutral_high":      60,   # 50-60 → 0
    "strong":            70,   # 60-70 → -1
    # > 70 → -2
}

# ============================================================
# MACD - 参数
# ============================================================
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ============================================================
# 均线偏离度 - 阈值
# ============================================================
MA_DEVIATION_THRESHOLDS = {
    "deep_below_ma200":  -10,   # < -10% from MA200 → +2
    "below_ma200":        -5,   # -5% to -10% → +1
    "above_ma200_extreme": 20,  # > +20% from MA200 → -2
    "above_ma50":         10,   # > +10% from MA50 → -1
}

# ============================================================
# 恐慌贪婪指数 - 阈值
# ============================================================
FEAR_GREED_THRESHOLDS = {
    "extreme_fear":  25,   # 0-25 → +2
    "fear":          45,   # 25-45 → +1
    "neutral":       55,   # 45-55 → 0
    "greed":         75,   # 55-75 → -1
    # > 75 → -2
}

# ============================================================
# 宏观利率 - FRED Series IDs
# ============================================================
FRED_SERIES = {
    "fed_funds_rate":  "DFF",      # 联邦基金有效利率
    "10y_yield":       "DGS10",    # 10年期国债收益率
    "2y_yield":        "DGS2",     # 2年期国债收益率
    "10y_2y_spread":   "T10Y2Y",   # 10Y-2Y 利差 (直接获取)
}

# 利差阈值
SPREAD_THRESHOLDS = {
    "deep_inversion":  -0.50,   # < -0.50% → +2
    "inversion":        0.00,   # -0.50 to 0 → +1
    "normal_low":       1.00,   # 0 to 1.00 → 0
    # > 1.00 → -1 (正常偏高，可能加息)
}

# ============================================================
# 美元指数 DXY - 阈值 (20 日涨跌幅 %)
# ============================================================
DXY_THRESHOLDS = {
    "strong_up":    2.0,    # > +2% → -1
    "strong_down": -2.0,    # < -2% → +1
}

# ============================================================
# 市场宽度 - 阈值 (成分股在 MA50 以上的比例 %)
# ============================================================
BREADTH_THRESHOLDS = {
    "extreme_pessimism": 30,   # < 30% → +2
    "pessimism":         50,   # 30-50% → +1
    "neutral":           70,   # 50-70% → 0
    "optimism":          85,   # 70-85% → -1
    # > 85% → -2
}

# ============================================================
# 决策映射 (加权总分 → 建议)
# ============================================================
DECISION_THRESHOLDS = {
    "aggressive_buy":  8,    # >= 8  → 大幅加仓
    "increase_dca":    3,    # 3-7   → 加大定投
    "maintain_dca":   -2,    # -2-2  → 保持定投
    "reduce_dca":     -7,    # -7 到 -3 → 减少定投
    # < -7 → 暂停观望
}

# ============================================================
# 数据缓存设置
# ============================================================
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
CACHE_NDX_HISTORY = os.path.join(DATA_DIR, "ndx_history.csv")
CACHE_PE_HISTORY = os.path.join(DATA_DIR, "pe_history.csv")
CACHE_VIX_HISTORY = os.path.join(DATA_DIR, "vix_history.csv")
CACHE_DXY_HISTORY = os.path.join(DATA_DIR, "dxy_history.csv")

# 报告设置
REPORT_FILE = os.path.join(OUTPUT_DIR, "index.html")
ARCHIVE_DIR = os.path.join(OUTPUT_DIR, "archive")

# GitHub Pages URL (部署后由用户设置)
GITHUB_PAGES_URL = os.getenv("GITHUB_PAGES_URL", "")
