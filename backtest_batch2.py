"""第二批策略回测：双均线5/20 / 多头排列 / MACD+RSI过滤 / 超跌反弹 / 放量突破"""
import akshare as ak
import pandas as pd
import numpy as np

SLIPPAGE = 0.001
FEE_RATE = 0.00025

def load_data(code, start='20210101', end='20260810'):
    df = ak.stock_zh_a_daily(symbol=code, start_date=start, end_date=end, adjust='qfq')
    if df is None or len(df) < 100:
        return None
    df = df.reset_index(drop=True)
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - 100 / (1 + rs)
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['macd_sig'] = df['macd'].ewm(span=9).mean()
    df['vol_ma5'] = df['volume'].rolling(5).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma5'].replace(0, np.nan)
    df['hh20'] = df['close'].rolling(20).max().shift(1)
    # 乖离率（相对60日均线）
    df['bias60'] = (df['close'] - df['ma60']) / df['ma60']
    return df

def run_strategy(df, signal_fn, label):
    pos = 0; cap = 1.0; hold_cap = 1.0; trades = 0
    for i in range(1, len(df)):
        price = df['close'].iloc[i]
        prev = df['close'].iloc[i-1]
        sig = signal_fn(df, i)
        if sig == 1 and pos == 0:
            cap *= (1 - SLIPPAGE - FEE_RATE)
            pos = 1; trades += 1
        elif sig == -1 and pos == 1:
            cap *= (1 - SLIPPAGE - FEE_RATE)
            pos = 0; trades += 1
        if pos == 1 and prev > 0:
            cap *= price / prev
        if prev > 0:
            hold_cap *= price / prev
    return {'label': label, 'strat': (cap-1)*100, 'hold': (hold_cap-1)*100,
            'excess': (cap-hold_cap)*100, 'trades': trades}

# 策略 1：双均线 5/20（短线趋势）
def sig_ma520(df, i):
    if i < 20 or pd.isna(df['ma5'].iloc[i]):
        return 0
    if df['ma5'].iloc[i] > df['ma20'].iloc[i] and df['ma5'].iloc[i-1] <= df['ma20'].iloc[i-1]:
        return 1
    if df['ma5'].iloc[i] < df['ma20'].iloc[i] and df['ma5'].iloc[i-1] >= df['ma20'].iloc[i-1]:
        return -1
    return 0

# 策略 2：均线多头排列（MA5>MA20>MA60 持有）
def sig_bull(df, i):
    if i < 60 or pd.isna(df['ma60'].iloc[i]):
        return 0
    if df['ma5'].iloc[i] > df['ma20'].iloc[i] > df['ma60'].iloc[i]:
        return 1
    if df['ma5'].iloc[i] < df['ma20'].iloc[i] < df['ma60'].iloc[i]:
        return -1
    return 0

# 策略 3：MACD 金叉 + RSI 过滤（RSI<75 才买——滤掉过热假信号）
def sig_macd_rsi(df, i):
    if i < 2 or pd.isna(df['macd'].iloc[i]):
        return 0
    golden = df['macd'].iloc[i] > df['macd_sig'].iloc[i] and df['macd'].iloc[i-1] <= df['macd_sig'].iloc[i-1]
    death = df['macd'].iloc[i] < df['macd_sig'].iloc[i] and df['macd'].iloc[i-1] >= df['macd_sig'].iloc[i-1]
    if golden and df['rsi'].iloc[i] < 75:
        return 1
    if death and df['rsi'].iloc[i] > 40:
        return -1
    return 0

# 策略 4：超跌反弹（乖离率<-20% 买入——跌过头；>20% 卖出）
def sig_bias(df, i):
    if pd.isna(df['bias60'].iloc[i]):
        return 0
    if df['bias60'].iloc[i] < -0.20:
        return 1
    if df['bias60'].iloc[i] > 0.20:
        return -1
    return 0

# 策略 5：放量突破（量比>2 且突破 20 日高——买入；跌破 20 日低——卖出）
def sig_vol_break(df, i):
    if i < 20 or pd.isna(df['hh20'].iloc[i]):
        return 0
    if df['close'].iloc[i] > df['hh20'].iloc[i] and df['vol_ratio'].iloc[i] > 1.5:
        return 1
    low20 = df['low'].iloc[i-20:i].min() if i >= 20 else df['low'].iloc[0]
    if df['close'].iloc[i] < low20:
        return -1
    return 0

STRATEGIES = [('双均线5/20', sig_ma520), ('多头排列', sig_bull),
              ('MACD+RSI过滤', sig_macd_rsi), ('超跌反弹', sig_bias), ('放量突破', sig_vol_break)]

def main():
    stocks = [('sh600519', '茅台'), ('sz300750', '宁德'), ('sz000858', '五粮液'),
              ('sh601318', '平安'), ('sh600036', '招行'), ('sz002594', '比亚迪'),
              ('sh601012', '隆基'), ('sh603259', '药明')]
    summary = {s[0]: {} for s in STRATEGIES}
    print('=' * 70)
    print('📊 第二批策略回测（2021-2026——滑点0.1%+手续费万2.5）')
    print('=' * 70)
    for code, name in stocks:
        df = load_data(code)
        if df is None:
            continue
        print(f'\n--- {name} ---')
        for label, fn in STRATEGIES:
            r = run_strategy(df, fn, label)
            summary[label][code] = r['excess']
            print(f'  {label}: 策略{r["strat"]:+.1f}% | 持有{r["hold"]:+.1f}% | 超额{r["excess"]:+.1f}% (交易{r["trades"]}次)')
    print('\n' + '=' * 70)
    print('📈 策略胜率汇总:')
    for label, _ in STRATEGIES:
        wins = sum(1 for v in summary[label].values() if v > 0)
        avg = np.mean(list(summary[label].values()))
        print(f'  {label}: {wins}/8 跑赢 | 平均超额 {avg:+.1f}%')

if __name__ == '__main__':
    main()
