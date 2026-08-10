"""批量爬取：50+ 代表股票 + 指数 + 期货（2018-2022 海量数据）→ SQLite"""
import akshare as ak
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import init_db, upsert_prices, upsert_index, upsert_futures, count_rows

# 代表股票池（各行业龙头 + 沪深300 代表——50+）
STOCKS = [
    ('sh600519', '贵州茅台'), ('sz300750', '宁德时代'), ('sz000858', '五粮液'),
    ('sh601318', '中国平安'), ('sh600036', '招商银行'), ('sz000333', '美的集团'),
    ('sh600900', '长江电力'), ('sz002594', '比亚迪'), ('sh601899', '紫金矿业'),
    ('sh600030', '中信证券'), ('sh601012', '隆基绿能'), ('sz002415', '海康威视'),
    ('sh600276', '恒瑞医药'), ('sz000651', '格力电器'), ('sh601888', '中国中免'),
    ('sz002475', '立讯精密'), ('sh600809', '山西汾酒'), ('sh603288', '海天味业'),
    ('sz000725', '京东方A'), ('sh600887', '伊利股份'), ('sz002714', '牧原股份'),
    ('sh601166', '兴业银行'), ('sz000002', '万科A'), ('sh600585', '海螺水泥'),
    ('sh601398', '工商银行'), ('sh600028', '中国石化'), ('sh601857', '中国石油'),
    ('sh600050', '中国联通'), ('sh601668', '中国建筑'), ('sz000001', '平安银行'),
    ('sh688981', '中芯国际'), ('sz002230', '科大讯飞'), ('sh603259', '药明康德'),
    ('sz300059', '东方财富'), ('sh601211', '国泰君安'), ('sh600104', '上汽集团'),
    ('sz002352', '顺丰控股'), ('sh600690', '海尔智家'), ('sz002027', '分众传媒'),
    ('sh601628', '中国人寿'), ('sz300760', '迈瑞医疗'), ('sz002304', '洋河股份'),
    ('sh603501', '韦尔股份'), ('sz300124', '汇川技术'), ('sh600570', '恒生电子'),
    ('sz002460', '赣锋锂业'), ('sh600438', '通威股份'), ('sz300014', '亿纬锂能'),
    ('sz002371', '北方华创'), ('sh601088', '中国神华'), ('sh600309', '万华化学'),
    ('sz002142', '宁波银行'), ('sh601601', '中国太保'), ('sz002050', '三花智控'),
]

# 指数
INDEXES = [('sh000001', '上证指数'), ('sz399001', '深证成指'), ('sz399006', '创业板指')]

# 期货主力（南华代码）
FUTURES = [('V0', '原油'), ('AU0', '沪金'), ('CU0', '沪铜'), ('RB0', '螺纹钢'), ('M0', '豆粕')]

def main():
    init_db()
    ok, fail = 0, 0
    # 1. 股票（腾讯源——已验证）
    for code, name in STOCKS:
        try:
            df = ak.stock_zh_a_daily(symbol=code, start_date='20180101', end_date='20221231', adjust='qfq')
            if len(df) > 0:
                upsert_prices(code, name, df.to_dict('records'))
                ok += 1
                print(f'✅ {code} {name}: {len(df)} 行')
            time.sleep(0.3)
        except Exception as e:
            fail += 1
            print(f'❌ {code} {name}: {str(e)[:50]}')
            time.sleep(0.5)
    # 2. 指数
    for code, name in INDEXES:
        try:
            df = ak.stock_zh_index_daily(symbol=code)
            df = df[(df['date'] >= '2018-01-01') & (df['date'] <= '2022-12-31')]
            upsert_index(code, df.to_dict('records'))
            ok += 1
            print(f'✅ 指数 {name}: {len(df)} 行')
        except Exception as e:
            fail += 1
            print(f'❌ 指数 {name}: {str(e)[:50]}')
    # 3. 期货
    for code, name in FUTURES:
        try:
            df = ak.futures_main_sina(symbol=code, start_date='20180101', end_date='20221231')
            if len(df) > 0:
                # 列名：日期/开盘价/最高价/最低价/收盘价/成交量
                df = df.rename(columns={'日期':'date','开盘价':'open','最高价':'high','最低价':'low','收盘价':'close','成交量':'volume'})
                upsert_futures(code, name, df.to_dict('records'))
                ok += 1
                print(f'✅ 期货 {name}: {len(df)} 行')
            time.sleep(0.3)
        except Exception as e:
            fail += 1
            print(f'❌ 期货 {name}: {str(e)[:50]}')
            time.sleep(0.5)
    n, ni, nf = count_rows()
    print(f'\n📊 完成: {ok} 成功/{fail} 失败 | 股票 {n} 行 | 指数 {ni} 行 | 期货 {nf} 行')

if __name__ == '__main__':
    main()
