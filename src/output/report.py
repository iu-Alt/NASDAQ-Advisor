"""
HTML 报告生成
================
使用 Plotly 生成交互式图表，Jinja2 模板渲染为最终 HTML 报告。
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import (
    OUTPUT_DIR, REPORT_FILE, VIX_THRESHOLDS,
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
)

logger = logging.getLogger(__name__)

# Jinja2 环境
_TPL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
_jinja_env = Environment(
    loader=FileSystemLoader(_TPL_DIR),
    autoescape=select_autoescape(["html"]),
)


def generate_report(all_data: Dict, indicator_results: Dict,
                    scoring_result: Dict, decision_result: Dict) -> str:
    """
    主入口：生成完整 HTML 报告。
    返回报告文件路径。
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 生成所有 Plotly 图表
    charts = {}
    charts["price-chart"] = _make_price_chart(all_data)
    charts["pe-chart"] = _make_pe_chart(all_data, indicator_results)
    charts["vix-chart"] = _make_vix_chart(all_data)
    charts["rsi-chart"] = _make_rsi_chart(all_data)
    charts["macd-chart"] = _make_macd_chart(all_data)
    charts["radar-chart"] = _make_radar_chart(indicator_results)

    # 准备模板变量
    ndx_current = all_data.get("ndx_current", {})
    pe_data = all_data.get("pe_data", {})
    vix_data = indicator_results.get("vix", {})

    price_str = f"${ndx_current.get('price', 'N/A'):,.0f}" if ndx_current.get("price") else "N/A"

    template_vars = {
        "report_date": all_data.get("fetch_date", datetime.now().strftime("%Y-%m-%d")),
        "timestamp": all_data.get("timestamp", datetime.now().isoformat()),
        "ndx_price": price_str,
        "ndx_data": ndx_current,
        "pe_data": pe_data,
        "vix_data": vix_data,
        "scoring": scoring_result,
        "decision": decision_result,
        "charts": charts,
    }

    # 渲染
    template = _jinja_env.get_template("report.html")
    html = template.render(**template_vars)

    # 写入文件
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"Report generated: {REPORT_FILE} ({len(html)} bytes)")
    return REPORT_FILE


# ============================================================
# 图表生成函数
# ============================================================

PLOTLY_THEME = "plotly_dark"
CHART_HEIGHT = 400
COLORS = {
    "price": "#60a5fa",
    "ma50": "#f59e0b",
    "ma200": "#ef4444",
    "pe": "#c084fc",
    "vix": "#f97316",
    "rsi": "#22c55e",
    "macd": "#3b82f6",
    "signal": "#f59e0b",
    "hist_green": "#22c55e",
    "hist_red": "#ef4444",
    "grid": "#1e293b",
    "bg": "#0f172a",
}


def _make_price_chart(data: Dict) -> str:
    """NDX 价格走势图 (含 MA50/MA200)。"""
    df = data.get("ndx_history", pd.DataFrame())
    if df.empty or "close" not in df.columns:
        return "null"

    df = df.tail(252 * 2)  # 近 2 年
    closes = df["close"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=closes.index, y=closes.values,
        mode="lines", name="NDX",
        line=dict(color=COLORS["price"], width=1.5),
    ))

    if len(closes) >= 50:
        ma50 = closes.rolling(50).mean()
        fig.add_trace(go.Scatter(
            x=ma50.index, y=ma50.values,
            mode="lines", name="MA50",
            line=dict(color=COLORS["ma50"], width=1, dash="dash"),
        ))
    if len(closes) >= 200:
        ma200 = closes.rolling(200).mean()
        fig.add_trace(go.Scatter(
            x=ma200.index, y=ma200.values,
            mode="lines", name="MA200",
            line=dict(color=COLORS["ma200"], width=1, dash="dot"),
        ))

    fig.update_layout(
        template=PLOTLY_THEME,
        title="NASDAQ-100 价格走势",
        height=CHART_HEIGHT,
        margin=dict(l=40, r=20, t=40, b=40),
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    return fig.to_json()


def _make_pe_chart(data: Dict, indicators: Dict) -> str:
    """PE 分位图（简化版：展示近期价格作为估值参考）。"""
    df = data.get("ndx_history", pd.DataFrame())
    if df.empty or "close" not in df.columns:
        return "null"

    df = df.tail(252 * 5)  # 近 5 年
    pe_info = indicators.get("pe_percentile", {})
    current_pe = pe_info.get("current_pe")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["close"].values,
        mode="lines", name="NDX 价格",
        line=dict(color=COLORS["price"], width=1.5),
        hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.0f}<extra></extra>",
    ))

    # 标注当前 PE
    if current_pe:
        percentile = pe_info.get("percentile", "N/A")
        assessment = pe_info.get("assessment", "")
        fig.add_annotation(
            xref="paper", yref="paper", x=0.02, y=0.95,
            text=f"当前 PE: {current_pe:.1f}<br>分位: {percentile}%<br>{assessment}",
            showarrow=False,
            font=dict(size=12, color=COLORS["pe"]),
            bgcolor="rgba(15,23,42,0.8)",
            bordercolor=COLORS["pe"],
            borderwidth=1,
            align="left",
        )

    fig.update_layout(
        template=PLOTLY_THEME,
        title=f"NDX 估值参考 (PE: {current_pe})" if current_pe else "NDX 价格走势 (近5年)",
        height=CHART_HEIGHT,
        margin=dict(l=40, r=20, t=40, b=40),
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        hovermode="x unified",
    )
    return fig.to_json()


