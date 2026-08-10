"""情绪数据每日入库：涨停池/跌停池/北向资金——积累情绪特征数据"""
import akshare as ak
import sys, os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def pull_sentiment():
    conn = get_conn()
    # 建表
    conn.execute('''CREATE TABLE IF NOT EXISTS sentiment_daily (
        date TEXT PRIMARY KEY, limit_up INTEGER, limit_down INTEGER,
        up_count INTEGER, down_count INTEGER, north_net REAL
    )''')
    # 最近交易日（取 5 天范围）
    today = datetime.now()
    for i in range(0, 5):
        d = (today - timedelta(days=i)).strftime('%Y%m%d')
        try:
            zt = ak.stock_zt_pool_em(date=d)  # 涨停池
            dt = ak.stock_zt_pool_dtgc_em(date=d)  # 跌停池
            limit_up = len(zt) if zt is not None else 0
            limit_down = len(dt) if dt is not None else 0
            # 北向（最近的）
            north = None
            try:
                hs = ak.stock_hsgt_fund_flow_summary_em()
                if hs is not None and len(hs) > 0:
                    # 找北向资金净买额
                    row = hs[hs['类型'].str.contains('北向')].iloc[0] if len(hs[hs['类型'].str.contains('北向')]) > 0 else hs.iloc[0]
                    north = float(row.get('成交净买额', 0) or 0)
            except Exception:
                pass
            date_str = datetime.strptime(d, '%Y%m%d').strftime('%Y-%m-%d')
            conn.execute('INSERT OR REPLACE INTO sentiment_daily (date, limit_up, limit_down, up_count, down_count, north_net) VALUES (?,?,?,?,?,?)',
                         (date_str, limit_up, limit_down, limit_up, limit_down, north))
            conn.commit()
            print(f'✅ {date_str}: 涨停{limit_up} 跌停{limit_down} 北向{north}')
        except Exception as e:
            print(f'❌ {d}: {str(e)[:50]}')
    cnt = conn.execute('SELECT COUNT(*) FROM sentiment_daily').fetchone()[0]
    conn.close()
    print(f'📊 情绪库 {cnt} 天')

if __name__ == '__main__':
    pull_sentiment()
