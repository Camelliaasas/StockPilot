"""概率校准：用历史滚动验证数据校准模型置信度（isotonic——说70%真70%）"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
import joblib
from sklearn.isotonic import IsotonicRegression
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FEATS = ['ret', 'ma5', 'ma20', 'ma60', 'macd', 'macd_hist', 'rsi', 'vol_ratio', 'amplitude',
         'macd_golden', 'ma520_bull', 'bull_align', 'mom20', 'bias60', 'hh20_break', 'boll_pos']

def build_calibrator():
    """用历史数据拟合校准器"""
    model = joblib.load('C:/Users/23643/src_workflow/stock_predict/model_index_binary.joblib')
    idx = ak.stock_zh_index_daily(symbol='sh000001')
    df = idx.copy().reset_index(drop=True)
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
    df['fwd_1'] = df['close'].shift(-1) / df['close'] - 1
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=['fwd_1'])
    d2 = df[np.abs(df['fwd_1']) > 0.01]
    X = d2[FEATS].values
    y = (d2['fwd_1'] > 0).astype(int)
    # 训练集（前 60%）
    split = int(len(X) * 0.6)
    proba = model.predict_proba(X[:split])[:, 1]
    iso = IsotonicRegression(out_of_bounds='clip')
    iso.fit(proba, y[:split])
    # 校准验证（后 40%）
    proba_test = model.predict_proba(X[split:])[:, 1]
    cal_test = iso.predict(proba_test)
    bins = [0, 0.5, 0.55, 0.6, 0.7, 1]
    print('📊 校准检查（预测概率 vs 实际上涨率）:')
    print('  概率区间 | 样本 | 实际上涨率 | 校准后概率')
    for i in range(len(bins) - 1):
        mask = (proba_test >= bins[i]) & (proba_test < bins[i + 1])
        if mask.sum() > 0:
            actual = y[split:][mask].mean()
            cal = cal_test[mask].mean()
            print(f'  {bins[i]:.2f}-{bins[i+1]:.2f} | {mask.sum():4d} | {actual*100:5.1f}% | {cal*100:5.1f}%')
    joblib.dump(iso, 'C:/Users/23643/src_workflow/stock_predict/calibrator_index.joblib')
    print('\n✅ 校准器已保存 calibrator_index.joblib')

if __name__ == '__main__':
    build_calibrator()
