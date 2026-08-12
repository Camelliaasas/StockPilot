"""历史回测战绩：过去 60 个交易日逐日预测→次日对照（真实样本——展示用）"""
import sys, os
import pandas as pd
import numpy as np
import joblib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def generate_backtest_history(limit_days=720):
    """用全市场模型对 8 只核心股做历史回测——每只取最近 limit_days 个交易日"""
    from paths import model_path
    model = joblib.load(model_path('model_stock_binary_full.joblib'))
    conn = get_conn()
    core = [('600519', '贵州茅台'), ('300750', '宁德时代'), ('603259', '药明康德'), ('601318', '中国平安'),
            ('600036', '招商银行'), ('002594', '比亚迪'), ('601012', '隆基绿能'), ('000858', '五粮液')]
    results = []
    for code, name in core:
        df = pd.read_sql(f"SELECT * FROM daily_prices WHERE code={code} ORDER BY date DESC LIMIT 800", conn)
        if df.empty:
            continue
        df = df.sort_values('date').reset_index(drop=True)
        # 简化特征（基础指标——模型 30 特征用 0 填充弱特征）
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
        # 预测（用基础 16 特征——其他填 0）
        feats = ['ret', 'ma5', 'ma20', 'ma60', 'macd', 'macd_hist', 'rsi', 'vol_ratio', 'amplitude',
                 'macd_golden', 'ma520_bull', 'bull_align', 'mom20', 'bias60', 'hh20_break', 'boll_pos']
        tail = df.tail(limit_days)
        for _, row in tail.iterrows():
            vals = []
            for f in feats:
                v = row[f] if pd.notna(row[f]) else 0.0
                vals.append(float(v))
            # 补足 31 特征（扩展指标+情绪特征填 0——中性）
            vals = vals + [0.0] * (31 - len(vals))
            x = np.nan_to_num(np.array([vals]), nan=0.0)
            try:
                proba = model.predict_proba(x)[0]
                up = float(proba[list(model.classes_).index(1)]) if 1 in model.classes_ else 0.5
                pred = 1 if up >= 0.5 else 0
                actual = 1 if row['fwd_1'] > 0 else 0
                results.append({'code': code, 'name': name, 'date': str(row['date'])[:10],
                                'pred': pred, 'actual': actual, 'correct': 1 if pred == actual else 0})
            except Exception:
                pass
    # 存表
    conn.execute('DROP TABLE IF EXISTS backtest_history')
    conn.execute('''CREATE TABLE IF NOT EXISTS backtest_history (
        code TEXT, name TEXT, date TEXT, pred INT, actual INT, correct INT
    )''')
    conn.executemany('INSERT INTO backtest_history VALUES (?,?,?,?,?,?)',
                     [(r['code'], r['name'], r['date'], r['pred'], r['actual'], r['correct']) for r in results])
    conn.commit()
    conn.close()
    n = len(results)
    acc = sum(r['correct'] for r in results) / n * 100 if n else 0
    print(f'✅ 历史回测战绩: {n} 样本 | 准确率 {acc:.1f}%')
    return {'samples': n, 'acc': round(acc, 1)}

if __name__ == '__main__':
    generate_backtest_history()
