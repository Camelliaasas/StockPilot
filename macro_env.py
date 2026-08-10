"""宏观环境引擎：CPI/PMI/社融/M2/LPR → 经济环境状态（预测输入）"""
import sys, os
import akshare as ak
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def macro_env():
    """宏观环境：通胀/景气/流动性/利率 → 状态判断"""
    env = {'cpi': None, 'pmi': None, 'm2': None, 'lpr': None, 'shrzgm': None, 'verdict': ''}
    # CPI（最新同比）
    try:
        cpi = ak.macro_china_cpi_yearly()
        row = cpi[cpi['商品'] == '全国-当月同比'].iloc[-1]
        env['cpi'] = float(row['今值'])
        # 趋势（近 6 期）
        vals = cpi[cpi['商品'] == '全国-当月同比']['今值'].tail(6).astype(float)
        env['cpi_trend'] = '上行' if vals.iloc[-1] > vals.iloc[0] else '下行'
    except Exception:
        pass
    # PMI（最新）
    try:
        pmi = ak.macro_china_pmi_yearly()
        row = pmi[pmi['商品'] == '制造业-指数'].iloc[-1] if (pmi['商品'] == '制造业-指数').any() else pmi.iloc[-1]
        env['pmi'] = float(row['今值'])
    except Exception:
        pass
    # M2 同比
    try:
        m2 = ak.macro_china_money_supply()
        col = [c for c in m2.columns if '同比增长' in c and 'M2' in c]
        if col:
            env['m2'] = float(m2[col[0]].iloc[-1])
    except Exception:
        pass
    # LPR（最新 1 年）
    try:
        lpr = ak.macro_china_lpr()
        env['lpr'] = float(lpr['LPR1Y'].iloc[-1])
        env['lpr_prev'] = float(lpr['LPR1Y'].iloc[-2])
    except Exception:
        pass
    # 社融（最新月增量——万亿）
    try:
        s = ak.macro_china_shrzgm()
        env['shrzgm'] = float(s['社会融资规模增量'].iloc[-1]) / 1e8
    except Exception:
        pass
    # 综合判断
    score = 0
    parts = []
    if env.get('cpi') is not None:
        c = env['cpi']
        if c > 3: score -= 1; parts.append(f'CPI {c:.1f}% 通胀偏高')
        elif c < 0: score -= 1; parts.append(f'CPI {c:.1f}% 通缩风险')
        else: score += 1; parts.append(f'CPI {c:.1f}% 温和')
    if env.get('pmi') is not None:
        p = env['pmi']
        if p > 50: score += 1; parts.append(f'PMI {p:.1f} 景气扩张')
        else: score -= 1; parts.append(f'PMI {p:.1f} 收缩')
    if env.get('m2') is not None:
        m = env['m2']
        if m > 10: score += 1; parts.append(f'M2 {m:.1f}% 流动性宽松')
        elif m < 8: score -= 1; parts.append(f'M2 {m:.1f}% 流动性收紧')
        else: parts.append(f'M2 {m:.1f}% 中性')
    if env.get('lpr') is not None and env.get('lpr_prev') is not None:
        if env['lpr'] < env['lpr_prev']: score += 1; parts.append('LPR 下调（宽松）')
        elif env['lpr'] > env['lpr_prev']: score -= 1; parts.append('LPR 上调（收紧）')
        else: parts.append(f'LPR {env["lpr"]}% 持平')
    if score >= 3: env['verdict'] = '🟢 经济环境偏暖（通胀温和+景气扩张+流动性宽松）——利好风险资产'
    elif score >= 1: env['verdict'] = '🟡 经济环境中性（多空平衡）'
    else: env['verdict'] = '🔴 经济环境偏冷（通胀/景气/流动性有压力）——风险资产承压'
    env['parts'] = parts
    return env

if __name__ == '__main__':
    e = macro_env()
    print('📊 宏观环境：')
    for p in e.get('parts', []):
        print(f'  · {p}')
    print(f'  判断: {e["verdict"]}')