def _make_vix_chart(data: Dict) -> str:
    """VIX 走势图 (含关键阈值)。"""
    df = data.get("vix_history", pd.DataFrame())
    if df.empty or "close" not in df.columns:
        return "null"

    df = df.tail(252)  # 近 1 年
    vix = df["close"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=vix.index, y=vix.values,
        mode="lines", name="VIX",
        line=dict(color=COLORS["vix"], width=1.5),
        fill="tozeroy",
        fillcolor="rgba(249,115,22,0.08)",
    ))

    # 关键阈值线
    for level, label in [(12, "极度平静"), (18, "正常"), (25, "恐慌"), (35, "极端恐慌")]:
        fig.add_hline(
            y=level, line_dash="dash", line_width=0.8,
            line_color="rgba(148,163,184,0.3)",
            annotation_text=label,
            annotation_position="top right",
            annotation_font=dict(size=9, color="#64748b"),
        )

    fig.update_layout(
        template=PLOTLY_THEME,
        title="VIX 恐慌指数 (近 1 年)",
        height=CHART_HEIGHT,
        margin=dict(l=40, r=20, t=40, b=40),
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        hovermode="x unified",
    )
    return fig.to_json()


def _make_rsi_chart(data: Dict) -> str:
    """RSI 走势图 (含超买/超卖线)。"""
    df = data.get("ndx_history", pd.DataFrame())
    if df.empty or "close" not in df.columns:
        return "null"

    closes = df["close"].dropna().tail(252)
    if len(closes) < RSI_PERIOD + 1:
        return "null"

    # 手动计算 RSI
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(span=RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(span=RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rsi.index, y=rsi.values,
        mode="lines", name="RSI(14)",
        line=dict(color=COLORS["rsi"], width=1.5),
    ))

    # 关键线
    for level, label, color in [
        (70, "超买 70", COLORS["hist_red"]),
        (30, "超卖 30", COLORS["hist_green"]),
        (50, "中性 50", "#64748b"),
    ]:
        fig.add_hline(
            y=level, line_dash="dash", line_width=0.8,
            line_color=color,
            annotation_text=label,
            annotation_position="right",
            annotation_font=dict(size=9, color=color),
        )

    fig.update_layout(
        template=PLOTLY_THEME,
        title="RSI 相对强弱 (近 1 年)",
        height=CHART_HEIGHT,
        margin=dict(l=40, r=20, t=40, b=40),
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        yaxis=dict(range=[0, 100]),
        hovermode="x unified",
    )
    return fig.to_json()


def _make_macd_chart(data: Dict) -> str:
    """MACD 图 (含柱状线)。"""
    df = data.get("ndx_history", pd.DataFrame())
    if df.empty or "close" not in df.columns:
        return "null"

    closes = df["close"].dropna().tail(252)
    if len(closes) < MACD_SLOW + MACD_SIGNAL + 2:
        return "null"

    ema_fast = closes.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = closes.ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    histogram = macd_line - signal_line

    fig = make_subplots(specs=[[{"secondary_y": False}]])
    fig.add_trace(go.Bar(
        x=histogram.index, y=histogram.values,
        name="柱状线",
        marker=dict(
            color=[COLORS["hist_green"] if v >= 0 else COLORS["hist_red"]
                   for v in histogram.values],
            opacity=0.6,
        ),
    ))
    fig.add_trace(go.Scatter(
        x=macd_line.index, y=macd_line.values,
        mode="lines", name="MACD",
        line=dict(color=COLORS["macd"], width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=signal_line.index, y=signal_line.values,
        mode="lines", name="Signal",
        line=dict(color=COLORS["signal"], width=1),
    ))

    fig.update_layout(
        template=PLOTLY_THEME,
        title="MACD (12,26,9) — 近 1 年",
        height=CHART_HEIGHT,
        margin=dict(l=40, r=20, t=40, b=40),
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        hovermode="x unified",
    )
    return fig.to_json()


def _make_radar_chart(indicator_results: Dict) -> str:
    """指标雷达图 — 9 个指标的得分总览。"""
    from config import WEIGHTS

    categories = []
    scores = []
    for key, weight in WEIGHTS.items():
        ind = indicator_results.get(key, {})
        display_names = {
            "pe_percentile": "PE分位", "vix": "VIX", "rsi": "RSI",
            "macd": "MACD", "ma_deviation": "均线偏离",
            "fear_greed": "恐慌贪婪", "macro": "宏观利率",
            "dxy": "美元指数", "breadth": "市场宽度",
        }
        categories.append(display_names.get(key, key))
        scores.append(ind.get("score", 0) if ind else 0)

    # 闭合雷达图
    categories.append(categories[0])
    scores.append(scores[0])

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=scores, theta=categories,
        fill="toself",
        name="当前得分",
        line=dict(color=COLORS["pe"], width=2),
        fillcolor="rgba(139,92,246,0.2)",
    ))

    # 参考圈
    fig.add_trace(go.Scatterpolar(
        r=[0] * len(categories), theta=categories,
        mode="lines", name="中性 (0)",
        line=dict(color="#64748b", width=1, dash="dash"),
        showlegend=False,
    ))

    fig.update_layout(
        template=PLOTLY_THEME,
        title="指标雷达图",
        height=CHART_HEIGHT + 100,
        margin=dict(l=60, r=60, t=60, b=60),
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        polar=dict(
            radialaxis=dict(
                range=[-2.5, 2.5],
                tickvals=[-2, -1, 0, 1, 2],
                ticktext=["-2", "-1", "0", "+1", "+2"],
                gridcolor=COLORS["grid"],
            ),
            angularaxis=dict(gridcolor=COLORS["grid"]),
            bgcolor=COLORS["bg"],
        ),
    )
    return fig.to_json()
