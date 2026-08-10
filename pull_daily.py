"""自主拉数：每日增量拉取——股票+指数+期货+新闻入库（5万+持续积累）"""
import sys, os, time
import akshare as ak
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, upsert_prices, upsert_index, upsert_futures

STOCKS = [('sh600519','贵州茅台'), ('sz300750','宁德时代'), ('sz000858','五粮液'),
          ('sh601318','中国平安'), ('sh600036','招商银行'), ('sz002594','比亚迪'),
          ('sh601012','隆基绿能'), ('sh603259','药明康德'), ('sz300059','东方财富'),
          ('sh600030','中信证券')]

def main():
    ok = 0
    # 增量拉最近 30 日（覆盖新交易日）
    for code, name in STOCKS:
        try:
            df = ak.stock_zh_a_daily(symbol=code, start_date=pd.Timestamp.now().strftime('%Y%m%d'), end_date='', adjust='qfq')
            if df is None or len(df) == 0:
                df = ak.stock_zh_a_daily(symbol=code, start_date='20260701', end_date='20260810', adjust='qfq')
            if len(df) > 0:
                upsert_prices(code, name, df.to_dict('records'))
                ok += 1
            time.sleep(0.3)
        except Exception as e:
            print(f'❌ {code}: {str(e)[:50]}')
    # 指数
    try:
        idx = ak.stock_zh_index_daily(symbol='sh000001')
        upsert_index('sh000001', idx.to_dict('records'))
        print('✅ 上证指数更新')
    except Exception as e:
        print(f'❌ 指数: {str(e)[:50]}')
    # 期货
    try:
        fut = ak.futures_main_sina(symbol='AU0', start_date='20260701', end_date='20260810')
        fut = fut.rename(columns={'日期':'date','开盘价':'open','最高价':'high','最低价':'low','收盘价':'close','成交量':'volume'})
        upsert_futures('AU0', '沪金', fut.to_dict('records'))
        print('✅ 沪金更新')
    except Exception as e:
        print(f'❌ 期货: {str(e)[:50]}')
    # 新闻入库
    try:
        news = ak.stock_info_global_em()
        conn = get_conn()
        for _, r in news.head(20).iterrows():
            conn.execute('INSERT OR IGNORE INTO news (date, title, content, source) VALUES (?,?,?,?)',
                         (str(r.get('发布时间',''))[:10], r.get('标题',''), r.get('摘要','')[:200], '东财'))
        conn.commit()
        conn.close()
        print('✅ 新闻入库')
    except Exception as e:
        print(f'❌ 新闻: {str(e)[:50]}')
    print(f'✅ 增量拉取完成（{ok} 只股票）')

if __name__ == '__main__':
    main()
