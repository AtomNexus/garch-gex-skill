#!/usr/bin/env python3
"""
GARCH QUANT 期权 GEX 分析引擎 v1.3
支持标的: SPX, SPY, QQQ
多源兜底: marketdata.app → Yahoo Finance → 合成演示数据
API Key 通过 config_local.py 本地配置（不提交到 GitHub）
"""

import requests
import pandas as pd
import numpy as np
try:
    import schedule
    import time
except ImportError:
    schedule = None
    time = None
import html
import random
import os
from datetime import datetime, timedelta

# ===================== 核心配置区 =====================
SYMBOLS = ["SPX", "SPY", "QQQ"]
CONTRACT_MULTIPLIER = 100
MARKETDATA_URL = "https://api.marketdata.app/v1/options/chains"
YAHOO_URL = "https://query1.finance.yahoo.com/v7/finance/options"
SAVE_DIR = "./"
RUN_INTERVAL_MIN = 30
BRAND_NAME = "GARCH QUANT"
BRAND_STYLE_COLOR = "#002b5c"
BRAND_ACCENT_COLOR = "#d4af37"
# =====================================================

# 标的价格参考（用于生成合理的合成数据）
REF_PRICES = {"SPX": 5900, "SPY": 590, "QQQ": 2050}

# ---- 本地配置（允许为空，使用合成数据兜底）----
try:
    from config_local import (
        MARKETDATA_API_KEY,
        TWELVEDATA_API_KEY,
        YAHOO_PROXY,
        PROXY,
    )
except ImportError:
    MARKETDATA_API_KEY = os.environ.get("MARKETDATA_API_KEY", "")
    TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY", "")
    YAHOO_PROXY = os.environ.get("YAHOO_PROXY", "")
    PROXY = os.environ.get("PROXY", "")


