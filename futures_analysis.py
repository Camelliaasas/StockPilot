"""期货分析：主力品种趋势/基差/预测（用户关注期货——扩展预测覆盖）"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 主力品种（南华代码）
FUTURES = [('V0', '原油'), ('AU0', '沪金'), ('CU0', '沪铜'), ('RB0', '螺纹钢'),
           ('M0', '豆粕'), ('AG0', '沪银'), ('TA0', 'PTA'), ('FG0', '玻璃')]

def analyze_futures(symbol, name):
    """期货分析：趋势 + 动量 + 波动"""
    try:
        df = ak.futures_main_sina(symbol=symbol, start_date='20260601', end_date='20260810')
        if df is None or len(df) < 20:
            return None
        df = df.rename(columns={'日期': 'date', '收盘价': 'close', '最高价': 'high', '最低价': 'low'})
        c = df['close'].reset_index(drop=True)
        cur = c.iloc[-1]
        ret_5 = (cur / c.iloc[-6] - 1) * 100 if len(c) >= 6 else 0
        ret_20 = (cur / c.iloc[-21] - 1) * 100 if len(c) >= 21 else 0
        ma5 = c.rolling(5).mean().iloc[-1]
        ma20 = c.rolling(20).mean().iloc[-1]
        trend = '多头' if ma5 > ma20 else '空头'
        vol = df['close'].pct_change().std() * np.sqrt(250) * 100
        # 信号
        if ret_20 > 3 and ma5 > ma20:
            signal, conf = '看多', min(50 + ret_20 * 2, 80)
        elif ret_20 < -3 and ma5 < ma20:
            signal, conf = '看空', min(50 + abs(ret_20) * 2, 80)
        else:
            signal, conf = '震荡', 50
        return {'name': name, 'cur': round(cur, 2), 'ret_5': round(ret_5, 2), 'ret_20': round(ret_20, 2),
                'trend': trend, 'vol': round(vol, 1), 'signal': signal, 'conf': conf}
    except Exception as e:
        return {'name': name, 'error': str(e)[:40]}

def main():
    print('=' * 60)
    print('📊 期货主力分析（趋势+动量——8 品种）')
    print('=' * 60)
    for symbol, name in FUTURES:
        r = analyze_futures(symbol, name)
        if not r:
            print(f'❌ {name}: 无数据')
            continue
        if 'error' in r:
            print(f'❌ {name}: {r["error"]}')
            continue
        icon = {'看多': '🔴', '看空': '🟢', '震荡': '⚪'}[r['signal']]
        print(f"\n{icon} {r['name']} 现价 {r['cur']}")
        print(f"   5日 {r['ret_5']:+.1f}% | 20日 {r['ret_20']:+.1f}% | 趋势 {r['trend']} | 年化波动 {r['vol']}%")
        print(f"   → {r['signal']}（置信 {r['conf']}%）")

if __name__ == '__main__':
    main()
