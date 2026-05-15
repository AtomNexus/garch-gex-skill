---
name: garch-gex-skill
description: GARCH QUANT 期权 GEX 分析 — 多标的（SPX/SPY/QQQ）期权链爬取、GEX 计算、Gamma 翻转位识别、品牌化 HTML 报告生成
category: finance
---

# GARCH QUANT 期权 GEX 分析 Skill

## 功能概述

实时爬取 SPX、SPY、QQQ 三个标的的期权链数据，计算 GEX（Gamma Exposure）指标，识别 Gamma 翻转价位，生成品牌化 HTML 分析报告。

## 核心公式

**GEX = Gamma × OpenInterest × ContractMultiplier**

- SPX/SPY/QQQ 合约乘数均为 100
- 正 GEX → 机构做多 Gamma（压制波动）；负 GEX → 机构做空 Gamma（助涨波动）
- Gamma 翻转位：GEX 符号由正转负（或反之）的行权价，是重要的动态支撑/阻力位

## 数据来源

- API: `https://api.marketdata.app/v1/options/chains/{SYMBOL}`
- 无需 API Key（公共接口）

## 输出文件

| 文件 | 说明 |
|------|------|
| `SPX_GEX_Report.html` | SPX 标普 500 指数 GEX 详细报告 |
| `SPY_GEX_Report.html` | SPY 标普 500 ETF GEX 详细报告 |
| `QQQ_GEX_Report.html` | QQQ 纳斯达克 100 ETF GEX 详细报告 |
| `GARCH_QUANT_GEX_Overview.html` | 三合一总览页面 |

## 使用方式

### 1. 手动一次性运行

```bash
python ~/.hermes/skills/garch-gex-skill/scripts/gex_analysis.py
```

### 2. 定时任务（cron）

推荐通过 cronjob 工具定时执行，例如每 30 分钟一次：

```
技能: garch-gex-skill
定时: every 30m
```

或通过 cronjob action='create' 完整创建：

```bash
# 首次运行后，定时任务自动按 schedule 执行
```

### 3. 作为模块导入

```python
from scripts.gex_analysis import GEXAnalysisSkill, run_all_symbols_task

# 单标的分析
skill = GEXAnalysisSkill("SPX")
chain_df = skill.get_option_chain()
gex_df, flip_strikes, total_net_gex = skill.calc_gex(chain_df)
html = skill.generate_brand_html(gex_df, flip_strikes, total_net_gex)
```

## 配置项（gex_analysis.py 顶部）

```python
SYMBOLS = ["SPX", "SPY", "QQQ"]      # 监测标的
CONTRACT_MULTIPLIER = 100           # 合约乘数
BASE_URL = "https://api.marketdata.app/v1/options/chains"
SAVE_DIR = "./"                     # 报告保存目录
RUN_INTERVAL_MIN = 30               # 定时运行间隔（分钟）
BRAND_NAME = "GARCH QUANT"
BRAND_STYLE_COLOR = "#002b5c"       # 深海军蓝
BRAND_ACCENT_COLOR = "#d4af37"      # 哑光金
```

## 报告解读

### 净 GEX（NetGEX）
- **正值**：期权市场整体做多 Gamma，机构倾向于卖出期权（Short Gamma），市场波动被压制
- **负值**：期权市场整体做空 Gamma，机构倾向于买入期权（Long Gamma），波动可能放大

### Gamma 翻转位（Gamma Flip Strike）
- 净 GEX 符号切换的行权价
- 接近该价位时，机构做市商对冲行为最活跃，价格容易出现快速波动
- 常被视为日内交易的关键拐点参考

## 已知限制

- 该 API 为公共接口，有频率限制，高频调用可能返回 429
- 不支持夜盘/期货期权的 GEX 计算
- GEX 指标仅反映期权市场的 Gamma 暴露，不构成投资建议

## 修复记录

- v1.1：修复原始代码 9 处 HTML 标签残缺、`__name__` 下划线缺失、`flip_strikes` 未转义等问题
