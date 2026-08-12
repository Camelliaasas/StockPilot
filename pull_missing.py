"""补拉缺失股票（全 A 5539 - 库中缺失——限频重试）"""
import sys, os, time
import akshare as ak
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def find_missing():
    """找库中缺失的股票"""
    try:
        info = ak.stock_info_a_code_name()
    except Exception:
        return []
    conn = get_conn()
    have = set(str(r[0]) for r in conn.execute('SELECT DISTINCT code FROM daily_prices').fetchall())
    conn.close()
    missing = []
    for _, r in info.iterrows():
        c = str(r['code']).zfill(6)
        # 库中 code 可能是 int（600519）——两种都查
        if c not in have and int(c) not in {int(h) for h in have if h.isdigit()}:
            missing.append((c, r['name']))
    return missing

def pull_missing(limit=50, sleep_s=1.5):
    """补拉（默认 50 只——限频慢拉）"""
    missing = find_missing()
    if not missing:
        print('✅ 无缺失股票')
        return
    print(f'缺失 {len(missing)} 只——补拉前 {limit} 只')
    ok = 0
    conn = get_conn()
    for code, name in missing[:limit]:
        symbol = ('sh' if code.startswith('6') else 'sz') + code
        try:
            df = ak.stock_zh_a_daily(symbol=symbol, start_date='20150101', end_date='20261231', adjust='qfq')
            if df is not None and len(df) > 0:
                rows = [(code, str(r['date'])[:10], float(r['open']), float(r['high']),
                         float(r['low']), float(r['close']), float(r['volume'])) for _, r in df.iterrows()]
                conn.executemany('INSERT OR REPLACE INTO daily_prices (code, date, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)', rows)
                conn.commit()
                ok += 1
                print(f'  ✅ {code} {name}: {len(rows)} 行')
            else:
                print(f'  ⚠️ {code} {name}: 空数据')
        except Exception as e:
            print(f'  ❌ {code} {name}: {str(e)[:40]}')
        time.sleep(sleep_s)
    conn.close()
    print(f'✅ 补拉完成 {ok}/{min(limit, len(missing))}')

if __name__ == '__main__':
    pull_missing()
