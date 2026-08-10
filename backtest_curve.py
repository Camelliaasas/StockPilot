"""策略净值曲线：MA(5,10) 回测净值序列（2021-2026）——可视化"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SLIPPAGE, FEE = 0.001, 0.00025

def curve(code, name, start='20210101', end='20260810'):
    """MA(5,10) 净值序列（策略 vs 买入持有）"""
    symbol = ('sh' if code.startswith('6') else 'sz') + code
    try:
        df = ak.stock_zh_a_daily(symbol=symbol, start_date=start, end_date=end, adjust='qfq')
        if df is None or len(df) < 30:
            return None
        df = df.reset_index(drop=True)
        c = df['close']
        ma5 = c.rolling(5).mean()
        ma10 = c.rolling(10).mean()
        pos = 0
        strat = 1.0
        hold = 1.0
        dates, s_nav, h_nav = [], [], []
        for i in range(1, len(df)):
            p, prev = c.iloc[i], c.iloc[i-1]
            cu = ma5.iloc[i-1] <= ma10.iloc[i-1] and ma5.iloc[i] > ma10.iloc[i]
            cd = ma5.iloc[i-1] >= ma10.iloc[i-1] and ma5.iloc[i] < ma10.iloc[i]
            if cu and pos == 0:
                strat *= (1 - SLIPPAGE - FEE); pos = 1
            elif cd and pos == 1:
                strat *= (1 - SLIPPAGE - FEE); pos = 0
            if pos == 1 and prev > 0:
                strat *= p / prev
            if prev > 0:
                hold *= p / prev
            dates.append(str(df['date'].iloc[i])[:10])
            s_nav.append(round(strat, 3))
            h_nav.append(round(hold, 3))
        # 采样（每 10 天一点——避免数据太多）
        return {'name': name, 'dates': dates[::10], 'strat': s_nav[::10], 'hold': h_nav[::10],
                'strat_ret': round((strat - 1) * 100, 1), 'hold_ret': round((hold - 1) * 100, 1)}
    except Exception as e:
        return {'name': name, 'error': str(e)[:40]}

if __name__ == '__main__':
    for code, name in [('600519', '贵州茅台'), ('300750', '宁德时代')]:
        r = curve(code, name)
        if r and 'error' not in r:
            print(f"{r['name']}: 策略{r['strat_ret']:+.1f}% vs 持有{r['hold_ret']:+.1f}% | {len(r['dates'])} 点")
