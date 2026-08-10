"""模型对比优化：RandomForest vs LightGBM vs 调参——找最优预测模型"""
import sys, os
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn
from ml_patterns import add_features
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import lightgbm as lgb

def prep(feats):
    conn = get_conn()
    df = pd.read_sql('SELECT * FROM daily_prices ORDER BY code, date', conn)
    conn.close()
    df = add_features(df)
    d = df.dropna(subset=feats + ['fwd_1']).copy()
    d = d.replace([np.inf, -np.inf], np.nan).dropna(subset=feats + ['fwd_1'])
    X = np.nan_to_num(d[feats].values, nan=0.0, posinf=0.0, neginf=0.0)
    y_cat = pd.cut(d['fwd_1'], bins=[-1, -0.01, 0.01, 1], labels=['看空', '观望', '看多'])
    valid = y_cat.notna()
    X, y = X[valid], y_cat[valid].astype(str)
    split = int(len(X) * 0.8)
    return X[:split], X[split:], y[:split], y[split:]

feats = ['ret', 'ma5', 'ma20', 'ma60', 'macd', 'macd_hist', 'rsi', 'vol_ratio', 'amplitude',
         'macd_golden', 'ma520_bull', 'bull_align', 'mom20', 'bias60', 'hh20_break']
Xtr, Xte, ytr, yte = prep(feats)
print(f'样本: 训练{len(Xtr)} 测试{len(Xte)}')

# 1. RandomForest（基准）
rf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
rf.fit(Xtr, ytr)
print(f'RF(200,8): {accuracy_score(yte, rf.predict(Xte))*100:.1f}%')

# 2. RandomForest 调参
rf2 = RandomForestClassifier(n_estimators=400, max_depth=12, min_samples_leaf=20, random_state=42, n_jobs=-1)
rf2.fit(Xtr, ytr)
print(f'RF(400,12,leaf20): {accuracy_score(yte, rf2.predict(Xte))*100:.1f}%')

# 3. LightGBM
lgbm = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, max_depth=8,
                          min_child_samples=20, random_state=42, n_jobs=-1, verbose=-1)
lgbm.fit(Xtr, ytr)
print(f'LGBM(300): {accuracy_score(yte, lgbm.predict(Xte))*100:.1f}%')

# 4. LightGBM 调参
lgbm2 = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.03, num_leaves=63, max_depth=10,
                           min_child_samples=30, subsample=0.8, colsample_bytree=0.8,
                           random_state=42, n_jobs=-1, verbose=-1)
lgbm2.fit(Xtr, ytr)
print(f'LGBM(500,tuned): {accuracy_score(yte, lgbm2.predict(Xte))*100:.1f}%')

# 5. 特征重要性（最优模型）
imp = sorted(zip(feats, lgbm2.feature_importances_), key=lambda x: -x[1])
print('LGBM 特征重要性:', ', '.join(f'{f}({v})' for f, v in imp[:8]))
