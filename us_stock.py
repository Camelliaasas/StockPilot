"""美股分析：趋势/动量/信号（AAPL/MSFT/NVDA 等）"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

US_STOCKS = [('AAPL', '苹果'), ('MSFT', '微软'), ('NVDA', '英伟达'), ('GOOGL', '谷歌'),
             ('TSLA', '特斯拉'), ('AMZN', '亚马逊'), ('META', 'Meta'), ('BABA', '阿里巴巴')]

def analyze_us(symbol, name):
    """美股分析：趋势+动量+信号"""
    try:
        df = ak.stock_us_daily(symbol=symbol, adjust='qfq')
        if df is None or len(df) < 60:
            return None
        c = df['close'].dropna().reset_index(drop=True)
        cur = c.iloc[-1]
        ret_20 = (cur / c.iloc[-21] - 1) * 100 if len(c) >= 21 else 0
        ret_60 = (cur / c.iloc[-61] - 1) * 100 if len(c) >= 61 else 0
        ma20 = c.rolling(20).mean().iloc[-1]
        ma60 = c.rolling(60).mean().iloc[-1]
        trend = '多头' if ma20 > ma60 else '空头'
        vol = c.pct_change().std() * np.sqrt(252) * 100
        if ret_20 > 3 and ma20 > ma60:
            signal, conf = '看多', min(50 + ret_20 * 2, 85)
        elif ret_20 < -3 and ma20 < ma60:
            signal, conf = '看空', min(50 + abs(ret_20) * 2, 85)
        else:
            signal, conf = '震荡', 50
        return {'name': name, 'cur': round(cur, 2), 'ret_20': round(ret_20, 1), 'ret_60': round(ret_60, 1),
                'trend': trend, 'vol': round(vol, 1), 'signal': signal, 'conf': round(conf)}
    except Exception as e:
        return {'name': name, 'error': str(e)[:40]}

if __name__ == '__main__':
    print('📊 美股分析（趋势+动量）:')
    for symbol, name in US_STOCKS:
        r = analyze_us(symbol, name)
        if r and 'error' not in r:
            icon = {'看多': '🔴', '看空': '🟢', '震荡': '⚪'}[r['signal']]
            print(f"{icon} {r['name']}({symbol}) ${r['cur']} | 20日{r['ret_20']:+.1f}% | 60日{r['ret_60']:+.1f}% | {r['trend']} | → {r['signal']}({r['conf']}%)")
        else:
            print(f"❌ {name}: {r.get('error', '无数据') if r else '无数据'}")
