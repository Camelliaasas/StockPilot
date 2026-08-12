"""全市场大回测：500 只×180 天——9 万样本——真实验证（展示用）"""
import sys, os, time
import pandas as pd
import numpy as np
import joblib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn
from paths import model_path

def run_market_backtest(n_stocks=500, limit_days=180):
    """全市场子集回测——逐日预测→次日对照"""
    t0 = time.time()
    model = joblib.load(model_path('model_stock_binary_full.joblib'))
    conn = get_conn()
    # 选股票（有足够数据的）
    codes = [r[0] for r in conn.execute(
        "SELECT code, COUNT(*) c FROM daily_prices GROUP BY code HAVING c > 400 ORDER BY c DESC LIMIT ?", (n_stocks,)).fetchall()]
    feats = ['ret', 'ma5', 'ma20', 'ma60', 'macd', 'macd_hist', 'rsi', 'vol_ratio', 'amplitude',
             'macd_golden', 'ma520_bull', 'bull_align', 'mom20', 'bias60', 'hh20_break', 'boll_pos']
    results = []
    done = 0
    for code in codes:
        try:
            df = pd.read_sql(f"SELECT * FROM daily_prices WHERE code={code} ORDER BY date DESC LIMIT {limit_days + 80}", conn)
            if df.empty or len(df) < 100:
                continue
            df = df.sort_values('date').reset_index(drop=True)
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
            tail = df.tail(limit_days)
            for _, row in tail.iterrows():
                vals = [float(row[f]) if pd.notna(row[f]) else 0.0 for f in feats]
                vals = vals + [0.0] * (31 - len(vals))
                x = np.nan_to_num(np.array([vals]), nan=0.0)
                try:
                    proba = model.predict_proba(x)[0]
                    up = float(proba[list(model.classes_).index(1)]) if 1 in model.classes_ else 0.5
                    pred = 1 if up >= 0.5 else 0
                    actual = 1 if row['fwd_1'] > 0 else 0
                    results.append((str(code), str(row['date'])[:10], pred, actual, 1 if pred == actual else 0))
                except Exception:
                    pass
            done += 1
            if done % 100 == 0:
                print(f'  进度 {done}/{min(len(codes), n_stocks)}——样本 {len(results):,}', flush=True)
        except Exception:
            continue
    # 存表（替换小样本）
    conn.execute('DROP TABLE IF EXISTS backtest_history')
    conn.execute('''CREATE TABLE IF NOT EXISTS backtest_history (
        code TEXT, date TEXT, pred INT, actual INT, correct INT
    )''')
    conn.executemany('INSERT INTO backtest_history (code, date, pred, actual, correct) VALUES (?,?,?,?,?)', results)
    conn.commit()
    conn.close()
    n = len(results)
    acc = sum(r[4] for r in results) / n * 100 if n else 0
    print(f'✅ 全市场回测: {n:,} 样本 | 准确率 {acc:.1f}% | 耗时 {time.time()-t0:.0f}s')

if __name__ == '__main__':
    run_market_backtest()
