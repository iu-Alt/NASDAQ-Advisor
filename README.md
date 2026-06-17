# 📊 纳斯达克 100 投资建议系统

> 📈 每日报告：**[点击查看](https://iu-alt.github.io/NASDAQ-Advisor/)**

基于多维度技术分析的 NASDAQ-100 指数每日投资建议，自动生成 HTML 可视化报告，支持微信/邮件推送。

## 功能

- 🔬 **9 项综合指标**：PE 估值分位、VIX 恐慌指数、RSI、MACD、均线偏离、恐慌贪婪指数、宏观利率、美元指数、市场宽度
- ⚖️ **加权评分模型**：每项指标按权重汇总，生成 5 档投资建议（大幅加仓 → 暂停观望）
- 📈 **交互式 HTML 报告**：Plotly 图表，包含雷达图、技术指标面板、历史趋势
- 📲 **智能推送**：仅在需要操作时通过微信/邮件通知（保持定投时不打扰）
- ⏰ **每日自动更新**：GitHub Actions 定时触发，美股收盘后自动运行

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/nasdaq-advisor.git
cd nasdaq-advisor
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置（可选）

复制 `.env.example` 为 `.env`，填入 API Keys：

```bash
cp .env.example .env
```

| 配置项 | 必需 | 说明 |
|--------|------|------|
| `FRED_API_KEY` | 推荐 | 宏观利率数据，[免费注册](https://fred.stlouisfed.org/docs/api/api_key.html) |
| `SERVER_CHAN_KEY` | 可选 | Server酱微信推送，[注册](https://sct.ftqq.com/) |
| `EMAIL_*` | 可选 | 邮件推送 (SMTP) |
| `GITHUB_PAGES_URL` | 可选 | 报告链接，用于推送消息中 |

### 4. 运行

```bash
python src/main.py
```

报告生成在 `output/index.html`，用浏览器打开即可查看。

## 指标体系

| 指标 | 权重 | 数据源 | 说明 |
|------|------|--------|------|
| PE 估值分位 | 25% | yfinance / Nasdaq.com / QQQ ETF | 当前 PE 在历史中的分位数 |
| VIX 恐慌指数 | 15% | yfinance (^VIX) | 期权隐含波动率，市场恐惧指标 |
| RSI 相对强弱 | 10% | NDX 收盘价计算 | 14日 RSI，超买/超卖判断 |
| MACD 趋势动能 | 10% | NDX 收盘价计算 | 12/26/9 MACD，趋势与动能 |
| 均线偏离度 | 10% | MA50 / MA200 | 价格相对于长短期均线的偏离 |
| 恐慌贪婪指数 | 10% | CNN / VIX 推算 | 市场情绪综合指标 |
| 宏观利率 | 10% | FRED API | 联邦基金利率、10Y-2Y 利差 |
| 美元指数 | 5% | yfinance (DXY) | 美元强弱影响全球资金流向 |
| 市场宽度 | 5% | NDX 成分股 | 高于 MA50 的成分股比例 |

## 决策映射

| 得分区间 | 建议 | 操作 | 推送 |
|---------|------|------|------|
| ≥ 8 | 🟢 大幅加仓 | 定投基础上追加 50-100% | ✅ |
| 3 ~ 7 | 🟢 加大定投 | 定投基础上追加 20-50% | ✅ |
| -2 ~ 2 | 🟡 保持定投 | 按原计划执行 | ❌ |
| -6 ~ -3 | 🟠 减少定投 | 定投金额减半 | ✅ |
| ≤ -7 | 🔴 暂停观望 | 暂停定投，持有现金 | ✅ |

## GitHub Actions 部署

1. Fork 本仓库
2. 在仓库 Settings → Secrets and variables → Actions 中设置：
   - `FRED_API_KEY`（推荐）
   - `SERVER_CHAN_KEY`（可选）
   - `GITHUB_PAGES_URL`: `https://YOUR_USERNAME.github.io/nasdaq-advisor/`
3. 在 Settings → Pages 中启用 GitHub Pages，Source 选择 `gh-pages` 分支
4. 系统将在每个交易日美东时间 16:30 (北京时间次日 05:30) 自动运行
5. 也可以手动触发：Actions → Daily NASDAQ Analysis → Run workflow

## 项目结构

```
纳指/
├── .github/workflows/      # GitHub Actions
├── src/
│   ├── data/               # 数据获取与缓存
│   │   ├── fetcher.py      # yfinance, FRED, CNN, Web scraping
│   │   └── store.py        # CSV 缓存读写
│   ├── indicators/         # 9 个指标计算模块
│   ├── engine/             # 加权评分 & 决策引擎
│   ├── output/             # HTML 报告 & 通知推送
│   └── main.py             # 主入口
├── templates/              # Jinja2 HTML 模板
├── config.py               # 全局配置（权重、阈值）
├── data/                   # 缓存的历史数据
├── output/                 # 生成的报告
└── scripts/                # 工具脚本
```

## 免责声明

⚠️ **本系统仅供个人投资参考，不构成任何形式的投资建议。**

- 所有分析基于公开数据和量化模型，模型可能失效
- 过往表现不代表未来收益
- 投资有风险，决策需谨慎
- 请结合自身风险承受能力、财务状况独立判断
- 作者不对使用本系统产生的任何投资损失负责

## License

MIT
