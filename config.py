"""
纳指投资建议系统 — 全局配置
==============================
所有可调整的权重、阈值、API keys 集中管理。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# CI 环境中可能没有 .env 文件，静默跳过
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    load_dotenv()  # 尝试从当前目录查找

# ============================================================
# 辅助函数：处理 GitHub Actions 中空字符串 secrets 的问题
# ============================================================
def _env(key: str, default: str = "") -> str:
    """获取环境变量，空字符串视为未设置。"""
    val = os.getenv(key, default)
    return val if val else default

def _env_int(key: str, default: int) -> int:
    """获取整数环境变量，空字符串视为未设置。"""
    val = os.getenv(key, "")
    return int(val) if val else default

# ============================================================
# API Keys (从环境变量读取，GitHub Actions 中通过 secrets 注入)
# ============================================================
FRED_API_KEY = _env("FRED_API_KEY")
SERVER_CHAN_KEY = _env("SERVER_CHAN_KEY")  # Server酱 SendKey
EMAIL_SMTP_HOST = _env("EMAIL_SMTP_HOST")
EMAIL_SMTP_PORT = _env_int("EMAIL_SMTP_PORT", 587)
EMAIL_USER = _env("EMAIL_USER")
EMAIL_PASSWORD = _env("EMAIL_PASSWORD")
EMAIL_TO = _env("EMAIL_TO")

# ============================================================
# 指标权重 (总和 100%)
# ============================================================
# 注意：
#   - PE 估值分位 (原 25%) 已移除 — 当前 PE 历史回推算法为同义反复，
#     在获得可靠的历史估值数据前暂时不计入评分。
#   - 市场宽度 (原 5%) 已移除 — 当前代理实现 (NDX vs MA50) 与均线
#     偏离度高度重复，真实成分股宽度待后续实现。
WEIGHTS = {
    "vix":             0.20,  # VIX 恐慌指数 (was 0.15)
    "rsi":             0.15,  # RSI 相对强弱 (was 0.10)
    "macd":            0.12,  # MACD 趋势动能 (was 0.10)
    "ma_deviation":    0.15,  # 均线偏离度 (was 0.10)
    "fear_greed":      0.15,  # 恐慌贪婪指数 (was 0.10)
    "macro":           0.15,  # 宏观利率 (was 0.10)
    "dxy":             0.08,  # 美元指数 (was 0.05)
}

# 核心指标：这些指标缺失时，系统不得发出增减仓信号
# (PE 和价格数据在 data_quality 层面独立检查)
CORE_INDICATORS = ["vix", "rsi", "ma_deviation"]

# 数据质量：最大允许的数据过期天数
MAX_DATA_STALENESS_DAYS = 3

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
# VIX 恐慌指数 - 阈值 (连续评分，无悬崖跳变)
# ============================================================
# VIX 基于标普 500 期权，纳指策略优先使用 VXN。
# 评分使用平滑过渡，>35 不再从 +2 跳到 -1。
VIX_THRESHOLDS = {
    "extreme_calm":  12,   # < 12 → -1 (自满风险)
    "calm":          18,   # 12-18 → 0
    "moderate_fear": 25,   # 18-25 → +1
    "high_fear":     35,   # 25-35 → +2 (最佳买入区间)
    "extreme_fear":  50,   # 35-50 → +1 (恐慌但仍偏高，降级)
    # > 50 → 0 (极端波动，不宜入场)
}

# VXN (Nasdaq-100 波动率指数) 阈值 — 与 VIX 相同结构但阈值略高
VXN_TICKER = "^VXN"
VXN_THRESHOLDS = {
    "extreme_calm":  14,
    "calm":          20,
    "moderate_fear": 28,
    "high_fear":     38,
    "extreme_fear":  55,
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
# 注意：收益率曲线倒挂是经济衰退风险信号，不能直接解释为买入信号。
# 倒挂 → 负面(风险)，陡峭正常化 → 正面。
SPREAD_THRESHOLDS = {
    "deep_inversion":  -0.50,   # < -0.50% → -1 (深度倒挂，衰退风险)
    "inversion":        0.00,   # -0.50 to 0 → 0 (浅倒挂，偏中性)
    "normal_low":       1.00,   # 0 to 1.00 → +1 (正常偏低)
    # > 1.00 → +1 (正常偏高，经济健康但可能加息)
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
# 决策映射 (加权均值 -2 ~ +2 → 建议)
# ============================================================
# 核心原则：基础定投永不暂停。模型只控制额外加仓资金的分配。
# 所有级别都保持基础定投执行。
DECISION_THRESHOLDS = {
    "aggressive_buy":  1.2,   # >= 1.2      → 基础定投 + 额外 50-100%
    "increase_dca":    0.4,   # 0.4~1.2     → 基础定投 + 额外 20-50%
    "maintain_dca":   -0.4,   # -0.4~0.4    → 基础定投，无额外
    "reduce_extra":   -1.2,   # -1.2~-0.4   → 基础定投，暂停额外资金
    # < -1.2 → 基础定投，额外资金转入储备池
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
GITHUB_PAGES_URL = _env("GITHUB_PAGES_URL")
