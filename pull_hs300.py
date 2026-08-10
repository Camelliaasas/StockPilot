"""大规模数据：沪深300 全量日线（2015-2026 长历史）→ 数据库"""
import akshare as ak
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import init_db, upsert_prices, count_rows

def main():
    init_db()
    cons = ak.index_stock_cons(symbol='000300')
    ok, fail = 0, 0
    total_rows = 0
    for _, row in cons.iterrows():
        code, name = row['品种代码'], row['品种名称']
        symbol = ('sh' if code.startswith('6') else 'sz') + code
        try:
            df = ak.stock_zh_a_daily(symbol=symbol, start_date='20150101', end_date='20260810', adjust='qfq')
            if df is not None and len(df) > 0:
                upsert_prices(code, name, df.to_dict('records'))
                total_rows += len(df)
                ok += 1
            time.sleep(0.25)
        except Exception as e:
            fail += 1
            time.sleep(0.5)
        if (ok + fail) % 50 == 0:
            print(f'进度: {ok+fail}/300 (ok={ok} fail={fail} 行数={total_rows})')
    n, ni, nf = count_rows()
    print(f'\n✅ 完成: 成功{ok} 失败{fail} | 股票库总计 {n} 行')

if __name__ == '__main__':
    main()
