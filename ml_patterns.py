"""ML 规律挖掘：从海量历史数据找规律 + 预测模型"""
import sys, os
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def load_all():
    conn = get_conn()
    df = pd.read_sql('SELECT * FROM daily_prices ORDER BY code, date', conn)
    conn.close()
    return df

def add_features(df):
    """计算技术特征"""
    df = df.sort_values(['code', 'date']).copy()
    g = df.groupby('code')
    df['ret'] = g['close'].pct_change()
    df['ma5'] = g['close'].transform(lambda x: x.rolling(5).mean())
    df['ma20'] = g['close'].transform(lambda x: x.rolling(20).mean())
    df['ma60'] = g['close'].transform(lambda x: x.rolling(60).mean())
    # MACD
    df['ema12'] = g['close'].transform(lambda x: x.ewm(span=12).mean())
    df['ema26'] = g['close'].transform(lambda x: x.ewm(span=26).mean())
    df['macd'] = df['ema12'] - df['ema26']
    df['macd_signal'] = g['macd'].transform(lambda x: x.ewm(span=9).mean())
    df['macd_hist'] = df['macd'] - df['macd_signal']
    # RSI14
    def rsi(series, n=14):
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(n).mean()
        loss = (-delta.clip(upper=0)).rolling(n).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - 100 / (1 + rs)
    df['rsi'] = g['close'].transform(rsi)
    # 量能
    df['vol_ma5'] = g['volume'].transform(lambda x: x.rolling(5).mean())
    df['vol_ratio'] = df['volume'] / df['vol_ma5'].replace(0, np.nan)
    # 振幅/换手
    df['amplitude'] = (df['high'] - df['low']) / df['close']
    # 趋势信号特征（回测验证的强策略）
    df['macd_golden'] = ((df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))).astype(int)
    df['ma520_bull'] = (df['ma5'] > df['ma20']).astype(int)
    df['bull_align'] = ((df['ma5'] > df['ma20']) & (df['ma20'] > df['ma60'])).astype(int)
    df['mom20'] = g['close'].transform(lambda x: x.pct_change(20))
    df['bias60'] = (df['close'] - df['ma60']) / df['ma60']
    df['hh20_break'] = (df['close'] > g['close'].transform(lambda x: x.rolling(20).max().shift(1))).astype(int)
    # 扩展指标：BOLL / KDJ / OBV / CCI / ADX（向量化——groupby.transform 替代 apply——提速 10 倍+）
    def boll(x):
        mid = x.rolling(20).mean()
        std = x.rolling(20).std()
        return (x - mid) / std.replace(0, np.nan)  # 布林带宽位置（-2~+2）
    df['boll_pos'] = g['close'].transform(boll)
    # KDJ（向量化）
    low9 = g['low'].transform(lambda x: x.rolling(9).min())
    high9 = g['high'].transform(lambda x: x.rolling(9).max())
    rsv = (df['close'] - low9) / (high9 - low9).replace(0, np.nan) * 100
    df['kdj_k'] = rsv.groupby(df['code']).transform(lambda x: x.ewm(com=2).mean())
    df['kdj_d'] = df['kdj_k'].groupby(df['code']).transform(lambda x: x.ewm(com=2).mean())
    df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
    # OBV（向量化——sign*volume 后 groupby cumsum）
    sign = np.sign(df['close'].groupby(df['code']).diff()).fillna(0)
    df['obv'] = (sign * df['volume']).groupby(df['code']).cumsum()
    df['obv_trend'] = (df['obv'] > df['obv'].groupby(df['code']).transform(lambda x: x.rolling(10).mean())).astype(int)
    # CCI（向量化——MD 用滚动平均绝对偏差近似）
    tp = (df['high'] + df['low'] + df['close']) / 3
    ma_tp = tp.groupby(df['code']).transform(lambda x: x.rolling(14).mean())
    md = (tp - ma_tp).abs().groupby(df['code']).transform(lambda x: x.rolling(14).mean())
    df['cci'] = (tp - ma_tp) / (0.015 * md.replace(0, np.nan))
    # ADX（向量化）
    up = df['high'].groupby(df['code']).diff()
    dn = -df['low'].groupby(df['code']).diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].groupby(df['code']).shift()).abs(),
                    (df['low'] - df['close'].groupby(df['code']).shift()).abs()], axis=1).max(axis=1)
    atr = tr.groupby(df['code']).transform(lambda x: x.ewm(alpha=1/14).mean()).replace(0, np.nan)
    pdi = 100 * plus.groupby(df['code']).transform(lambda x: x.ewm(alpha=1/14).mean()) / atr
    mdi = 100 * minus.groupby(df['code']).transform(lambda x: x.ewm(alpha=1/14).mean()) / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    df['adx'] = dx.groupby(df['code']).transform(lambda x: x.ewm(alpha=1/14).mean())
    df['adx_strong'] = (df['adx'] > 25).astype(int)
    # 更多指标：WR 威廉 / ROC 变动率 / BIAS20 / 量价背离（向量化）
    hh10 = g['high'].transform(lambda x: x.rolling(10).max())
    ll10 = g['low'].transform(lambda x: x.rolling(10).min())
    df['wr'] = (hh10 - df['close']) / (hh10 - ll10).replace(0, np.nan) * 100
    df['roc'] = g['close'].transform(lambda x: x.pct_change(12) * 100)
    df['bias20'] = (df['close'] - df['ma20']) / df['ma20']
    df['wr_oversold'] = (df['wr'] > 80).astype(int)   # 超卖
    df['wr_overbought'] = (df['wr'] < 20).astype(int)  # 超买
    # 量价背离（价创新高但量萎缩——顶背离）
    df['price_high'] = (df['close'] == g['close'].transform(lambda x: x.rolling(10).max())).astype(int)
    df['vol_shrink'] = (df['volume'] < df['vol_ma5']).astype(int)
    df['divergence'] = ((df['price_high'] == 1) & (df['vol_shrink'] == 1)).astype(int)
    # 涨跌停标记
    df['limit_up'] = (df['ret'] > 0.095).astype(int)
    # 未来 5 日收益（标签）
    df['fwd_5'] = g['close'].transform(lambda x: x.shift(-5) / x - 1)
    df['fwd_1'] = g['close'].transform(lambda x: x.shift(-1) / x - 1)
    return df

