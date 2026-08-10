"""风险预警：持仓波动/回撤/集中度/异动提醒"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def load_hist(code, days=120):
    symbol = ('sh' if code.startswith('6') else 'sz') + code
    try:
        df = ak.stock_zh_a_daily(symbol=symbol, start_date='20260101', end_date='20260810', adjust='qfq')
        return df.tail(days)
    except Exception:
        return None

def check_risk(positions):
    """风险检查：positions = [(code, name, weight_pct)]"""
    print('=' * 56)
    print('🚨 风险预警扫描')
    print('=' * 56)
    alerts = []
    total_w = sum(w for _, _, w in positions)
    # 集中度
    for code, name, w in positions:
        if w / total_w > 0.4:
            alerts.append(f'⚠️ 集中度风险: {name} 占 {w/total_w*100:.0f}% —— 超过 40%（单票过重）')
    # 个股波动/回撤
    for code, name, w in positions:
        df = load_hist(code)
        if df is None or len(df) < 30:
            continue
        c = df['close']
        ret = c.pct_change().dropna()
        vol = ret.std() * np.sqrt(250) * 100
        dd = (c / c.cummax() - 1).min() * 100
        if vol > 50:
            alerts.append(f'🔴 波动风险: {name} 年化波动 {vol:.0f}% —— 高波动（>50%）')
        if dd < -20:
            alerts.append(f'🔴 回撤风险: {name} 区间回撤 {dd:.0f}% —— 深度回撤（<-20%）')
        # 异动（今日）
        last_ret = ret.iloc[-1] * 100
        if abs(last_ret) > 5:
            alerts.append(f'⚡ 异动: {name} 今日 {last_ret:+.1f}% —— 大幅波动')
    # 组合相关
    rets = {}
    for code, name, w in positions:
        df = load_hist(code)
        if df is not None and len(df) > 30:
            rets[name] = df['close'].pct_change().dropna()
    if len(rets) >= 2:
        df = pd.DataFrame(rets).dropna()
        corr = df.corr()
        for i in range(len(corr)):
            for j in range(i + 1, len(corr)):
                if abs(corr.iloc[i, j]) > 0.75:
                    alerts.append(f'🔗 相关性风险: {corr.index[i]}↔{corr.columns[j]} 相关 {corr.iloc[i,j]:.2f}（同涨同跌——分散失效）')
    if not alerts:
        print('\n✅ 无重大风险信号（持仓健康）')
    else:
        print(f'\n发现 {len(alerts)} 条预警:')
        for a in alerts:
            print('  ' + a)
    print('\n⚠️ 仅供参考——风险识别非投资建议')

if __name__ == '__main__':
    demo = [('600519', '茅台', 30), ('300750', '宁德', 25), ('603259', '药明', 25),
            ('601318', '平安', 10), ('600036', '招行', 10)]
    check_risk(demo)
