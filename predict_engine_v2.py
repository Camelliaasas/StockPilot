"""预测引擎 v2：三版预测 + 真LLM + 幅度区间 + 时间窗 + 封存对照"""
import sys, os, json
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn
from sentiment_llm import llm_analyze, ANALYST_PROMPT

def get_news_today():
    """抓今日全球快讯（东财）"""
    try:
        news = ak.stock_info_global_em()
        return [f'{r["标题"]}' for _, r in news.head(10).iterrows()]
    except Exception:
        return []

def ml_predict(feats=['ret', 'ma5', 'ma20', 'macd', 'macd_hist', 'rsi', 'vol_ratio', 'amplitude']):
    """快速预测：加载已训练模型 + 指数特征（秒级）"""
    import joblib, os as _os
    _dir = _os.path.dirname(_os.path.abspath(__file__))
    model = joblib.load(_os.path.join(_dir, 'model_lgbm.joblib'))
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
        return df
    feats_all = ['ret', 'ma5', 'ma20', 'ma60', 'macd', 'macd_hist', 'rsi', 'vol_ratio', 'amplitude',
                 'macd_golden', 'ma520_bull', 'bull_align', 'mom20', 'bias60', 'hh20_break']
    idx = ak.stock_zh_index_daily(symbol='sh000001').tail(120)
    cur = features(idx)
    row = cur.iloc[-1]
    x = np.array([[float(row[f]) if not pd.isna(row[f]) else 0.0 for f in feats_all]])
    x = np.nan_to_num(x, nan=0.0)
    proba = model.predict_proba(x)[0]
    probs = {c: float(p) for c, p in zip(model.classes_, proba)}
    return probs, model

def main():
    print('=' * 52)
    print('📊 预测引擎 v2——明日上证方向 + 幅度区间')
    print('=' * 52)
    # 新闻
    news = get_news_today()
    print(f'\n今日新闻 {len(news)} 条')
    for n in news[:5]:
        print(f'  - {n[:45]}')
    # 版 A：ML
    probs, _ = ml_predict()
    a_dir = max(probs, key=probs.get)
    print(f'\n【版A·ML技术】{a_dir} | {dict(sorted(probs.items(), key=lambda x: -x[1]))}')
    # 版 B：真 LLM
    r = llm_analyze('上证指数', news)
    print(f'\n【版B·LLM分析师】{r.get("direction")} 置信度{r.get("confidence")}')
    print(f'  理由: {r.get("reason", "")[:80]}')
    # 版 C：综合
    wA, wB = 0.4, 0.6
    b_map = {'看多': 1, '观望': 0, '看空': -1}
    a_score = {'看多': probs.get('看多', 0) - probs.get('看空', 0), '观望': 0, '看空': probs.get('看空', 0) - probs.get('看多', 0)}
    score = {k: a_score[k] * wA + b_map[r.get('direction', '观望')] * (r.get('confidence', 50)/100) * wB for k in ['看多', '看空', '观望']}
    c_dir = max(score, key=score.get)
    c_conf = abs(score[c_dir]) * 100
    print(f'\n【版C·综合】{c_dir} | 强度 {c_conf:.0f}%')
    # 幅度区间（版B置信度映射）
    conf = r.get('confidence', 50)
    if c_dir == '看多':
        rng = f'+0.2%~+1.5%（置信度{conf:.0f}%）'
    elif c_dir == '看空':
        rng = f'-1.5%~-0.2%（置信度{conf:.0f}%）'
    else:
        rng = f'-0.5%~+0.5%（震荡）'
    print(f'\n【幅度区间】{rng}')
    # 封存
    conn = get_conn()
    for ver, d, conf_v in [('A', a_dir, probs[a_dir]), ('B', r.get('direction'), r.get('confidence', 50)/100),
                            ('C', c_dir, c_conf/100)]:
        conn.execute('INSERT INTO predictions (date, code, direction, confidence, reason) VALUES (?,?,?,?,?)',
                     ('2026-08-10', f'VER-{ver}', d, conf_v,
                      f'版{ver}预测明日上证 | 幅度{rng} | LLM理由:{r.get("reason","")[:100]}'))
    conn.commit()
    conn.close()
    print('\n✅ 三版+幅度已封存（明日对照）')
    # 校准提示
    print('📌 校准：连续 20 次预测后——算"置信度70%时实际正确率"——校准曲线')

if __name__ == '__main__':
    main()
