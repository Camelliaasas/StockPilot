"""三源综合引擎：技术ML + 新闻LLM + 财务基本面 → 综合预测（预测引擎 v3）"""
import sys, os, json
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn
from sentiment_llm import llm_analyze, get_llm_key

# ── 版 A：ML 技术（15 特征——45.5%）──
def ml_technical(code, symbol):
    from sklearn.ensemble import RandomForestClassifier
    conn = get_conn()
    hist = pd.read_sql("SELECT code, date, open, high, low, close, volume, amount FROM daily_prices ORDER BY code, date", conn)
    conn.close()
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
        df['fwd_1'] = df['close'].shift(-1) / df['close'] - 1
        return df
    feats = ['ret', 'ma5', 'ma20', 'ma60', 'macd', 'macd_hist', 'rsi', 'vol_ratio', 'amplitude',
             'macd_golden', 'ma520_bull', 'bull_align', 'mom20', 'bias60', 'hh20_break']
    h = features(hist)
    d = h.dropna(subset=feats + ['fwd_1']).copy()
    d = d.replace([np.inf, -np.inf], np.nan).dropna(subset=feats + ['fwd_1'])
    X = np.nan_to_num(d[feats].values, nan=0.0, posinf=0.0, neginf=0.0)
    y_cat = pd.cut(d['fwd_1'], bins=[-1, -0.01, 0.01, 1], labels=['看空', '观望', '看多'])
    valid = y_cat.notna()
    X, y = X[valid], y_cat[valid].astype(str)
    model = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
    model.fit(X, y)
    # 当前股票特征
    try:
        cur = ak.stock_zh_a_daily(symbol=symbol, start_date='20260101', end_date='20260810', adjust='qfq')
        cur = features(cur)
        row = cur.iloc[-1]
        x = np.array([[float(row[f]) if not pd.isna(row[f]) else 0.0 for f in feats]])
        x = np.nan_to_num(x, nan=0.0)
        proba = model.predict_proba(x)[0]
        return {c: float(p) for c, p in zip(model.classes_, proba)}
    except Exception:
        return {'看多': 0.33, '看空': 0.33, '观望': 0.34}

# ── 版 C：财务基本面（financials 表——ROE/营收/利润）──
def fundamental(code):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM financials WHERE code=? ORDER BY report_date DESC LIMIT 4", (code,)).fetchall()
    conn.close()
    if not rows:
        return None
    latest = rows[0]
    score = 0
    details = []
    # ROE
    roe = latest['roe']
    if roe is not None:
        if roe > 15: score += 2; details.append(f'ROE {roe:.1f}% 优秀')
        elif roe > 8: score += 1; details.append(f'ROE {roe:.1f}% 良好')
        else: score -= 1; details.append(f'ROE {roe:.1f}% 偏弱')
    # 营收增长
    rev = latest['revenue_yoy']
    if rev is not None:
        if rev > 20: score += 2; details.append(f'营收+{rev:.1f}% 高增长')
        elif rev > 5: score += 1; details.append(f'营收+{rev:.1f}% 稳健')
        else: score -= 1; details.append(f'营收+{rev:.1f}% 乏力')
    # 利润增长
    prof = latest['profit_yoy']
    if prof is not None:
        if prof > 20: score += 2; details.append(f'利润+{prof:.1f}% 高增长')
        elif prof > 0: score += 1; details.append(f'利润+{prof:.1f}% 正增长')
        else: score -= 1; details.append(f'利润+{prof:.1f}% 负增长')
    if score >= 3: direction, conf = '看多', 0.7
    elif score >= 1: direction, conf = '看多', 0.55
    elif score <= -3: direction, conf = '看空', 0.7
    elif score <= -1: direction, conf = '看空', 0.55
    else: direction, conf = '观望', 0.5
    return {'direction': direction, 'confidence': conf, 'score': score, 'details': details}

# ── 三源融合 ──
def fuse(code, symbol, name, news):
    print(f'\n📊 三源分析：{name}（{code}）')
    # A 技术
    a_probs = ml_technical(code, symbol)
    a_dir = max(a_probs, key=a_probs.get)
    print(f'【技术ML】{a_dir} {dict(sorted(a_probs.items(), key=lambda x: -x[1]))}')
    # B 新闻
    b = llm_analyze(f'{name}', news)
    print(f'【新闻LLM】{b.get("direction")} 置信{b.get("confidence")}%')
    # C 财务
    c = fundamental(code)
    if c:
        print(f'【财务基本面】{c["direction"]} 得分{c["score"]} | {", ".join(c["details"][:2])}')
    else:
        print('【财务基本面】无数据')
        c = {'direction': '观望', 'confidence': 0.5}
    # 融合：多源投票加权（每个源 ±1 分 × 置信度 × 权重）
    b_map = {'看多': 1, '观望': 0, '看空': -1}
    a_val = (a_probs.get('看多', 0) - a_probs.get('看空', 0))  # -1~+1 技术倾向
    b_val = b_map.get(b.get('direction', '观望'), 0) * (b.get('confidence', 50) / 100)
    c_val = b_map.get(c['direction'], 0) * c['confidence']
    total = a_val * 0.3 + b_val * 0.4 + c_val * 0.3
    if total > 0.15:
        final, conf = '看多', total * 100
    elif total < -0.15:
        final, conf = '看空', abs(total) * 100
    else:
        final, conf = '观望', (1 - abs(total)) * 100
    print(f'  技术倾向:{a_val:+.2f} 新闻:{b_val:+.2f} 财务:{c_val:+.2f} → 总分:{total:+.2f}')
    print(f'🏆 综合：{final} | 强度 {conf:.0f}%')
    return final, conf, a_dir, b.get('direction'), c['direction']

if __name__ == '__main__':
    targets = [
        ('600519', 'sh600519', '贵州茅台'),
        ('300750', 'sz300750', '宁德时代'),
        ('603259', 'sh603259', '药明康德'),
    ]
    try:
        news = [f'{r["标题"]}' for _, r in ak.stock_info_global_em().head(8).iterrows()]
    except Exception:
        news = []
    for code, symbol, name in targets:
        fuse(code, symbol, name, news)
