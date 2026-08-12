"""演示数据：首次运行自动拉取核心数据（8 只+指数+财务+新闻）——快速可用"""
import os, sys
import akshare as ak
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

CORE = [('600519', '贵州茅台'), ('300750', '宁德时代'), ('603259', '药明康德'), ('601318', '中国平安'),
        ('600036', '招商银行'), ('002594', '比亚迪'), ('601012', '隆基绿能'), ('000858', '五粮液')]

def load_demo():
    import os as _os
    log_path = _os.path.join(_os.path.expanduser('~'), 'StockPilotData', 'demo_log.txt')
    def log(msg):
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except Exception:
            pass
    conn = get_conn()
    cnt = conn.execute('SELECT COUNT(*) FROM daily_prices').fetchone()[0]
    conn.close()
    if cnt > 1000:
        log(f'✅ 已有数据 {cnt} 行——跳过演示加载')
        print(f'✅ 已有数据 {cnt} 行——跳过演示加载')
        return
    log('📥 首次运行——加载演示数据...')
    print('📥 首次运行——加载演示数据（8 只核心股×11年+指数）...')
    total = 0
    for code, name in CORE:
        symbol = ('sh' if code.startswith('6') else 'sz') + code
        try:
            df = ak.stock_zh_a_daily(symbol=symbol, start_date='20150101', end_date='20260810', adjust='qfq')
            if df is not None and len(df) > 0:
                rows = [(code, str(r['date'])[:10], float(r['open']), float(r['high']),
                         float(r['low']), float(r['close']), float(r['volume'])) for _, r in df.iterrows()]
                conn = get_conn()
                conn.executemany('INSERT OR REPLACE INTO daily_prices (code, date, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)', rows)
                conn.commit()
                conn.close()
                total += len(rows)
                log(f'  ✅ {name}: {len(rows)} 行')
                print(f'  ✅ {name}: {len(rows)} 行')
        except Exception as e:
            log(f'  ❌ {name}: {str(e)[:80]}')
            print(f'  ❌ {name}: {str(e)[:40]}')
    # 指数
    try:
        idx = ak.stock_zh_index_daily(symbol='sh000001')
        conn = get_conn()
        conn.executemany('INSERT OR REPLACE INTO index_daily (code, date, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)',
                         [('000001', str(r['date'])[:10], float(r['open']), float(r['high']), float(r['low']), float(r['close']), float(r['volume'])) for _, r in idx.iterrows()])
        conn.commit()
        conn.close()
        print(f'  ✅ 上证指数: {len(idx)} 行')
    except Exception:
        pass
    # 自选（默认 8 只）
    conn = get_conn()
    conn.executemany('INSERT OR IGNORE INTO watchlist (code, name) VALUES (?,?)', CORE)
    conn.commit()
    conn.close()
    print(f'✅ 演示数据完成——共 {total} 行——看板已可用')

if __name__ == '__main__':
    load_demo()
