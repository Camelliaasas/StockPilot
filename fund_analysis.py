"""基金分析：热门基金净值趋势/表现（沪深300ETF/主动基金）"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 热门基金
FUNDS = [('110022', '易方达消费行业'), ('005827', '易方达蓝筹精选'), ('161725', '招商中证白酒'),
         ('510300', '沪深300ETF'), ('510500', '中证500ETF'), ('588000', '科创50ETF')]

def analyze_fund(code, name):
    """基金分析：净值趋势 + 收益 + 波动"""
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator='单位净值走势')
        if df is None or len(df) < 30:
            return None
        df = df.rename(columns={'净值日期': 'date', '单位净值': 'nav', '日增长率': 'growth'})
        df['date'] = pd.to_datetime(df['date'])
        nav = df['nav'].astype(float)
        cur = nav.iloc[-1]
        ret_1m = (cur / nav.iloc[-22] - 1) * 100 if len(nav) >= 22 else 0
        ret_3m = (cur / nav.iloc[-66] - 1) * 100 if len(nav) >= 66 else 0
        ret_1y = (cur / nav.iloc[-244] - 1) * 100 if len(nav) >= 244 else None
        vol = df['growth'].astype(float).std() * np.sqrt(250)
        # 信号
        if ret_3m > 5:
            signal = '看多'
        elif ret_3m < -5:
            signal = '看空'
        else:
            signal = '震荡'
        return {'name': name, 'code': code, 'cur': round(cur, 4), 'ret_1m': round(ret_1m, 1),
                'ret_3m': round(ret_3m, 1), 'ret_1y': round(ret_1y, 1) if ret_1y is not None else None,
                'vol': round(vol, 1), 'signal': signal}
    except Exception as e:
        return {'name': name, 'error': str(e)[:40]}

if __name__ == '__main__':
    print('📊 基金分析（净值趋势）:')
    for code, name in FUNDS:
        r = analyze_fund(code, name)
        if r and 'error' not in r:
            y = f' | 1年{r["ret_1y"]:+.1f}%' if r['ret_1y'] is not None else ''
            print(f"{r['name']}({r['code']}) 净值{r['cur']} | 1月{r['ret_1m']:+.1f}% | 3月{r['ret_3m']:+.1f}%{y} | → {r['signal']}")
        else:
            print(f"❌ {name}: {r.get('error', '无数据') if r else '无数据'}")