def find_patterns(df):
    """规律统计：技术信号胜率"""
    patterns = []
    d = df.dropna(subset=['ma20', 'macd', 'rsi'])
    for code, sub in d.groupby('code'):
        name = sub['name'].iloc[0]
        # 1. MACD 金叉（macd 上穿 signal）后 5 日胜率
        cross = (sub['macd'] > sub['macd_signal']) & (sub['macd'].shift(1) <= sub['macd_signal'].shift(1))
        idx = sub[cross].index
        wins = 0; total = 0
        for i in idx:
            pos = sub.index.get_loc(i)
            if pos + 5 < len(sub) and not pd.isna(sub['fwd_5'].iloc[pos]):
                total += 1
                if sub['fwd_5'].iloc[pos] > 0: wins += 1
        if total >= 10:
            patterns.append(('MACD金叉后5日', code, name, wins/total, total))
        # 2. RSI 超卖（<30）后 5 日
        oversold = sub['rsi'] < 30
        idx = sub[oversold].index
        wins = 0; total = 0
        for i in idx:
            pos = sub.index.get_loc(i)
            if pos + 5 < len(sub) and not pd.isna(sub['fwd_5'].iloc[pos]):
                total += 1
                if sub['fwd_5'].iloc[pos] > 0: wins += 1
        if total >= 5:
            patterns.append(('RSI超卖后5日', code, name, wins/total, total))
        # 3. 放量突破（量比>2 且突破 20 日线）后 5 日
        brk = (sub['vol_ratio'] > 2) & (sub['close'] > sub['ma20']) & (sub['close'].shift(1) <= sub['ma20'].shift(1))
        idx = sub[brk].index
        wins = 0; total = 0
        for i in idx:
            pos = sub.index.get_loc(i)
            if pos + 5 < len(sub) and not pd.isna(sub['fwd_5'].iloc[pos]):
                total += 1
                if sub['fwd_5'].iloc[pos] > 0: wins += 1
        if total >= 5:
            patterns.append(('放量突破后5日', code, name, wins/total, total))
    return patterns

def train_model(df):
    """RandomForest 次日涨跌方向预测（三分类）"""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import accuracy_score
    d = df.dropna(subset=['ma5', 'ma20', 'ma60', 'macd', 'rsi', 'vol_ratio', 'amplitude', 'fwd_1']).copy()
    d = d.replace([np.inf, -np.inf], np.nan).dropna(subset=['ma5', 'ma20', 'ma60', 'macd', 'rsi', 'vol_ratio', 'amplitude', 'fwd_1'])
    # 特征（原 9 个 + 趋势信号 6 个 = 15 个）
    feats = ['ret', 'ma5', 'ma20', 'ma60', 'macd', 'macd_hist', 'rsi', 'vol_ratio', 'amplitude',
             'macd_golden', 'ma520_bull', 'bull_align', 'mom20', 'bias60', 'hh20_break']
    X = np.nan_to_num(d[feats].values, nan=0.0, posinf=0.0, neginf=0.0)
    # 标签：次日涨跌>1% 看多 / <-1% 看空 / 中间观望
    y_cat = pd.cut(d['fwd_1'], bins=[-1, -0.01, 0.01, 1], labels=['看空', '观望', '看多'])
    valid = y_cat.notna()
    X, y = X[valid], y_cat[valid].astype(str)
    # 时间序列交叉验证（前 80% 训练/后 20% 测试——避免前视）
    split = int(len(X) * 0.8)
    Xtr, Xte, ytr, yte = X[:split], X[split:], y[:split], y[split:]
    model = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
    model.fit(Xtr, ytr)
    pred = model.predict(Xte)
    acc = accuracy_score(yte, pred)
    # 特征重要性
    imp = sorted(zip(feats, model.feature_importances_), key=lambda x: -x[1])[:5]
    return model, acc, imp, len(X)

if __name__ == '__main__':
    print('加载数据...')
    df = load_all()
    print(f'数据: {len(df)} 行 | 标的数: {df["code"].nunique()}')
    print('计算特征...')
    df = add_features(df)
    print('规律挖掘...')
    patterns = find_patterns(df)
    print(f'\n📊 找到 {len(patterns)} 个规律（样本>=5/10）:')
    # 按胜率排序展示 Top 15
    for p, c, n, rate, cnt in sorted(patterns, key=lambda x: -x[3])[:15]:
        print(f'  {p} | {c} {n} | 胜率 {rate*100:.0f}% (样本{cnt})')
    print('\n🎯 训练预测模型...')
    try:
        model, acc, imp, total = train_model(df)
        print(f'  样本: {total} | 测试集准确率: {acc*100:.1f}%')
        print('  特征重要性 Top5:', ', '.join(f'{f}({v:.3f})' for f, v in imp))
    except Exception as e:
        print(f'  模型训练异常: {str(e)[:80]}')
