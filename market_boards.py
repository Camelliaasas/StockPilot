"""市场涨跌榜：涨幅/跌幅/成交额/量比——市场总览"""
import sys, os
import akshare as ak
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def market_boards():
    """涨跌榜（新浪全市场——5541 只）"""
    try:
        df = ak.stock_zh_a_spot()
        if df is None or len(df) == 0:
            return {'error': '行情不可用'}
        df = df.copy()
        df['涨跌幅'] = df['涨跌幅'].astype(float)
        df['成交额'] = df['成交额'].astype(float)
        df['成交量'] = df['成交量'].astype(float)
        # 过滤停牌（涨跌幅 0 且成交额 0）
        active = df[(df['成交额'] > 0)]
        gain = active.nlargest(10, '涨跌幅')[['代码', '名称', '最新价', '涨跌幅']]
        loss = active.nsmallest(10, '涨跌幅')[['代码', '名称', '最新价', '涨跌幅']]
        amount = active.nlargest(10, '成交额')[['代码', '名称', '最新价', '涨跌幅', '成交额']]
        vol_hot = active.nlargest(10, '成交量')[['代码', '名称', '最新价', '涨跌幅', '成交量']]
        # 市场统计
        up_cnt = (active['涨跌幅'] > 0).sum()
        down_cnt = (active['涨跌幅'] < 0).sum()
        limit_up = (active['涨跌幅'] >= 9.8).sum()
        limit_down = (active['涨跌幅'] <= -9.8).sum()
        total_amt = active['成交额'].sum()
        def fmt(r):
            return {'code': r['代码'], 'name': r['名称'], 'price': round(float(r['最新价']), 2),
                    'chg': round(float(r['涨跌幅']), 2)}
        return {
            'stats': {'up': int(up_cnt), 'down': int(down_cnt),
                      'limit_up': int(limit_up), 'limit_down': int(limit_down),
                      'total_amt': round(float(total_amt) / 1e8, 0)},
            'gain': [fmt(r) for _, r in gain.iterrows()],
            'loss': [fmt(r) for _, r in loss.iterrows()],
            'amount': [{'code': r['代码'], 'name': r['名称'], 'price': round(float(r['最新价']), 2),
                        'chg': round(float(r['涨跌幅']), 2), 'amt': round(float(r['成交额']) / 1e8, 1)} for _, r in amount.iterrows()],
            'vol_hot': [{'code': r['代码'], 'name': r['名称'], 'price': round(float(r['最新价']), 2),
                         'chg': round(float(r['涨跌幅']), 2)} for _, r in vol_hot.iterrows()],
        }
    except Exception as e:
        return {'error': str(e)[:60]}

if __name__ == '__main__':
    r = market_boards()
    if 'error' in r:
        print('❌', r['error'])
    else:
        s = r['stats']
        print(f"📊 市场总览: 上涨{s['up']} | 下跌{s['down']} | 涨停{s['limit_up']} | 跌停{s['limit_down']} | 成交{s['total_amt']:.0f}亿")
        print('\n🔥 涨幅榜:')
        for g in r['gain'][:5]:
            print(f"  {g['name']} {g['price']} ({g['chg']:+.2f}%)")
        print('\n💧 成交额榜:')
        for a in r['amount'][:5]:
            print(f"  {a['name']} {a['amt']}亿 ({a['chg']:+.2f}%)")
