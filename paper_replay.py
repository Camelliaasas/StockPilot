"""模拟盘回放：MA(5,10) 策略 2024-2026 历史回放——净值/持仓/交易记录"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SLIPPAGE, FEE = 0.001, 0.00025

def replay(code, name, start='20240101', end='20260810', cash=100000):
    """回放模拟盘：信号→买卖→净值"""
    symbol = ('sh' if code.startswith('6') else 'sz') + code
    try:
        df = ak.stock_zh_a_daily(symbol=symbol, start_date=start, end_date=end, adjust='qfq')
        if df is None or len(df) < 30:
            return None
        df = df.reset_index(drop=True)
        c = df['close']
        ma5 = c.rolling(5).mean()
        ma10 = c.rolling(10).mean()
        cash_f = float(cash)
        shares = 0
        trades = []
        nav_pts = []
        for i in range(1, len(df)):
            price = float(c.iloc[i])
            prev = float(c.iloc[i-1])
            cu = ma5.iloc[i-1] <= ma10.iloc[i-1] and ma5.iloc[i] > ma10.iloc[i]
            cd = ma5.iloc[i-1] >= ma10.iloc[i-1] and ma5.iloc[i] < ma10.iloc[i]
            if cu and shares == 0:
                buy = int(cash_f * 0.95 / price / 100) * 100
                if buy > 0:
                    cost = buy * price * (1 + SLIPPAGE + FEE)
                    if cost <= cash_f:
                        cash_f -= cost
                        shares = buy
                        trades.append({'date': str(df['date'].iloc[i])[:10], 'action': 'BUY', 'price': round(price, 2), 'shares': buy})
            elif cd and shares > 0:
                proceeds = shares * price * (1 - SLIPPAGE - FEE)
                cash_f += proceeds
                trades.append({'date': str(df['date'].iloc[i])[:10], 'action': 'SELL', 'price': round(price, 2), 'shares': shares})
                shares = 0
            if i % 5 == 0:
                nav = cash_f + shares * price
                nav_pts.append((str(df['date'].iloc[i])[:10], round(nav)))
        final_nav = cash_f + shares * price
        ret = (final_nav / cash - 1) * 100
        return {'name': name, 'code': code, 'nav': nav_pts, 'trades': trades[-10:],
                'trades_count': len(trades), 'ret': round(ret, 1), 'final_nav': round(final_nav),
                'holding': shares > 0}
    except Exception as e:
        return {'name': name, 'error': str(e)[:40]}

if __name__ == '__main__':
    for code, name in [('600519', '贵州茅台'), ('300750', '宁德时代'), ('603259', '药明康德')]:
        r = replay(code, name)
        if r and 'error' not in r:
            print(f"{r['name']}: 净值 ¥{r['final_nav']:,} ({r['ret']:+.1f}%) | 交易 {r['trades_count']} 次 | 持仓{'是' if r['holding'] else '否'}")
