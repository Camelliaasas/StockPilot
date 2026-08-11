"""每日决策卡：每只自选股明确决策（买入/持有/卖出/观望）+ 仓位建议 + 实时价"""
import sys, os, json
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn
from sentiment_llm import llm_analyze, get_llm_key
from diagnose import diagnose

WATCHLIST = [('600519', '贵州茅台'), ('300750', '宁德时代'), ('603259', '药明康德'),
             ('601318', '中国平安'), ('600036', '招商银行'), ('002594', '比亚迪'),
             ('601012', '隆基绿能'), ('000858', '五粮液')]

def get_spot(code):
    """实时行情（spot）"""
    symbol = ('sh' if code.startswith('6') else 'sz') + code
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df['代码'] == code]
        if len(row) > 0:
            r = row.iloc[0]
            return {'price': float(r['最新价']), 'change': float(r['涨跌幅']), 'name': r['名称']}
    except Exception:
        pass
    # 备选：日线最后价
    try:
        d = ak.stock_zh_a_daily(symbol=symbol, start_date='20260801', end_date='20260810', adjust='qfq')
        if d is not None and len(d) > 0:
            last = d.iloc[-1]
            prev = d.iloc[-2]
            return {'price': round(float(last['close']), 2), 'change': round((float(last['close'])/float(prev['close'])-1)*100, 2), 'name': ''}
    except Exception:
        pass
    return None

def fast_decision(code, name, news=None):
    """快速决策（看板用——DB 秒查——不调外部接口——0.5 秒/只）"""
    symbol = ('sh' if code.startswith('6') else 'sz') + code
    tech = '观望'
    tech_score = 0
    bias = 0.0
    try:
        import joblib as _jb
        import numpy as _np
        import pandas as _pd
        m = _jb.load('C:/Users/23643/src_workflow/stock_predict/model_stock_binary_full.joblib')
        # 从本地 DB 读（秒级——不调腾讯）
        from db import get_conn as _gc
        _conn = _gc()
        rows = _conn.execute("SELECT date, open, high, low, close, volume FROM daily_prices WHERE code=? ORDER BY date DESC LIMIT 70", (int(code),)).fetchall()
        _conn.close()
        if rows and len(rows) > 30:
            df = _pd.DataFrame([dict(r) for r in rows][::-1])
            c = df['close']
            last_close = float(c.iloc[-1])
            feats_row = [float(c.pct_change().iloc[-1]),
                         float(c.rolling(5).mean().iloc[-1]) / last_close - 1,
                         float(c.rolling(20).mean().iloc[-1]) / last_close - 1,
                         float(c.rolling(60).mean().iloc[-1]) / last_close - 1,
                         0.0, 0.0, 50.0, 1.0, 0.01, 0, 0, 0, 0.0, 0.0, 0, 0.0, 1.0, 1.0,
                         0.0, 50.0, 50.0, 0, 0.0, 25.0, 0, 50.0, 0.0, 0.0, 0, 0, 0]
            x = _np.nan_to_num(_np.array([feats_row[:m.n_features_in_]]), nan=0.0)
            proba = m.predict_proba(x)[0]
            up = float(proba[list(m.classes_).index(1)]) if 1 in m.classes_ else 0.5
            if up >= 0.58:
                tech, tech_score = '买入', 2
            elif up >= 0.52:
                tech, tech_score = '持有', 1
            elif up <= 0.42:
                tech, tech_score = '卖出', -2
            elif up <= 0.48:
                tech, tech_score = '减持', -1
    except Exception:
        pass
    # 基本面（DB 财务）
    fund = '中'
    fund_score = 0
    try:
        from db import get_conn
        conn = get_conn()
        row = conn.execute("SELECT roe, revenue_yoy FROM financials WHERE code=? ORDER BY report_date DESC LIMIT 1", (int(code),)).fetchone()
        conn.close()
        if row:
            roe, rev = row['roe'], row['revenue_yoy']
            if roe > 15 and rev > 10:
                fund, fund_score = '强', 2
            elif roe > 8:
                fund, fund_score = '中', 0
            else:
                fund, fund_score = '弱', -1
    except Exception:
        pass
    score = tech_score + fund_score
    if score >= 3:
        act, pos = '买入', '30%'
    elif score >= 1:
        act, pos = '持有', '20%'
    elif score <= -2:
        act, pos = '卖出', '0%'
    else:
        act, pos = '观望', '10%'
    return {'code': code, 'name': name, 'tech': tech, 'fund': fund, 'news': '—',
            'score': score, 'action': act, 'position': pos, 'bias': bias, 'inst': '', 'val': '', 'chip': ''}

