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

## 数据来源（多源自动切换）

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | marketdata.app | 免费注册，需 API Key，详见本地配置 |
| 2 | Yahoo Finance | 无需 Key，频繁限流 |
| 3 | 合成演示数据 | 完全离线，明确标注 `[DEMO DATA]` |

## 安装

```bash
git clone https://github.com/AtomNexus/garch-gex-skill.git
cd garch-gex-skill/scripts

# 首次配置 API Key（可选，不配置则使用演示数据）
cp config_local.py.example config_local.py
# 编辑 config_local.py，填入你的 API Key
```

## 使用方式

```bash
cd garch-gex-skill/scripts
pip install -q requests pandas numpy schedule

# 手动运行
python gex_analysis.py

# 定时任务（推荐通过 cronjob 工具配置）
```

## 重要：API Key 配置

**API Key 不会提交到 GitHub**，通过 `config_local.py` 本地管理：

```python
# config_local.py.example（公开模板）
MARKETDATA_API_KEY = ""      # marketdata.app 免费 Key
TWELVEDATA_API_KEY = ""     # Twelve Data（可选）
PROXY = ""                  # 代理（可选）
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `SPX_GEX_Report.html` | SPX 标普 500 指数 GEX 详细报告 |
| `SPY_GEX_Report.html` | SPY 标普 500 ETF GEX 详细报告 |
| `QQQ_GEX_Report.html` | QQQ 纳斯达克 100 ETF GEX 详细报告 |
| `GARCH_QUANT_GEX_Overview.html` | 三合一总览页面 |

## 报告解读

### 净 GEX（NetGEX）
- **正值**：期权市场整体做多 Gamma，机构倾向于卖出期权（Short Gamma），市场波动被压制
- **负值**：期权市场整体做空 Gamma，机构倾向于买入期权（Long Gamma），波动可能放大

### Gamma 翻转位（Gamma Flip Strike）
- 净 GEX 符号切换的行权价
- 接近该价位时，机构做市商对冲行为最活跃，价格容易出现快速波动
- 常被视为日内交易的关键拐点参考

## 已知限制

- marketdata.app 免费层有频率限制，高频调用可能返回 429
- Yahoo Finance 无需 Key 但经常限流（建议配合代理）
- 不支持夜盘/期货期权的 GEX 计算
- GEX 指标仅反映期权市场的 Gamma 暴露，不构成投资建议

## 版本历史

- **v1.3**：API Key 分离到 `config_local.py`（不提交 GitHub），增加 `.gitignore`
- **v1.2**：多源兜底（marketdata → Yahoo → 合成数据），合成数据明确标注
- **v1.1**：修复原始代码 9 处 HTML 语法错误
