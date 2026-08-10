"""历史滚动验证：过去 N 天逐日预测→对照实际→真实准确率（今天就出结果）"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
import joblib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    df['vol_ma5'] = df['volume'].rolling(5).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma5'].replace(0, np.nan)
    df['amplitude'] = (df['high'] - df['low']) / df['close']
    df['macd_golden'] = ((df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))).astype(int)
    df['ma520_bull'] = (df['ma5'] > df['ma20']).astype(int)
    df['bull_align'] = ((df['ma5'] > df['ma20']) & (df['ma20'] > df['ma60'])).astype(int)
    df['mom20'] = df['close'].pct_change(20)
    df['bias60'] = (df['close'] - df['ma60']) / df['ma60']
    df['hh20_break'] = (df['close'] > df['close'].rolling(20).max().shift(1)).astype(int)
    # 扩展
    df['boll_pos'] = (df['close'] - df['ma20']) / df['close'].rolling(20).std().replace(0, np.nan)
    low9 = df['low'].rolling(9).min()
    high9 = df['high'].rolling(9).max()
    rsv = (df['close'] - low9) / (high9 - low9).replace(0, np.nan) * 100
    df['kdj_k'] = rsv.ewm(com=2).mean()
    df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_k'].ewm(com=2).mean()
    sign = np.sign(df['close'].diff()).fillna(0)
    df['obv'] = (sign * df['volume']).cumsum()
    df['obv_trend'] = (df['obv'] > df['obv'].rolling(10).mean()).astype(int)
    tp = (df['high'] + df['low'] + df['close']) / 3
    ma_tp = tp.rolling(14).mean()
    md = tp.rolling(14).apply(lambda x: np.abs(x - x.mean()).mean())
    df['cci'] = (tp - ma_tp) / (0.015 * md.replace(0, np.nan))
    df['wr'] = (df['high'].rolling(10).max() - df['close']) / (df['high'].rolling(10).max() - df['low'].rolling(10).min()).replace(0, np.nan) * 100
    df['roc'] = df['close'].pct_change(12) * 100
    df['bias20'] = (df['close'] - df['ma20']) / df['ma20']
    df['wr_oversold'] = (df['wr'] > 80).astype(int)
    df['wr_overbought'] = (df['wr'] < 20).astype(int)
    df['vol_shrink'] = (df['volume'] < df['vol_ma5']).astype(int)
    df['divergence'] = ((df['close'] == df['close'].rolling(10).max()) & (df['vol_shrink'] == 1)).astype(int)
    df['adx'] = 25.0  # 简化（全量计算慢——用中性值）
    df['adx_strong'] = 0
    return df

def validate(days=60):
    """滚动验证：过去 N 天——每天用截至当日数据预测次日"""
    print('📊 历史滚动验证（今天出结果——不等待）')
    print('=' * 56)
    # 模型（30 特征大盘版——优先；降级全市场版）
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model_lgbm_hs300_v2.joblib')
    if not os.path.exists(model_path):
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model_lgbm.joblib')
    model = joblib.load(model_path)
    n_feats = model.n_features_in_
    print(f'模型: {os.path.basename(model_path)}（{n_feats} 特征）')
    # 指数数据
    idx = ak.stock_zh_index_daily(symbol='sh000001')
    idx = idx.reset_index(drop=True)
    df = features(idx)
    # 滚动
    FEATS = ['ret', 'ma5', 'ma20', 'ma60', 'macd', 'macd_hist', 'rsi', 'vol_ratio', 'amplitude',
             'macd_golden', 'ma520_bull', 'bull_align', 'mom20', 'bias60', 'hh20_break',
             'boll_pos', 'kdj_k', 'kdj_j', 'obv_trend', 'cci', 'wr', 'roc', 'bias20',
             'wr_oversold', 'wr_overbought', 'divergence', 'adx', 'adx_strong']
    results = []
    total = 0
    correct = 0
    for i in range(len(df) - days - 1, len(df) - 1):
        row = df.iloc[i]
        actual_ret = float(df['close'].iloc[i + 1] / df['close'].iloc[i] - 1)
        # 特征（模型需要 30——用 28 技术 + 2 财务中性）
        vals = [float(row[f]) if pd.notna(row[f]) else 0.0 for f in FEATS]
        if n_feats > len(vals):
            vals += [1.0, 1.0]  # 财务中性
        x = np.array([vals[:n_feats]])
        x = np.nan_to_num(x, nan=0.0)
        probs = model.predict_proba(x)[0]
        label = int(model.classes_[np.argmax(probs)])  # 0=跌 1=平 2=涨
        pred_dir = '涨' if label == 2 else ('跌' if label == 0 else '平')
        actual_dir = '涨' if actual_ret > 0.01 else ('跌' if actual_ret < -0.01 else '平')
        hit = pred_dir == actual_dir
        total += 1
        correct += 1 if hit else 0
        results.append((str(df['date'].iloc[i + 1])[:10], pred_dir, actual_dir, round(actual_ret * 100, 2), hit))
    acc = correct / total * 100 if total else 0
    print(f'\n📈 验证 {total} 天 | 正确 {correct} | 准确率 {acc:.1f}%')
    print(f'（三分类基准 33%——{acc - 33:+.1f}pp）')
    print()
    print('📋 逐日明细（后 15 天）:')
    for d, p, a, r, h in results[-15:]:
        mark = '✅' if h else '❌'
        print(f'  {d}: 预测[{p}] 实际[{a}]（{r:+.2f}%）{mark}')
    return acc, results

if __name__ == '__main__':
    acc, results = validate(60)
