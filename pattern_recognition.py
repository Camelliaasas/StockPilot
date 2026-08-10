"""技术形态识别：双底/头肩顶/新高突破/趋势线（自选股形态扫描）"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decision_card import get_watchlist

def detect_patterns(df):
    """识别近期形态（最近 60 日窗口）"""
    if df is None or len(df) < 60:
        return []
    c = df['close'].reset_index(drop=True)
    low = df['low'].reset_index(drop=True)
    high = df['high'].reset_index(drop=True)
    patterns = []
    w = c.iloc[-60:]
    wl = low.iloc[-60:]
    wh = high.iloc[-60:]
    # 1. 双底（W 形——两个相近低点+中间反弹）
    lows = wl.values
    for i in range(10, len(lows) - 5):
        seg = lows[i-5:i+1]
        if len(seg) >= 3 and seg[-1] == seg.min():
            bottom1 = seg.min()
            mid_peak = w.iloc[max(0, i-5):i+1].max()
            fwd = lows[i+1:i+6]
            if len(fwd) > 0 and abs(fwd.min() - bottom1) / bottom1 < 0.03 and mid_peak > bottom1 * 1.03:
                patterns.append('双底（W底）形态')
                break
    # 2. 头肩顶（中间高两边低）
    for i in range(15, len(wh) - 5):
        seg = wh.iloc[i-7:i+1]
        if len(seg) >= 3 and seg.iloc[-1] == seg.max():
            peak = seg.max()
            left = wh.iloc[i-7:i-3]
            right = wh.iloc[i-3:i]
            if len(left) > 0 and len(right) > 0 and left.max() > peak * 0.97 and right.max() > peak * 0.97:
                patterns.append('头肩顶（警惕见顶）')
                break
    # 3. 新高突破（20日新高+放量）
    hh20 = c.rolling(20).max().shift(1)
    if c.iloc[-1] > hh20.iloc[-1] and df['volume'].iloc[-1] > df['volume'].rolling(5).mean().iloc[-1] * 1.2:
        patterns.append('20日新高放量突破')
    # 4. 均线金叉（5 上穿 20——刚发生）
    ma5 = c.rolling(5).mean()
    ma20 = c.rolling(20).mean()
    if ma5.iloc[-1] > ma20.iloc[-1] and ma5.iloc[-2] <= ma20.iloc[-2]:
        patterns.append('均线金叉（5上穿20）')
    # 5. 连续缩量（地量——可能变盘）
    if df['volume'].tail(5).mean() < df['volume'].rolling(20).mean().iloc[-1] * 0.7:
        patterns.append('连续缩量（地量——关注变盘）')
    # 6. 上升通道（20日低点抬高）
    lows20 = low.tail(20)
    if lows20.iloc[-1] > lows20.quantile(0.25) and c.iloc[-1] > c.rolling(20).mean().iloc[-1]:
        patterns.append('上升通道（低点抬高）')
    return patterns

def scan_watchlist():
    """扫描自选股形态"""
    results = []
    for code, name in get_watchlist()[:6]:
        try:
            symbol = ('sh' if code.startswith('6') else 'sz') + code
            df = ak.stock_zh_a_daily(symbol=symbol, start_date='20260101', end_date='20260810', adjust='qfq')
            pats = detect_patterns(df)
            results.append({'name': name, 'code': code, 'patterns': pats})
        except Exception:
            pass
    return results

if __name__ == '__main__':
    print('🔍 自选股技术形态扫描:')
    for r in scan_watchlist():
        if r['patterns']:
            print(f"\n{r['name']}（{r['code']}）:")
            for p in r['patterns']:
                print(f"  📌 {p}")
        else:
            print(f"\n{r['name']}: 无明显形态")
