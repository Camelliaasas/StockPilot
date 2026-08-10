"""数据层验证：AKShare 各数据源逐个测试可用性"""
import akshare as ak

results = []

def test(name, fn):
    try:
        df = fn()
        n = len(df) if hasattr(df, '__len__') else '?'
        cols = list(df.columns)[:6] if hasattr(df, 'columns') else []
        results.append(f'✅ {name}: {n} 行 | 列: {cols}')
    except Exception as e:
        results.append(f'❌ {name}: {str(e)[:60]}')

# 1. 个股日线（腾讯源——已验证）
test('个股日线(腾讯)', lambda: ak.stock_zh_a_daily(symbol='sh600519', start_date='20260601', end_date='20260810', adjust='qfq'))

# 2. 宏观数据（CPI）
test('CPI月度', lambda: ak.macro_china_cpi_yearly())

# 3. 全球财经快讯（东财）
test('全球财经快讯', lambda: ak.stock_info_global_em())

# 4. 个股新闻
test('个股新闻', lambda: ak.stock_news_em(symbol='600519'))

# 5. 期货主力行情（商品期货）
test('期货行情(南华)', lambda: ak.futures_main_sina(symbol='V0', start_date='20260701', end_date='20260810'))

# 6. 期货实时（东财）
test('期货实时(东财)', lambda: ak.futures_zh_spot())

# 7. A股实时行情（东财）
test('A股实时(东财)', lambda: ak.stock_zh_a_spot_em())

# 8. 大盘指数
test('上证指数', lambda: ak.stock_zh_index_daily(symbol='sh000001'))

# 9. 北向资金
test('北向资金', lambda: ak.stock_hsgt_fund_flow_summary_em())

# 10. 涨跌停
test('涨跌停统计', lambda: ak.stock_zt_pool_em(date='20260807'))

for r in results:
    print(r)
print(f'\n通过 {sum(1 for r in results if r.startswith("✅"))}/{len(results)}')
