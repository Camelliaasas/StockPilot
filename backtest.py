"""专业回测引擎：滑点+手续费+基准对比（机构级标准）"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

# 成本参数（机构级）
SLIPPAGE = 0.001   # 滑点 0.1%
FEE_RATE = 0.00025 # 手续费 万2.5

def backtest_strategy(code, name, start='20210101', end='20260810', ma_short=20, ma_long=60):
    """双均线策略回测（含成本）——vs 基准（买入持有）"""
    df = ak.stock_zh_a_daily(symbol=code, start_date=start, end_date=end, adjust='qfq')
    if df is None or len(df) < ma_long + 10:
        return None
    df = df.reset_index(drop=True)
    df['ma_s'] = df['close'].rolling(ma_short).mean()
    df['ma_l'] = df['close'].rolling(ma_long).mean()
    # 策略信号：短期上穿长期 = 买入；下穿 = 卖出
    position = 0
    strat_cap = 1.0  # 策略资金
    hold_cap = 1.0   # 买入持有
    trades = 0
    for i in range(ma_long, len(df)):
        price = df['close'].iloc[i]
        prev = df['close'].iloc[i-1]
        cross_up = df['ma_s'].iloc[i-1] <= df['ma_l'].iloc[i-1] and df['ma_s'].iloc[i] > df['ma_l'].iloc[i]
        cross_down = df['ma_s'].iloc[i-1] >= df['ma_l'].iloc[i-1] and df['ma_s'].iloc[i] < df['ma_l'].iloc[i]
        # 策略
        if cross_up and position == 0:
            strat_cap *= (1 - SLIPPAGE - FEE_RATE)  # 买入成本
            position = 1
            trades += 1
        elif cross_down and position == 1:
            strat_cap *= (1 - SLIPPAGE - FEE_RATE)  # 卖出成本
            strat_cap *= price / prev if prev > 0 else 1
            position = 0
            trades += 1
        if position == 1:
            strat_cap *= (1 + (price - prev) / prev)
        hold_cap *= (1 + (price - prev) / prev)
    # 基准（买入持有）
    n = len(df)
    years = n / 250
    strat_ret = (strat_cap - 1) * 100
    hold_ret = (hold_cap - 1) * 100
    return {
        'code': code, 'name': name,
        'period': f'{df["date"].iloc[0]} ~ {df["date"].iloc[-1]}',
        'trades': trades,
        'strat_ret': round(strat_ret, 2),
        'hold_ret': round(hold_ret, 2),
        'excess': round(strat_ret - hold_ret, 2),
        'annual': round(((strat_cap) ** (1/years) - 1) * 100, 2) if years > 0.5 else None,
        'hold_annual': round(((hold_cap) ** (1/years) - 1) * 100, 2) if years > 0.5 else None,
    }

def main():
    stocks = [('sh600519', '贵州茅台'), ('sz300750', '宁德时代'), ('sz000858', '五粮液'),
              ('sh601318', '中国平安'), ('sh600036', '招商银行'), ('sz002594', '比亚迪'),
              ('sh601012', '隆基绿能'), ('sh603259', '药明康德')]
    print('=' * 60)
    print('📊 专业回测（双均线策略——滑点0.1%+手续费万2.5）')
    print('=' * 60)
    results = []
    for code, name in stocks:
        r = backtest_strategy(code, name)
        if r:
            results.append(r)
            print(f'\n{r["name"]}({r["code"]}) {r["period"]}  交易{r["trades"]}次')
            print(f'  策略: {r["strat_ret"]:+.1f}% (年化{r["annual"]}%)')
            print(f'  持有: {r["hold_ret"]:+.1f}% (年化{r["hold_annual"]}%)')
            print(f'  超额: {r["excess"]:+.1f}%')
    # 汇总
    win = sum(1 for r in results if r['excess'] > 0)
    print(f'\n📈 策略跑赢买入持有: {win}/{len(results)} 只')
    if results:
        avg_excess = np.mean([r['excess'] for r in results])
        print(f'平均超额收益: {avg_excess:+.1f}%')

if __name__ == '__main__':
    main()
