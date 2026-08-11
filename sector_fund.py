"""板块资金雷达：行业板块资金强度（成交额+涨跌——资金聚焦/流出）"""
import sys, os
import akshare as ak
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def sector_fund():
    """板块资金：成交额排行 + 资金强度（成交×涨跌——资金进场/出逃）"""
    try:
        df = ak.stock_sector_spot(indicator='新浪行业')
        if df is None or len(df) < 10:
            return {'error': '板块数据不可用'}
        df2 = df.drop_duplicates(subset='板块').copy()
        df2['涨跌幅'] = df2['涨跌幅'].astype(float)
        df2['总成交额'] = df2['总成交额'].astype(float)
        # 资金强度 = 成交额 × 涨跌幅（正=资金净流入方向；负=流出）
        df2['fund_strength'] = df2['总成交额'] * df2['涨跌幅']
        inflow = df2.nlargest(6, 'fund_strength')[['板块', '涨跌幅', '总成交额', 'fund_strength']]
        outflow = df2.nsmallest(6, 'fund_strength')[['板块', '涨跌幅', '总成交额', 'fund_strength']]
        hot_amt = df2.nlargest(5, '总成交额')[['板块', '涨跌幅', '总成交额']]
        return {
            'inflow': [{'name': r['板块'], 'chg': round(float(r['涨跌幅']), 2),
                        'amt': round(float(r['总成交额']) / 1e8, 1),
                        'strength': round(float(r['fund_strength']) / 1e8, 0)} for _, r in inflow.iterrows()],
            'outflow': [{'name': r['板块'], 'chg': round(float(r['涨跌幅']), 2),
                         'amt': round(float(r['总成交额']) / 1e8, 1),
                         'strength': round(float(r['fund_strength']) / 1e8, 0)} for _, r in outflow.iterrows()],
            'hot': [{'name': r['板块'], 'chg': round(float(r['涨跌幅']), 2),
                     'amt': round(float(r['总成交额']) / 1e8, 1)} for _, r in hot_amt.iterrows()],
        }
    except Exception as e:
        return {'error': str(e)[:60]}

if __name__ == '__main__':
    r = sector_fund()
    if 'error' in r:
        print('❌', r['error'])
    else:
        print('💧 资金流入板块（成交×涨跌——资金进场）:')
        for x in r['inflow'][:5]:
            print(f"  {x['name']}: 强度{x['strength']:.0f}亿 | {x['chg']:+.1f}% | 成交{x['amt']:.0f}亿")
        print('\n💸 资金流出板块:')
        for x in r['outflow'][:3]:
            print(f"  {x['name']}: 强度{x['strength']:.0f}亿 | {x['chg']:+.1f}%")
