"""黄金/外汇分析：避险资产 + 汇率（国际联动）"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def gold_fx():
    """黄金 + 汇率分析"""
    result = {'gold': {}, 'fx': {}}
    # 黄金（上海金基准价）
    try:
        df = ak.spot_golden_benchmark_sge()
        if df is not None and len(df) > 20:
            df['日期'] = pd.to_datetime(df['交易时间'])
            gold = df.sort_values('日期')
            price = float(gold['晚盘价'].iloc[-1])
            ret_20 = (price / float(gold['晚盘价'].iloc[-21]) - 1) * 100 if len(gold) >= 21 else 0
            ret_60 = (price / float(gold['晚盘价'].iloc[-61]) - 1) * 100 if len(gold) >= 61 else 0
            signal = '看多' if ret_20 > 2 else ('看空' if ret_20 < -2 else '震荡')
            result['gold'] = {'price': round(price, 2), 'ret_20': round(ret_20, 1), 'ret_60': round(ret_60, 1), 'signal': signal}
    except Exception as e:
        result['gold']['error'] = str(e)[:40]
    # 汇率（USD/CNY——美元强弱）
    try:
        fx = ak.fx_spot_quote()
        if fx is not None and len(fx) > 0:
            usd = fx[fx['货币对'] == 'USD/CNY']
            if len(usd) > 0:
                r = usd.iloc[0]
                result['fx'] = {'usd_cny': round(float(r['买报价']), 4), 'note': 'USD/CNY——数值高=人民币弱'}
    except Exception as e:
        result['fx']['error'] = str(e)[:40]
    # 人民币汇率趋势（中行牌价——月度）
    try:
        cny = ak.currency_boc_safe()
        if cny is not None and len(cny) > 30:
            cny['日期'] = pd.to_datetime(cny['日期'])
            cny = cny.sort_values('日期')
            usd_series = cny['美元'].astype(float)
            cur = usd_series.iloc[-1]
            prev_60 = usd_series.iloc[-61] if len(usd_series) >= 61 else usd_series.iloc[0]
            trend = '人民币升值' if cur < prev_60 else ('人民币贬值' if cur > prev_60 else '持平')
            result['fx']['trend'] = f'{trend}（60日 {prev_60:.4f}→{cur:.4f}）'
    except Exception:
        pass
    return result

if __name__ == '__main__':
    r = gold_fx()
    print('🥇 黄金（上海金）:')
    g = r.get('gold', {})
    if 'price' in g:
        print(f"  现价 {g['price']} | 20日 {g['ret_20']:+.1f}% | 60日 {g['ret_60']:+.1f}% → {g['signal']}")
    else:
        print(f"  {g.get('error', '无数据')}")
    print('💱 汇率:')
    f = r.get('fx', {})
    if 'usd_cny' in f:
        print(f"  USD/CNY {f['usd_cny']}")
    if 'trend' in f:
        print(f"  {f['trend']}")
