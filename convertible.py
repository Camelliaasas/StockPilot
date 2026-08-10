"""可转债分析：双低筛选（低价格+低溢价——低风险机会）+ 市场概况"""
import sys, os
import akshare as ak
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def convertible():
    """可转债：市场概况 + 双低机会"""
    try:
        df = ak.bond_zh_hs_cov_spot()
        if df is None or len(df) == 0:
            return {'error': '可转债数据不可用'}
        # 字段兼容
        df = df.copy()
        df['changepercent'] = df['changepercent'].astype(float)
        df['trade'] = df['trade'].astype(float)
        avg_chg = df['changepercent'].mean()
        up_cnt = (df['changepercent'] > 0).sum()
        # 双低策略（价格<120 + 转股溢价率<30%——近似用价格+涨幅）
        cheap = df[df['trade'] < 115].nlargest(8, 'changepercent')[['name', 'trade', 'changepercent']]
        return {
            'count': len(df), 'avg_chg': round(avg_chg, 2),
            'up_pct': round(up_cnt / len(df) * 100, 1),
            'cheap': [{'name': r['name'], 'price': round(float(r['trade']), 2),
                       'chg': round(float(r['changepercent']), 2)} for _, r in cheap.iterrows()],
        }
    except Exception as e:
        return {'error': str(e)[:60]}

if __name__ == '__main__':
    r = convertible()
    if 'error' in r:
        print('❌', r['error'])
    else:
        print(f"📊 可转债市场（{r['count']} 只）:")
        print(f"  平均涨跌 {r['avg_chg']:+.2f}% | 上涨占比 {r['up_pct']}%")
        print('\n💎 低价活跃标的（双低候选——价格<115）:')
        for c in r['cheap']:
            print(f"  {c['name']}: {c['price']}（{c['chg']:+.2f}%）")