def decision(code, name, news):
    """单只决策：技术信号 + 基本面 + 新闻 → 明确决策 + 仓位"""
    symbol = ('sh' if code.startswith('6') else 'sz') + code
    # 技术信号（ML 二分类——54.8% 验证——优于三分类）
    tech = '观望'
    tech_score = 0
    bias = 0.0
    try:
        import joblib as _jb
        import numpy as _np
        m = _jb.load('C:/Users/23643/src_workflow/stock_predict/model_stock_binary_full.joblib')
        df = ak.stock_zh_a_daily(symbol=symbol, start_date='20260101', end_date='20260810', adjust='qfq')
        if df is not None and len(df) > 30:
            c = df['close'].reset_index(drop=True)
            last_close = float(c.iloc[-1])
            feats_row = [float(c.pct_change().iloc[-1]),
                         float(c.rolling(5).mean().iloc[-1]) / last_close - 1,
                         float(c.rolling(20).mean().iloc[-1]) / last_close - 1,
                         float(c.rolling(60).mean().iloc[-1]) / last_close - 1,
                         0.0, 0.0, 50.0, 1.0, 0.01, 0, 0, 0, 0.0, 0.0, 0, 0.0, 1.0, 1.0,
                         0.0, 50.0, 50.0, 0, 0.0, 25.0, 0, 50.0, 0.0, 0.0, 0, 0, 0]
            x = _np.nan_to_num(_np.array([feats_row[:m.n_features_in_]]), nan=0.0)
            proba = m.predict_proba(x)[0]
            up = float(proba[list(m.classes_).index(1)]) if 1 in m.classes_ else 0.5
            if up >= 0.58:
                tech, tech_score = '买入', 2
            elif up >= 0.52:
                tech, tech_score = '持有', 1
            elif up <= 0.42:
                tech, tech_score = '卖出', -2
            elif up <= 0.48:
                tech, tech_score = '减持', -1
    except Exception:
        pass
        # 强度（乖离率）
        bias = (c.iloc[-1] / ma10.iloc[-1] - 1) * 100
    except Exception:
        bias = 0
    # 基本面
    try:
        conn = get_conn()
        f = conn.execute("SELECT * FROM financials WHERE code=? ORDER BY report_date DESC LIMIT 1", (code,)).fetchone()
        conn.close()
        fund = '多' if (f and f['roe'] and f['roe'] > 8 and f['revenue_yoy'] and f['revenue_yoy'] > 5) else ('空' if (f and f['roe'] and f['roe'] < 5) else '中')
    except Exception:
        fund = '中'
    # 新闻情绪（LLM）
    nl = llm_analyze(name, news)
    news_dir = nl.get('direction', '观望')
    # 机构预期（研报——数据深度）
    inst = ''
    try:
        r = ak.stock_research_report_em(symbol=code)
        if r is not None and len(r) > 0:
            top = r.iloc[0]
            inst = f'{top["机构"]} {top["东财评级"]}（{top["2026-盈利预测-市盈率"]}x）'
    except Exception:
        inst = ''
    # 估值分位（贵/便宜——价值判断）
    val = ''
    val_score = 0
    try:
        from valuation import valuation as val_fn
        v = val_fn(code, name)
        if v.get('pe_pct') is not None:
            p = v['pe_pct']
            val = f'PE{v["pe"]} 历史{p}%分位'
            if p < 20: val_score = 1; val += '（极便宜）'
            elif p < 50: val_score = 1; val += '（偏便宜）'
            elif p > 80: val_score = -1; val += '（偏贵）'
    except Exception:
        pass
    # 筹码信号（股东户数变化）
    chip = ''
    chip_score = 0
    try:
        from chip_signal import chip_signal as chip_fn
        cr = chip_fn(code, name)
        sig = cr.get('signal', '')
        if '集中' in sig:
            chip_score = 1
            chip = sig
        elif '分散' in sig:
            chip_score = -1
            chip = sig
    except Exception:
        pass
    # 决策表
    score = 0
    score += 2 if tech == '买入' else (1 if tech == '持有' else (-1 if tech == '卖出' else 0))
    score += 1 if fund == '多' else (-1 if fund == '空' else 0)
    score += 1 if news_dir == '看多' else (-1 if news_dir == '看空' else 0)
    score += val_score + chip_score
    if score >= 3: act, pos = '买入', '30%'
    elif score >= 1: act, pos = '持有', '20%'
    elif score <= -2: act, pos = '卖出', '0%'
    else: act, pos = '观望', '10%'
    return {'code': code, 'name': name, 'tech': tech, 'fund': fund, 'news': news_dir,
            'score': score, 'action': act, 'position': pos, 'bias': bias, 'inst': inst, 'val': val, 'chip': chip}

def get_watchlist():
    """自选股（DB——用户可自定义）"""
    try:
        from db import get_conn
        conn = get_conn()
        rows = conn.execute('SELECT code, name FROM watchlist ORDER BY added_at').fetchall()
        conn.close()
        if rows:
            return [(r['code'], r['name']) for r in rows]
    except Exception:
        pass
    return WATCHLIST  # 兜底默认

def main():
    try:
        news = [f'{r["标题"]}' for _, r in ak.stock_info_global_em().head(8).iterrows()]
    except Exception:
        news = []
    watch = get_watchlist()
    print('=' * 62)
    print('📋 每日决策卡（技术MA5/10 + 基本面 + 新闻情绪 → 明确决策）')
    print('=' * 62)
    cards = []
    for code, name in watch:
        spot = get_spot(code)
        d = decision(code, name, news)
        price = spot['price'] if spot else '—'
        chg = spot['change'] if spot else None
        chg_txt = f' ({chg:+.1f}%)' if chg is not None else ''
        icon = {'买入': '🔴', '持有': '🟡', '卖出': '🟢', '观望': '⚪'}[d['action']]
        print(f"\n{icon} {d['name']}（{d['code']}）现价 {price}{chg_txt}")
        if d.get('inst'):
            print(f"   🏦 机构: {d['inst']}")
        if d.get('val'):
            print(f"   💰 估值: {d['val']}")
        if d.get('chip'):
            print(f"   🎯 筹码: {d['chip']}")
        print(f"   技术[{d['tech']}] 基本面[{d['fund']}] 新闻[{d['news']}] 综合分[{d['score']:+d}]")
        print(f"   → 决策：{d['action']} | 建议仓位 {d['position']}")
        cards.append(d)
    print('\n' + '=' * 62)
    buys = [c for c in cards if c['action'] == '买入']
    sells = [c for c in cards if c['action'] == '卖出']
    if buys:
        print(f'🔴 建议买入: {", ".join(c["name"] for c in buys)}')
    if sells:
        print(f'🟢 建议卖出: {", ".join(c["name"] for c in sells)}')
    print('⚠️ 决策仅供参考——非投资建议')

if __name__ == '__main__':
    main()
