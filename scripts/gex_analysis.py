#!/usr/bin/env python3
"""
GARCH QUANT 期权 GEX 分析引擎
支持标的: SPX, SPY, QQQ
修复版: 修正所有 HTML 语法错误、__name__ 下划线、标签完整性
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
from datetime import datetime

# ===================== 核心配置区 =====================
SYMBOLS = ["SPX", "SPY", "QQQ"]
CONTRACT_MULTIPLIER = 100
BASE_URL = "https://api.marketdata.app/v1/options/chains"
SAVE_DIR = "./"
RUN_INTERVAL_MIN = 30
BRAND_NAME = "GARCH QUANT"
BRAND_STYLE_COLOR = "#002b5c"
BRAND_ACCENT_COLOR = "#d4af37"
# =====================================================


class GEXAnalysisSkill:
    """期权 GEX 分析 — 多标的爬取、计算、HTML 报告生成"""

    def __init__(self, symbol):
        self.symbol = symbol
        self.contract_multiplier = CONTRACT_MULTIPLIER
        self.brand = BRAND_NAME

    def get_option_chain(self):
        """获取期权链原始数据"""
        url = f"{BASE_URL}/{self.symbol}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=20)
        res.raise_for_status()
        data = res.json()
        df = pd.DataFrame({
            "行权价": data["strike"],
            "期权类型": data["optionType"],
            "Gamma值": data["gamma"],
            "持仓量": data["openInterest"]
        })
        return df

    def calc_gex(self, df):
        """计算 GEX 指标及 Gamma 翻转位"""
        df = df.copy()
        df["GEX"] = df["Gamma值"] * df["持仓量"] * self.contract_multiplier

        call_df = df[df["期权类型"] == "C"].groupby("行权价")["GEX"].sum()
        put_df = df[df["期权类型"] == "P"].groupby("行权价")["GEX"].sum()

        gex_result = pd.DataFrame(index=sorted(df["行权价"].unique()))
        gex_result["看涨期权GEX(CallGEX)"] = call_df
        gex_result["看跌期权GEX(PutGEX)"] = put_df
        gex_result = gex_result.fillna(0)
        gex_result["净GEX(NetGEX)"] = (
            gex_result["看涨期权GEX(CallGEX)"] + gex_result["看跌期权GEX(PutGEX)"]
        ).round(2)

        gex_result["GEX符号"] = np.sign(gex_result["净GEX(NetGEX)"])
        gamma_flip_strikes = gex_result[
            gex_result["GEX符号"].diff() != 0
        ].index.tolist()
        total_net_gex = round(gex_result["净GEX(NetGEX)"].sum(), 2)

        return gex_result, gamma_flip_strikes, total_net_gex

    def generate_brand_html(self, gex_df, flip_strikes, total_net_gex):
        """生成单标的 HTML 报告"""
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        flip_str = html.escape(str(flip_strikes))

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
        <div class="brand-name">{self.brand}</div>
        <h2 class="report-title">{self.symbol} 期权 GEX 敞口分析</h2>
    </div>
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
            print(f"[{ts}] {self.brand} - {self.symbol} 报告生成完成 ✓")
            return True
        except Exception as e:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] {self.brand} - {self.symbol} 异常：{e}")
            return False


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
    for symbol in SYMBOLS:
        skill = GEXAnalysisSkill(symbol)
        skill.run_single_task()
    generate_overview_html()


if __name__ == "__main__":
    print(f"========== {BRAND_NAME} 期权 GEX 分析引擎启动 ==========")
    run_all_symbols_task()
    if schedule is not None:
        schedule.every(RUN_INTERVAL_MIN).minutes.do(run_all_symbols_task)
        print(f"定时任务已启动，每 {RUN_INTERVAL_MIN} 分钟自动更新")
        print(f"======================================================\n")
        while True:
            schedule.run_pending()
            time.sleep(10)
    else:
        print("========== 单次运行完成 ==========")
