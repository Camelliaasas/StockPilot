"""估值分位引擎：PE/PB 历史分位——判断"贵不贵"——决策卡/研报引用"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def valuation(code, name=''):
    """估值分析：PE(TTM) 历史分位 + 结论"""
    code = str(code).replace('sh', '').replace('sz', '').replace('bj', '').strip()
    result = {'code': code, 'name': name, 'pe': None, 'pe_pct': None, 'pb': None, 'pb_pct': None, 'verdict': ''}
    # PE 历史
    try:
        df = ak.stock_zh_valuation_baidu(symbol=code, indicator='市盈率(TTM)', period='全部')
        if df is not None and len(df) > 100:
            pe = df['value'].dropna()
            cur = pe.iloc[-1]
            pct = (pe < cur).mean() * 100
            result['pe'] = round(float(cur), 2)
            result['pe_pct'] = round(float(pct))
    except Exception as e:
        result['pe_err'] = str(e)[:40]
    # PB 历史
    try:
        df2 = ak.stock_zh_valuation_baidu(symbol=code, indicator='市净率', period='全部')
        if df2 is not None and len(df2) > 100:
            pb = df2['value'].dropna()
            cur = pb.iloc[-1]
            pct = (pb < cur).mean() * 100
            result['pb'] = round(float(cur), 2)
            result['pb_pct'] = round(float(pct))
    except Exception:
        pass
    # 结论
    if result['pe_pct'] is not None:
        p = result['pe_pct']
        if p >= 80: result['verdict'] = f'🔴 偏贵（PE 处于历史 {p}% 分位——高于 80% 时间）'
        elif p >= 50: result['verdict'] = f'🟡 中性（PE 处于历史 {p}% 分位）'
        elif p >= 20: result['verdict'] = f'🟢 偏便宜（PE 处于历史 {p}% 分位——低于 80% 时间）'
        else: result['verdict'] = f'💎 极便宜（PE 处于历史 {p}% 分位——低于 20% 时间）'
    else:
        result['verdict'] = '估值数据不足'
    return result

if __name__ == '__main__':
    for code, name in [('600519', '贵州茅台'), ('300750', '宁德时代'), ('603259', '药明康德'), ('601318', '中国平安')]:
        v = valuation(code, name)
        print(f"\n📊 估值：{v['name']}（{v['code']}）")
        if v.get('pe') is not None:
            print(f"  PE(TTM): {v['pe']}（历史 {v['pe_pct']}% 分位）")
        if v.get('pb') is not None:
            print(f"  PB: {v['pb']}（历史 {v['pb_pct']}% 分位）")
        print(f"  结论: {v['verdict']}")
