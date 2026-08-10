"""全 A 批量拉取（5539 只×10 年——目标 1500 万行——断点续跑）"""
import akshare as ak
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import init_db, upsert_prices, count_rows

PROGRESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pull_progress.json')

def get_progress():
    if os.path.exists(PROGRESS):
        try:
            with open(PROGRESS) as f:
                return json.load(f)
        except Exception:
            pass
    return {'done': 0, 'last_code': ''}

def save_progress(done, last_code):
    with open(PROGRESS, 'w') as f:
        json.dump({'done': done, 'last_code': last_code}, f)

def main():
    init_db()
    stocks = ak.stock_info_a_code_name()
    prog = get_progress()
    start_idx = prog['done']
    total = len(stocks)
    print(f'全 A: {total} 只 | 从 {start_idx} 续跑')
    ok, fail = 0, 0
    rows_added = 0
    for i in range(start_idx, total):
        row = stocks.iloc[i]
        code, name = str(row['code']).zfill(6), str(row['name']).replace(' ', '')
        symbol = ('sh' if code.startswith('6') else 'sz') + code
        try:
            df = ak.stock_zh_a_daily(symbol=symbol, start_date='20150101', end_date='20260810', adjust='qfq')
            if df is not None and len(df) > 0:
                upsert_prices(code, name, df.to_dict('records'))
                rows_added += len(df)
                ok += 1
            time.sleep(0.15)
        except Exception:
            fail += 1
            time.sleep(0.4)
        if (i - start_idx + 1) % 100 == 0:
            save_progress(i + 1, code)
            n, _, _ = count_rows()
            print(f'进度 {i+1}/{total} | ok={ok} fail={fail} | 库总量 {n} 行', flush=True)
    save_progress(total, '')
    n, ni, nf = count_rows()
    print(f'\n✅ 全市场完成: ok={ok} fail={fail} | 日线库 {n} 行 | 新增 {rows_added}')

if __name__ == '__main__':
    main()
