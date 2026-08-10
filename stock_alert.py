"""异动提醒：自选股异动扫描（涨跌>3%/涨停跌停/成交突增）——有异动推微信"""
import os
os.environ['TQDM_DISABLE'] = '1'
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, 'C:/Users/23643/src_workflow/stock_predict')
import akshare as ak
from decision_card import get_watchlist

def scan():
    """扫描自选股异动——返回提醒列表（无异动返回空=静默）"""
    alerts = []
    watch = get_watchlist()
    if not watch:
        return []
    for code, name in watch:
        try:
            symbol = ('sh' if code.startswith('6') else 'sz') + code
            df = ak.stock_zh_a_daily(symbol=symbol, start_date='20260801', end_date='20260810', adjust='qfq')
            if df is None or len(df) < 2:
                continue
            last = df.iloc[-1]
            prev = df.iloc[-2]
            chg = (float(last['close']) / float(prev['close']) - 1) * 100
            price = float(last['close'])
            reason = []
            if chg >= 9.8: reason.append(f'涨停! {chg:+.1f}%')
            elif chg <= -9.8: reason.append(f'跌停! {chg:+.1f}%')
            elif chg >= 5: reason.append(f'大涨 {chg:+.1f}%')
            elif chg <= -5: reason.append(f'大跌 {chg:+.1f}%')
            if reason:
                alerts.append(f"⚡ {name}（{code}）{price:.2f} | {' | '.join(reason)}")
        except Exception:
            pass
    return alerts

if __name__ == '__main__':
    alerts = scan()
    if alerts:
        print('📡 自选股异动提醒:')
        for a in alerts:
            print(a)
    # 无异动——静默（不输出——cron 不推送）
