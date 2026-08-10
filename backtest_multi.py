"""多策略回测对比：动量/RSI/MACD/布林/海龟突破 vs 买入持有"""
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
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    # RSI14
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - 100 / (1 + rs)
    # MACD
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['macd_sig'] = df['macd'].ewm(span=9).mean()
    # 布林
    df['bb_mid'] = df['close'].rolling(20).mean()
    df['bb_std'] = df['close'].rolling(20).std()
    df['bb_up'] = df['bb_mid'] + 2 * df['bb_std']
    df['bb_dn'] = df['bb_mid'] - 2 * df['bb_std']
    # 动量（20日）
    df['mom20'] = df['close'].pct_change(20)
    # 海龟突破（20日新高）
    df['hh20'] = df['close'].rolling(20).max().shift(1)
    return df

def run_strategy(df, signal_fn, label):
    """通用策略回测（含成本）"""
    pos = 0
    cap = 1.0
    hold_cap = 1.0
    trades = 0
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

# 策略信号函数
def sig_momentum(df, i):
    """动量：20日涨幅>8% 持有；<-8% 空仓"""
    if i < 20 or pd.isna(df['mom20'].iloc[i]):
        return 0
    if df['mom20'].iloc[i] > 0.08: return 1
    if df['mom20'].iloc[i] < -0.08: return -1
    return 0

def sig_rsi(df, i):
    """RSI：<30 买入；>70 卖出"""
    if pd.isna(df['rsi'].iloc[i]):
        return 0
    if df['rsi'].iloc[i] < 30: return 1
    if df['rsi'].iloc[i] > 70: return -1
    return 0

def sig_macd(df, i):
    """MACD：金叉买 死叉卖"""
    if i < 2 or pd.isna(df['macd'].iloc[i]):
        return 0
    if df['macd'].iloc[i] > df['macd_sig'].iloc[i] and df['macd'].iloc[i-1] <= df['macd_sig'].iloc[i-1]:
        return 1
    if df['macd'].iloc[i] < df['macd_sig'].iloc[i] and df['macd'].iloc[i-1] >= df['macd_sig'].iloc[i-1]:
        return -1
    return 0

def sig_bollinger(df, i):
    """布林：触下轨买 触上轨卖"""
    if pd.isna(df['bb_dn'].iloc[i]):
        return 0
    if df['close'].iloc[i] <= df['bb_dn'].iloc[i]: return 1
    if df['close'].iloc[i] >= df['bb_up'].iloc[i]: return -1
    return 0

def sig_turtle(df, i):
    """海龟：突破20日新高买；跌破20日最低卖"""
    if i < 20 or pd.isna(df['hh20'].iloc[i]):
        return 0
    if df['close'].iloc[i] > df['hh20'].iloc[i]: return 1
    low20 = df['low'].iloc[i-20:i].min() if i >= 20 else df['low'].iloc[0]
    if df['close'].iloc[i] < low20: return -1
    return 0

STRATEGIES = [('动量', sig_momentum), ('RSI', sig_rsi), ('MACD', sig_macd),
              ('布林', sig_bollinger), ('海龟突破', sig_turtle)]

def main():
    stocks = [('sh600519', '茅台'), ('sz300750', '宁德'), ('sz000858', '五粮液'),
              ('sh601318', '平安'), ('sh600036', '招行'), ('sz002594', '比亚迪'),
              ('sh601012', '隆基'), ('sh603259', '药明')]
    # 汇总矩阵
    summary = {s[0]: {} for s in STRATEGIES}
    print('=' * 70)
    print('📊 多策略回测（2021-2026——滑点0.1%+手续费万2.5）')
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
    print('📈 策略胜率汇总（跑赢买入持有的股票数/8）:')
    for label, _ in STRATEGIES:
        wins = sum(1 for v in summary[label].values() if v > 0)
        avg = np.mean(list(summary[label].values()))
        print(f'  {label}: {wins}/8 跑赢 | 平均超额 {avg:+.1f}%')

if __name__ == '__main__':
    main()
