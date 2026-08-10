"""拉取 2018-2022 历史数据（回测验证用）：上证指数 + 代表个股"""
import akshare as ak
import json

def pull(name, symbol_fn, **kw):
    try:
        df = symbol_fn(**kw)
        return df
    except Exception as e:
        print(f'❌ {name}: {str(e)[:60]}')
        return None

# 上证指数 2018-2022
idx = ak.stock_zh_index_daily(symbol='sh000001')
idx = idx[(idx['date'] >= '2018-01-01') & (idx['date'] <= '2022-12-31')]
print(f'上证指数 2018-2022: {len(idx)} 交易日')
# 关键年度涨跌
for y in range(2018, 2023):
    yd = idx[idx['date'].astype(str).str.startswith(str(y))]
    if len(yd) > 0:
        chg = (yd.iloc[-1]['close'] / yd.iloc[0]['close'] - 1) * 100
        print(f'  {y}年: {yd.iloc[0]["close"]:.0f} → {yd.iloc[-1]["close"]:.0f} ({chg:+.1f}%)')

# 茅台 2018-2022
mt = ak.stock_zh_a_daily(symbol='sh600519', start_date='20180101', end_date='20221231', adjust='qfq')
print(f'\n茅台 2018-2022: {len(mt)} 交易日')
for y in range(2018, 2023):
    yd = mt[mt['date'].astype(str).str.startswith(str(y))]
    if len(yd) > 0:
        chg = (yd.iloc[-1]['close'] / yd.iloc[0]['close'] - 1) * 100
        print(f'  {y}年: {yd.iloc[0]["close"]:.0f} → {yd.iloc[-1]["close"]:.0f} ({chg:+.1f}%)')

# 宁德时代 2018-2022（2018.6 上市）
try:
    nd = ak.stock_zh_a_daily(symbol='sz300750', start_date='20180601', end_date='20221231', adjust='qfq')
    print(f'\n宁德时代: {len(nd)} 交易日')
    for y in range(2018, 2023):
        yd = nd[nd['date'].astype(str).str.startswith(str(y))]
        if len(yd) > 0:
            chg = (yd.iloc[-1]['close'] / yd.iloc[0]['close'] - 1) * 100
            print(f'  {y}年: {yd.iloc[0]["close"]:.0f} → {yd.iloc[-1]["close"]:.0f} ({chg:+.1f}%)')
except Exception as e:
    print(f'宁德时代: {str(e)[:60]}')

# 保存数据供后续分析
idx.to_json(r'C:\Users\23643\src_workflow\stock_predict\history_idx.json', orient='records', date_format='iso')
if mt is not None:
    mt.to_json(r'C:\Users\23643\src_workflow\stock_predict\history_mt.json', orient='records', date_format='iso')
print('\n数据已保存')
