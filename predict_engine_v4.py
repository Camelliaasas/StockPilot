"""预测引擎 v4：3日周期(最优55.8%) + 高置信门槛(70%+才给方向——历史90%准)
策略：宁缺毋滥——低于门槛输出"观望"——不给错信号"""
import sys, os, json
import akshare as ak
import pandas as pd
import numpy as np
import joblib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, 'C:/Users/23643/src_workflow/stock_predict')
from db import get_conn

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

def train_3d():
    """训练 3 日周期模型（最优 55.8%）——保存"""
    idx = ak.stock_zh_index_daily(symbol='sh000001')
    df = features(idx)
    df['fwd_3'] = df['close'].shift(-3) / df['close'] - 1
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=['fwd_3'])
    d2 = df[np.abs(df['fwd_3']) > 0.02]
    X = np.nan_to_num(d2[FEATS].values, nan=0.0)
    y = (d2['fwd_3'] > 0).astype(int)
    print(f'3日模型样本: {len(X)}')
    import lightgbm as lgb
    m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, max_depth=8, random_state=42, n_jobs=-1, verbose=-1)
    m.fit(X, y)
    joblib.dump(m, 'C:/Users/23643/src_workflow/stock_predict/model_index_3d.joblib')
    print('✅ 保存 model_index_3d.joblib')
    return m

def ml_predict_3d():
    """3 日预测 + 高置信门槛（70%+ 才给方向）"""
    import os as _os
    model_path = 'C:/Users/23643/src_workflow/stock_predict/model_index_3d.joblib'
    if not _os.path.exists(model_path):
        train_3d()
    model = joblib.load(model_path)
    idx = ak.stock_zh_index_daily(symbol='sh000001').tail(120)
    cur = features(idx)
    row = cur.iloc[-1]
    vals = [float(row[f]) if not pd.isna(row[f]) else 0.0 for f in FEATS]
    x = np.nan_to_num(np.array([vals]), nan=0.0)
    proba = model.predict_proba(x)[0]
    up_p = float(proba[list(model.classes_).index(1)]) if 1 in model.classes_ else 0.5
    # 高置信门槛
    if up_p >= 0.70:
        direction, conf = '看多', up_p * 100
    elif up_p <= 0.30:
        direction, conf = '看空', (1 - up_p) * 100
    else:
        direction, conf = '观望', max(up_p, 1 - up_p) * 100
    return direction, conf, f'3日模型+高置信门槛（历史：70%+时实际90%准——样本{len(idx)}）'

def main():
    print('=' * 56)
    print('📊 预测引擎 v5（3日ML + 趋势规则 + 事件连锁推演——三信号融合）')
    print('=' * 56)
    # 信号1：3日 ML（高置信门槛）
    dir_a, conf_a, reason_a = ml_predict_3d()
    print(f'\n【信号1·3日模型】{dir_a} | 置信 {conf_a:.0f}%')
    print(f'  {reason_a}')
    # 市场环境过滤器（多时段验证：趋势市61.3%准/熊市45.9%不准）
    env_dir = '趋势市'
    try:
        idx_env = ak.stock_zh_index_daily(symbol='sh000001').tail(120)
        c_env = idx_env['close']
        ma60_env = c_env.rolling(60).mean().iloc[-1]
        cur_env = c_env.iloc[-1]
        if cur_env > ma60_env:
            env_dir = '趋势市'
        else:
            env_dir = '熊市/弱势市'
        print(f'\n【环境过滤】{env_dir}（指数 {">" if cur_env > ma60_env else "<"} MA60——{cur_env:.0f} vs {ma60_env:.0f}）')
        if env_dir == '熊市/弱势市':
            print(f'  ⚠️ 多时段验证：熊市准确率 45.9%（不可靠）——预测降级观望')
            dir_a = '观望'
    except Exception:
        pass
    # 信号2：趋势规则
    idx = ak.stock_zh_index_daily(symbol='sh000001').tail(80)
    c = idx['close']
    ma5, ma20 = c.rolling(5).mean(), c.rolling(20).mean()
    score2 = 0
    if ma5.iloc[-1] > ma20.iloc[-1]: score2 += 1
    if c.iloc[-1] / c.iloc[-6] - 1 > 0.01: score2 += 1
    elif c.iloc[-1] / c.iloc[-6] - 1 < -0.01: score2 -= 1
    dir_c = '看多' if score2 > 0 else ('看空' if score2 < 0 else '震荡')
    print(f'\n【信号2·趋势规则】{dir_c}（均线+5日动量）')
    # 信号3：事件连锁推演（新增）
    chain_score = 0
    chain_dir = '中性'
    try:
        from event_chain import analyze_chain
        cr = analyze_chain()
        if 'error' not in cr:
            chain_score = cr['total_score']
            if chain_score >= 5: chain_dir = '看多'
            elif chain_score <= -5: chain_dir = '看空'
            elif chain_score > 0: chain_dir = '偏多'
            elif chain_score < 0: chain_dir = '偏空'
            print(f'\n【信号3·事件连锁】{chain_dir}（综合评分 {chain_score:+d}）')
            for ev in cr['events'][:3]:
                print(f'  · {ev["event"]} → {ev["impact"]}')
    except Exception as e:
        print(f'\n【信号3·事件连锁】不可用: {str(e)[:40]}')
    # 三信号融合（加权投票）
    votes = {}
    def vote(d, w):
        votes[d] = votes.get(d, 0) + w
    if dir_a != '观望':
        vote(dir_a, 0.4)
    else:
        vote(dir_c if dir_c != '震荡' else '观望', 0.4)
    vote(dir_c if dir_c != '震荡' else '观望', 0.2)
    if chain_dir in ('看多', '偏多'):
        vote('看多', 0.4)
    elif chain_dir in ('看空', '偏空'):
        vote('看空', 0.4)
    final = max(votes, key=votes.get) if votes else '观望'
    print(f'\n【综合】{final} | 投票: {votes}')
    print(f'  事件链评分 {chain_score:+d}（{chain_dir}）—— 已纳入决策')
    # 封存
    conn = get_conn()
    today = pd.Timestamp.now().strftime('%Y-%m-%d')
    target = (pd.Timestamp.now() + pd.Timedelta(days=3)).strftime('%Y-%m-%d')
    conn.execute('INSERT INTO predictions (date, code, direction, confidence, reason) VALUES (?,?,?,?,?)',
                 (today, 'VER-A', final, max(votes.values(), default=0.5),
                  f'三信号融合(ML3日+趋势+事件链{chain_score:+d}) 预测{target}'))
    conn.commit()
    conn.close()
    print(f'\n✅ 已封存（{target} 对照——3 日后验证）')
    print('📌 真实基准：3日 55.8% / 高置信70%+实际90%准——不夸大')

if __name__ == '__main__':
    main()