class GEXAnalysisSkill:
    """期权 GEX 分析 — 多源爬取 + 计算 + HTML 报告"""

    def __init__(self, symbol):
        self.symbol = symbol
        self.contract_multiplier = CONTRACT_MULTIPLIER
        self.brand = BRAND_NAME
        self.is_demo = False

    # ---- 数据获取（多源兜底） ----

    def _fetch_marketdata(self):
        """Source 1: marketdata.app（需要 API Key，免费注册）"""
        if not MARKETDATA_API_KEY:
            print("  [marketdata] 无 API Key，跳过")
            return None
        url = f"{MARKETDATA_URL}/{self.symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Authorization": f"Bearer {MARKETDATA_API_KEY}"
        }
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code != 200:
                print(f"  [marketdata] HTTP {res.status_code}")
                return None
            data = res.json()
            if data.get("s") != "ok" or "strike" not in data:
                print(f"  [marketdata] s={data.get('s')}")
                return None
            return self._normalize_marketdata(data)
        except Exception as e:
            print(f"  [marketdata] 异常: {e}")
            return None

    def _normalize_marketdata(self, data):
        """将 marketdata.app 格式标准化"""
        rows = []
        strikes = data.get("strike", [])
        opt_types = data.get("optionType", [])
        gammas = data.get("gamma", [])
        ois = data.get("openInterest", [])
        for i in range(len(strikes)):
            rows.append({
                "行权价": strikes[i],
                "期权类型": opt_types[i].upper() if isinstance(opt_types[i], str)
                           else ("C" if opt_types[i] == 1 else "P"),
                "Gamma值": float(gammas[i]) if gammas[i] is not None else 0.0,
                "持仓量": int(ois[i]) if ois[i] is not None else 0
            })
        return pd.DataFrame(rows)

    def _fetch_yahoo(self):
        """Source 2: Yahoo Finance options API（无需 Key，但常限流）"""
        proxies = {"http": PROXY, "https": PROXY} if PROXY else None
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        try:
            res = requests.get(
                f"{YAHOO_URL}/{self.symbol}",
                headers=headers, proxies=proxies, timeout=15
            )
            if res.status_code != 200:
                print(f"  [Yahoo] HTTP {res.status_code}")
                return None
            data = res.json()
            result = data.get("optionChain", {}).get("result", [])
            if not result:
                print(f"  [Yahoo] 无 result 数据")
                return None
            opts = result[0].get("options", [{}])[0]
            calls = opts.get("calls", [])
            puts = opts.get("puts", [])
            rows = []
            for c in calls:
                rows.append({
                    "行权价": float(c.get("strike", 0)),
                    "期权类型": "C",
                    "Gamma值": float(c.get("impliedVolatility", 0) * c.get("openInterest", 0) / 1000),
                    "持仓量": int(c.get("openInterest", 0))
                })
            for p in puts:
                rows.append({
                    "行权价": float(p.get("strike", 0)),
                    "期权类型": "P",
                    "Gamma值": float(p.get("impliedVolatility", 0) * p.get("openInterest", 0) / 1000),
                    "持仓量": int(p.get("openInterest", 0))
                })
            if not rows:
                return None
            return pd.DataFrame(rows)
        except Exception as e:
            print(f"  [Yahoo] 异常: {e}")
            return None

    def _generate_demo_data(self):
        """Source 3: 合成演示数据（标注 [DEMO DATA]）"""
        self.is_demo = True
        ref = REF_PRICES.get(self.symbol, 1000)
        strikes = sorted(set([ref + i * ref * 0.01 for i in range(-20, 21)]))
        rows = []
        for k in strikes:
            dist = abs(k - ref) / ref
            gamma_call = random.uniform(0.01, 0.3) * (1 - dist * 2)
            gamma_put = random.uniform(0.01, 0.3) * (1 - dist * 2)
            rows.append({
                "行权价": round(k, 2), "期权类型": "C",
                "Gamma值": max(gamma_call, 0.001),
                "持仓量": random.randint(100, 5000)
            })
            rows.append({
                "行权价": round(k, 2), "期权类型": "P",
                "Gamma值": max(gamma_put, 0.001),
                "持仓量": random.randint(100, 5000)
            })
        return pd.DataFrame(rows)

    def get_option_chain(self):
        """三层兜底获取期权链"""
        df = self._fetch_marketdata()
        if df is not None and not df.empty:
            print(f"  [marketdata.app] {self.symbol}: {len(df)} 条记录")
            return df
        df = self._fetch_yahoo()
        if df is not None and not df.empty:
            print(f"  [Yahoo Finance] {self.symbol}: {len(df)} 条记录")
            return df
        print(f"  [合成演示数据] {self.symbol}: API 不可用，使用 [DEMO DATA]")
        return self._generate_demo_data()

    # ---- GEX 计算 ----

    def calc_gex(self, df):
        """计算 GEX 及 Gamma 翻转位"""
        df = df.copy()
        df["GEX"] = df["Gamma值"] * df["持仓量"] * self.contract_multiplier

        call_df = df[df["期权类型"] == "C"].groupby("行权价")["GEX"].sum()
        put_df = df[df["期权类型"] == "P"].groupby("行权价")["GEX"].sum()

        gex_result = pd.DataFrame(index=sorted(df["行权价"].unique()))
        gex_result["看涨期权GEX(CallGEX)"] = call_df
        gex_result["看跌期权GEX(PutGEX)"] = put_df
        gex_result = gex_result.fillna(0)
        gex_result["净GEX(NetGEX)"] = (
            gex_result["看涨期权GEX(CallGEX)"] +
            gex_result["看跌期权GEX(PutGEX)"]
        ).round(2)

        gex_result["GEX符号"] = np.sign(gex_result["净GEX(NetGEX)"])
        gamma_flip_strikes = gex_result[
            gex_result["GEX符号"].diff() != 0
        ].index.tolist()
        total_net_gex = round(gex_result["净GEX(NetGEX)"].sum(), 2)

        return gex_result, gamma_flip_strikes, total_net_gex

    # ---- HTML 生成 ----

    def generate_brand_html(self, gex_df, flip_strikes, total_net_gex):
        """生成单标的 HTML 报告"""
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        flip_str = html.escape(str(flip_strikes))
        demo_badge = (
            f'<span style="background:#d4af37;color:#002b5c;padding:2px 8px;'
            f'border-radius:4px;font-size:12px;margin-left:8px;">⚠️ [DEMO DATA]</span>'
        ) if self.is_demo else ""
        demo_notice = (
            '<div style="background:#fff3cd;border:1px solid #ffc107;'
            'border-radius:6px;padding:12px;margin-bottom:16px;font-size:14px;color:#856404;">'
            '⚠️ 当前为演示数据（API 不可用或未配置）</div>'
        ) if self.is_demo else ""

        html_content = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self.brand} | {self.symbol} GEX 期权敞口分析</title>
