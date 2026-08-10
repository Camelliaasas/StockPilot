"""板块轮动雷达：行业板块涨跌/热度变化/轮动信号"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def sector_radar():
    """板块雷达：今日强势板块 + 热度 + 轮动提示"""
    try:
        df = ak.stock_sector_spot(indicator='新浪行业')
        if df is None or len(df) < 10:
            return {'error': '板块数据不可用'}
        df2 = df.drop_duplicates(subset='板块')
        # 今日涨跌排行
        df2 = df2.copy()
        df2['涨跌幅'] = df2['涨跌幅'].astype(float)
        top = df2.nlargest(5, '涨跌幅')[['板块', '涨跌幅', '总成交额']]
        bottom = df2.nsmallest(3, '涨跌幅')[['板块', '涨跌幅']]
        # 成交额（资金关注度）
        df2['总成交额'] = df2['总成交额'].astype(float)
        hot = df2.nlargest(5, '总成交额')[['板块', '总成交额', '涨跌幅']]
        return {
            'top': [{'name': r['板块'], 'change': round(float(r['涨跌幅']), 2),
                     'amount': round(float(r['总成交额']) / 1e8, 1)} for _, r in top.iterrows()],
            'bottom': [{'name': r['板块'], 'change': round(float(r['涨跌幅']), 2)} for _, r in bottom.iterrows()],
            'hot': [{'name': r['板块'], 'amount': round(float(r['总成交额']) / 1e8, 1),
                     'change': round(float(r['涨跌幅']), 2)} for _, r in hot.iterrows()],
        }
    except Exception as e:
        return {'error': str(e)[:60]}

if __name__ == '__main__':
    r = sector_radar()
    if 'error' in r:
        print('❌', r['error'])
    else:
        print('📡 板块轮动雷达:')
        print('\n🔥 今日强势板块 TOP5:')
        for t in r['top']:
            print(f"  {t['name']}: {t['change']:+.1f}%（成交{t['amount']}亿）")
        print('\n💧 资金聚焦板块（成交额）:')
        for t in r['hot']:
            print(f"  {t['name']}: {t['amount']}亿（{t['change']:+.1f}%）")
        print('\n❄️ 弱势板块:')
        for t in r['bottom']:
            print(f"  {t['name']}: {t['change']:+.1f}%")
