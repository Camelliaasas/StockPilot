"""三测试版预测：A技术ML / B新闻LLM / C综合——预测明日(8-11)上证方向——封存验证"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

# ── 1. 拉当前数据（指数 + 茅台）──
idx = ak.stock_zh_index_daily(symbol='sh000001')
idx = idx.tail(120)  # 近 120 日（特征计算用）
mt = ak.stock_zh_a_daily(symbol='sh600519', start_date='20260101', end_date='20260810', adjust='qfq')

# ── 2. 特征计算（当前状态）──
def features(df):
    df = df.copy().reset_index(drop=True)
    df['ret'] = df['close'].pct_change()
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
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
    df['fwd_1'] = df['close'].shift(-1) / df['close'] - 1
    return df

# ── 版 A：ML 技术模型（历史库训练——当前特征预测）──
def predict_ml():
    from sklearn.ensemble import RandomForestClassifier
    conn = get_conn()
    hist = pd.read_sql("SELECT code, date, open, high, low, close, volume, amount FROM daily_prices ORDER BY code, date", conn)
    conn.close()
    # 用所有股票训练（特征→次日方向）
    h = features(hist)
    feats = ['ret', 'ma5', 'ma20', 'macd', 'macd_hist', 'rsi', 'vol_ratio', 'amplitude']
    d = h.dropna(subset=feats + ['fwd_1']).copy()
    d = d.replace([np.inf, -np.inf], np.nan).dropna(subset=feats + ['fwd_1'])
    X = np.nan_to_num(d[feats].values, nan=0.0, posinf=0.0, neginf=0.0)
    y_cat = pd.cut(d['fwd_1'], bins=[-1, -0.01, 0.01, 1], labels=['看空', '观望', '看多'])
    valid = y_cat.notna()
    X, y = X[valid], y_cat[valid].astype(str)
    model = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
    model.fit(X, y)
    # 当前指数特征
    cur = features(idx)
    row = cur.iloc[-1]
    x = np.array([[row['ret'] if not pd.isna(row['ret']) else 0,
                   row['ma5'] if not pd.isna(row['ma5']) else 0,
                   row['ma20'] if not pd.isna(row['ma20']) else 0,
                   row['macd'] if not pd.isna(row['macd']) else 0,
                   row['macd_hist'] if not pd.isna(row['macd_hist']) else 0,
                   row['rsi'] if not pd.isna(row['rsi']) else 50,
                   row['vol_ratio'] if not pd.isna(row['vol_ratio']) else 1,
                   row['amplitude'] if not pd.isna(row['amplitude']) else 0.02]])
    proba = model.predict_proba(x)[0]
    probs = {c: float(p) for c, p in zip(model.classes_, proba)}
    return probs, model

# ── 版 B：LLM 新闻分析（分析师角色——手动分析今日新闻）──
def analyze_news():
    """分析师角色分析（基于今日已抓新闻——8-10 上午）"""
    # 今日新闻要点（已抓取）：
    news = [
        ('地缘缓和', '特朗普倾向对伊朗经济施压而非军事打击——地缘风险下降'),
        ('科技强势', '港股科技反弹/南向抢筹半导体/大摩预计云资本开支2027+29%'),
        ('医药利好', '药明康德创历史新高——港股医药外包全线上涨'),
        ('消费电子', '苹果折叠iPhone规划到第三代——全球份额或超华为'),
        ('短期扰动', '台风致1943航班取消——北京启动防汛二级响应'),
        ('存储突破', '国产存储产业突围——半导体国产化'),
    ]
    pos = ['地缘缓和', '科技强势', '医药利好', '消费电子', '存储突破']
    neg = ['短期扰动']
    pos_score = len([n for n in news if n[0] in pos]) * 2
    neg_score = len([n for n in news if n[0] in neg]) * 1
    net = pos_score - neg_score
    if net >= 3:
        return '看多', 0.75, news
    elif net <= -2:
        return '看空', 0.7, news
    else:
        return '观望', 0.5, news

# ── 执行 ──
print('═' * 50)
print('📊 三测试版预测——明日(2026-08-11 周二)上证方向')
print('═' * 50)

# 版 A
try:
    probs, model = predict_ml()
    a_dir = max(probs, key=probs.get)
    a_conf = probs[a_dir]
    print(f'\n【版A·ML技术模型】')
    print(f'  预测: {a_dir} | 概率: {dict(sorted(probs.items(), key=lambda x: -x[1]))}')
except Exception as e:
    print(f'\n【版A·ML】失败: {str(e)[:80]}')
    a_dir, a_conf = '观望', 0.5
    probs = {}

# 版 B
b_dir, b_conf, news_list = analyze_news()
print(f'\n【版B·LLM新闻分析】')
for k, v in news_list:
    print(f'  [{k}] {v[:40]}')
print(f'  预测: {b_dir} | 置信度: {b_conf*100:.0f}%')

# 版 C：综合
if probs:
    # A 权重 0.4 + B 权重 0.6（新闻面优先——专业判断）
    scores = {'看多': probs.get('看多', 0)*0.4 + (1 if b_dir=='看多' else 0)*0.6*b_conf,
              '看空': probs.get('看空', 0)*0.4 + (1 if b_dir=='看空' else 0)*0.6*b_conf,
              '观望': probs.get('观望', 0)*0.4 + (1 if b_dir=='观望' else 0)*0.6*b_conf}
    c_dir = max(scores, key=scores.get)
    c_conf = scores[c_dir]
else:
    c_dir, c_conf = b_dir, b_conf
print(f'\n【版C·综合(A40%+B60%)】')
print(f'  预测: {c_dir} | 置信度: {c_conf*100:.0f}%')

# 封存预测
conn = get_conn()
for ver, d, conf in [('A', a_dir, a_conf), ('B', b_dir, b_conf), ('C', c_dir, c_conf)]:
    conn.execute('INSERT INTO predictions (date, code, direction, confidence, reason) VALUES (?,?,?,?,?)',
                 ('2026-08-10', f'VER-{ver}', d, conf, '预测2026-08-11上证方向'))
conn.commit()
conn.close()
print('\n✅ 三版预测已封存（predictions 表——明日对照实际）')