<style>
    * {{margin: 0; padding: 0; box-sizing: border-box;}}
    body {{font-family: 'Microsoft YaHei', Arial, sans-serif; background: #f9fafb; color: #222; line-height: 1.6;}}
    .container {{max-width: 1200px; margin: 30px auto; padding: 0 20px;}}
    .brand-header {{text-align: center; margin-bottom: 20px; padding: 15px;
                    border-bottom: 2px solid {BRAND_ACCENT_COLOR};}}
    .brand-name {{font-size: 28px; font-weight: bold; color: {BRAND_STYLE_COLOR};}}
    .report-title {{font-size: 22px; color: {BRAND_STYLE_COLOR}; margin: 10px 0;}}
    .info-bar {{background: #fff; padding: 15px; border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,43,92,0.08); margin-bottom: 20px;}}
    .info-item {{margin: 8px 0; font-size: 15px;}}
    .flip-info {{color: #cc0000; font-weight: bold;}}
    .gex-table {{width: 100%; border-collapse: collapse; background: #fff;
                 border-radius: 8px; overflow: hidden;
                 box-shadow: 0 2px 8px rgba(0,43,92,0.08);}}
    .gex-table th {{background: {BRAND_STYLE_COLOR}; color: #fff; padding: 12px;
                   text-align: center; font-weight: 500;}}
    .gex-table td {{padding: 10px; text-align: center; border: 1px solid #d0d7de;}}
    .gex-table tr:nth-child(even) {{background: #f6f8fa;}}
    .footer {{text-align: center; margin-top: 30px; padding: 15px;
              color: #666; font-size: 13px;}}
</style>
</head>
<body>
<div class="container">
    <div class="brand-header">
        <div class="brand-name">{self.brand}{demo_badge}</div>
        <h2 class="report-title">{self.symbol} 期权 GEX 敞口分析</h2>
    </div>
    {demo_notice}
    <div class="info-bar">
        <div class="info-item">数据更新时间：{update_time}</div>
        <div class="info-item">全市场总净 GEX：{total_net_gex}</div>
        <div class="info-item flip-info">Gamma 关键翻转行权价：{flip_str}</div>
    </div>
    {gex_df.to_html(classes="gex-table", index=True)}
    <div class="footer">
        © {datetime.now().year} {self.brand} All Rights Reserved | 数据仅供研究分析
    </div>
</div>
</body>
</html>"""
        return html_content

    def run_single_task(self):
        """执行单标的完整分析"""
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] {self.brand} - 开始处理 {self.symbol}...")
            chain_df = self.get_option_chain()
            gex_df, flip_strikes, total_net_gex = self.calc_gex(chain_df)
            html_report = self.generate_brand_html(gex_df, flip_strikes, total_net_gex)
            save_path = f"{SAVE_DIR}{self.symbol}_GEX_Report.html"
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(html_report)
            tag = "⚠️ [DEMO]" if self.is_demo else "✓"
            print(f"[{ts}] {self.brand} - {self.symbol} 报告生成完成 {tag}")
            return True, self.is_demo
        except Exception as e:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] {self.brand} - {self.symbol} 异常：{e}")
            return False, False


def generate_overview_html():
    """生成三合一总览页面"""
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    overview_html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{BRAND_NAME} | 期权 GEX 分析总览</title>
<style>
    * {{margin: 0; padding: 0; box-sizing: border-box;}}
    body {{font-family: 'Microsoft YaHei', Arial, sans-serif; background: #f9fafb; color: #222;}}
    .container {{max-width: 1000px; margin: 50px auto; padding: 0 20px;}}
    .brand-header {{text-align: center; margin-bottom: 40px; padding: 20px;
                    border-bottom: 3px solid {BRAND_ACCENT_COLOR};}}
    .brand-name {{font-size: 36px; font-weight: bold; color: {BRAND_STYLE_COLOR}; margin-bottom: 10px;}}
    .overview-title {{font-size: 24px; color: {BRAND_STYLE_COLOR};}}
    .report-card {{background: #fff; padding: 25px; border-radius: 10px;
                   box-shadow: 0 3px 12px rgba(0,43,92,0.1); margin-bottom: 20px; text-align: center;}}
    .report-link {{display: inline-block; padding: 12px 30px;
                   background: {BRAND_STYLE_COLOR}; color: #fff; text-decoration: none;
                   border-radius: 6px; font-size: 16px; margin: 10px 0; transition: 0.3s;}}
    .report-link:hover {{background: {BRAND_ACCENT_COLOR}; color: #222;}}
    .update-time {{text-align: center; color: #666; margin: 20px 0; font-size: 15px;}}
    .footer {{text-align: center; margin-top: 50px; padding: 20px;
              color: #666; font-size: 14px; border-top: 1px solid #eee;}}
</style>
</head>
<body>
<div class="container">
    <div class="brand-header">
        <div class="brand-name">{BRAND_NAME}</div>
        <h1 class="overview-title">期权 GEX 敞口分析总览</h1>
    </div>
    <div class="update-time">数据最后更新时间：{update_time}</div>

    <div class="report-card">
        <h3>SPX 标普 500 指数</h3>
        <a href="SPX_GEX_Report.html" class="report-link" target="_blank">查看详细报告</a>
    </div>
    <div class="report-card">
        <h3>SPY 标普 500 ETF</h3>
        <a href="SPY_GEX_Report.html" class="report-link">查看详细报告</a>
    </div>
    <div class="report-card">
        <h3>QQQ 纳斯达克 100 ETF</h3>
        <a href="QQQ_GEX_Report.html" class="report-link">查看详细报告</a>
    </div>

    <div class="footer">
        © {datetime.now().year} {BRAND_NAME} All Rights Reserved | 专业量化研究工具 | 数据仅供研究分析
    </div>
</div>
</body>
</html>"""
    with open(f"{SAVE_DIR}GARCH_QUANT_GEX_Overview.html", "w", encoding="utf-8") as f:
        f.write(overview_html)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {BRAND_NAME} 总览页面生成完成 ✓")


def run_all_symbols_task():
    """批量执行 + 生成总览"""
    results = {}
    for symbol in SYMBOLS:
        skill = GEXAnalysisSkill(symbol)
        ok, is_demo = skill.run_single_task()
        results[symbol] = {"ok": ok, "demo": is_demo}
    generate_overview_html()
    return results


if __name__ == "__main__":
    print(f"========== {BRAND_NAME} 期权 GEX 分析引擎 v1.3 启动 ==========")
    run_all_symbols_task()
    if schedule is not None:
        schedule.every(RUN_INTERVAL_MIN).minutes.do(run_all_symbols_task)
        print(f"定时任务已启动，每 {RUN_INTERVAL_MIN} 分钟自动更新")
        print(f"=========================================================\n")
        while True:
            schedule.run_pending()
            time.sleep(10)
    else:
        print("========== 单次运行完成 ==========")
