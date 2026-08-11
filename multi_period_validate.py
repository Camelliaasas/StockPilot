"""多时段验证：3日预测在多个历史时间段（牛/熊/震荡市）的准确率——找稳定规律"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import accuracy_score
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FEATS = ['ret', 'ma5', 'ma20', 'ma60', 'macd', 'macd_hist', 'rsi', 'vol_ratio', 'amplitude',
         'macd_golden', 'ma520_bull', 'bull_align', 'mom20', 'bias60', 'hh20_break', 'boll_pos']

def features(df):
    df = df.copy().reset_index(drop=True)
    df['ret'] = df['close'].pct_change()
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - 100 / (1 + rs)
    df['vol_ratio'] = df['volume'] / df['volume'].rolling(5).mean().replace(0, np.nan)
    df['amplitude'] = (df['high'] - df['low']) / df['close']
    df['macd_golden'] = ((df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))).astype(int)
    df['ma520_bull'] = (df['ma5'] > df['ma20']).astype(int)
    df['bull_align'] = ((df['ma5'] > df['ma20']) & (df['ma20'] > df['ma60'])).astype(int)
    df['mom20'] = df['close'].pct_change(20)
    df['bias60'] = (df['close'] - df['ma60']) / df['ma60']
    df['hh20_break'] = (df['close'] > df['close'].rolling(20).max().shift(1)).astype(int)
    df['boll_pos'] = (df['close'] - df['ma20']) / df['close'].rolling(20).std().replace(0, np.nan)
    return df

# 多时段（覆盖牛/熊/震荡——用滚动训练：每时段用前 60% 训练、后 40% 验证）
PERIODS = [
    ('2016-2018 震荡', '20160101', '20181231'),
    ('2019-2021 牛+震荡', '20190101', '20211231'),
    ('2022-2023 熊', '20220101', '20231231'),
    ('2024-2026 震荡', '20240101', '20260810'),
]

def validate_period(df_all, label, start, end):
    df = df_all[(df_all['date'] >= start) & (df_all['date'] <= end)].copy()
    if len(df) < 300:
        return None
    df = features(df)
    df['fwd_3'] = df['close'].shift(-3) / df['close'] - 1
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=['fwd_3'])
    d2 = df[np.abs(df['fwd_3']) > 0.02]
    if len(d2) < 150:
        d2 = df
    X = np.nan_to_num(d2[FEATS].values, nan=0.0)
    y = (d2['fwd_3'] > 0).astype(int)
    split = int(len(X) * 0.6)
    m = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=31, max_depth=8, random_state=42, n_jobs=-1, verbose=-1)
    m.fit(X[:split], y[:split])
    acc = accuracy_score(y[split:], m.predict(X[split:]))
    # 市场环境（该时段指数涨跌）
    total_ret = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100
    return {'period': label, 'ret': round(total_ret, 1), 'samples': len(d2),
            'train': split, 'acc': round(acc * 100, 1), 'excess': round((acc - 0.5) * 100, 1)}

def main():
    print('📊 多时段验证（3 日预测——各市场环境准确率）')
    print('=' * 60)
    idx = ak.stock_zh_index_daily(symbol='sh000001')
    idx['date'] = idx['date'].astype(str).str[:10]
    results = []
    for label, start, end in PERIODS:
        r = validate_period(idx, label, start, end)
        if r:
            results.append(r)
            env = '牛' if r['ret'] > 20 else ('熊' if r['ret'] < -10 else '震荡')
            print(f"\n【{r['period']}】指数{r['ret']:+.0f}% ({env}市) | 样本{r['samples']}")
            print(f"  训练{r['train']} → 验证准确率 {r['acc']}% ({r['excess']:+.1f}pp vs 基准50%)")
    print('\n' + '=' * 60)
    avg = np.mean([r['acc'] for r in results])
    best = max(results, key=lambda x: x['acc'])
    worst = min(results, key=lambda x: x['acc'])
    print(f'平均准确率: {avg:.1f}% | 最佳: {best["period"]} ({best["acc"]}%) | 最差: {worst["period"]} ({worst["acc"]}%)')
    print('💡 规律: 看哪个市场环境最准——模型在什么环境可靠')

if __name__ == '__main__':
    main()
