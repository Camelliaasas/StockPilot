"""个股体检报告：一键全维度诊断（基本面+技术+趋势+情绪+资金——打分）"""
import sys, os, json
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def diagnose(code, name=''):
    """生成个股体检报告——各项打分（0-100）+ 结论"""
    code = str(code).replace('sh', '').replace('sz', '').replace('bj', '').strip()
    symbol = ('sh' if code.startswith('6') else 'sz') + code
    report = {'code': code, 'name': name, 'scores': {}, 'summary': [], 'conclusion': ''}
    # 1. 技术面（趋势/均线/MACD/RSI）
    try:
        df = ak.stock_zh_a_daily(symbol=symbol, start_date='20240101', end_date='20260810', adjust='qfq')
        if df is not None and len(df) > 60:
            c = df['close']
            ma20 = c.rolling(20).mean().iloc[-1]
            ma60 = c.rolling(60).mean().iloc[-1]
            cur = c.iloc[-1]
            # 趋势分
            trend = 0
            if cur > ma20: trend += 40
            if cur > ma60: trend += 30
            if ma20 > ma60: trend += 30
            report['scores']['技术趋势'] = trend
            # 动量（20日）
            mom = (cur / c.iloc[-21] - 1) * 100
            report['scores']['动量'] = min(max(50 + mom * 2, 0), 100)
            # 波动风险（振幅）
            amp = ((df['high'] - df['low']) / c).tail(20).mean() * 100
            report['scores']['波动风险'] = min(amp * 8, 100)
            report['summary'].append(f'股价{cur:.2f} | 20日涨幅{mom:+.1f}% | 20日均线{"上" if cur>ma20 else "下"}方')
    except Exception as e:
        report['summary'].append(f'技术数据失败: {str(e)[:40]}')
    # 2. 基本面（财务）
    try:
        conn = get_conn()
        f = conn.execute("SELECT * FROM financials WHERE code=? ORDER BY report_date DESC LIMIT 1", (code,)).fetchone()
        conn.close()
        if f:
            score = 50
            det = []
            if f['roe'] and f['roe'] > 10: score += 15; det.append(f'ROE {f["roe"]:.1f}%')
            if f['roe'] and f['roe'] < 5: score -= 15
            if f['revenue_yoy'] and f['revenue_yoy'] > 20: score += 20; det.append(f'营收+{f["revenue_yoy"]:.0f}%')
            if f['revenue_yoy'] and f['revenue_yoy'] < 0: score -= 20
            if f['profit_yoy'] and f['profit_yoy'] > 20: score += 15; det.append(f'利润+{f["profit_yoy"]:.0f}%')
            if f['profit_yoy'] and f['profit_yoy'] < 0: score -= 15
            report['scores']['基本面'] = min(max(score, 0), 100)
            report['summary'].append('财务: ' + ' | '.join(det) if det else '财务数据有限')
        else:
            report['scores']['基本面'] = 50
            report['summary'].append('财务: 无数据')
    except Exception:
        report['scores']['基本面'] = 50
    # 3. 市场情绪（新闻板块）
    try:
        conn = get_conn()
        news = conn.execute("SELECT sector, impact, strength, level FROM news WHERE sector IS NOT NULL AND sector != '' ORDER BY id DESC LIMIT 30").fetchall()
        conn.close()
        # 找相关板块新闻（简化：看全市场情绪——近期利好利空比）
        pos = sum(1 for n in news if n['impact'] == '利好')
        neg = sum(1 for n in news if n['impact'] == '利空')
        if pos + neg > 0:
            senti = pos / (pos + neg) * 100
            report['scores']['市场情绪'] = senti
            report['summary'].append(f'近期新闻情绪: 利好{pos}/利空{neg}')
        else:
            report['scores']['市场情绪'] = 50
    except Exception:
        report['scores']['市场情绪'] = 50
    # 4. 综合
    scores = report['scores']
    total = sum(scores.values()) / len(scores) if scores else 50
    report['scores']['综合'] = round(total, 1)
    if total >= 70: report['conclusion'] = '🟢 强势（多维度向好——关注回调机会）'
    elif total >= 55: report['conclusion'] = '🔵 稳健（整体健康——可关注）'
    elif total >= 40: report['conclusion'] = '🟡 中性（多空均衡——观望为主）'
    else: report['conclusion'] = '🔴 弱势（多维度承压——谨慎）'
    return report

if __name__ == '__main__':
    for code, name in [('600519', '贵州茅台'), ('300750', '宁德时代'), ('603259', '药明康德'), ('601318', '中国平安')]:
        r = diagnose(code, name)
        print(f"\n📋 体检报告：{r['name']}（{r['code']}）")
        for k, v in r['scores'].items():
            print(f'  {k}: {v:.0f}')
        print(f'  结论: {r["conclusion"]}')
        for s in r['summary']:
            print(f'  📝 {s}')
