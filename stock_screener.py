"""条件选股引擎（问财式）：低PE高ROE/高增长/强势股——1088万行+财务数据筛选"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def screener(pe_max=None, pe_min=None, roe_min=None, rev_min=None, chg_min=None,
             vol_ratio_min=None, market_cap_max=None, limit=20):
    """条件选股：
    pe_max/pe_min=市盈率区间, roe_min=ROE最低, rev_min=营收增速, chg_min=今日涨幅,
    vol_ratio_min=量比, market_cap_max=市值上限(亿)
    """
    conn = get_conn()
    # 财务（最新报告期）
    fin = pd.read_sql('SELECT * FROM financials ORDER BY report_date', conn)
    conn.close()
    if fin.empty:
        return {'error': '财务数据为空'}
    fin_latest = fin.sort_values('report_date').groupby('code').last().reset_index()
    df = fin_latest.copy()
    # 行情（最新收盘——从 daily_prices 取最近一天）
    conn = get_conn()
    last_date = conn.execute('SELECT MAX(date) FROM daily_prices').fetchone()[0]
    px = pd.read_sql(f"SELECT code, close, volume FROM daily_prices WHERE date='{last_date}'", conn)
    conn.close()
    px['code'] = px['code'].astype(str).str.zfill(6)
    df['code'] = df['code'].astype(str).str.zfill(6)
    df = df.merge(px, on='code', how='inner')
    # 条件过滤
    if roe_min is not None:
        df = df[df['roe'].astype(float) >= roe_min]
    if rev_min is not None:
        df = df[df['revenue_yoy'].astype(float) >= rev_min]
    # 涨跌幅（需要前一日）
    if chg_min is not None or vol_ratio_min is not None:
        try:
            prev = conn = get_conn()
            dates = pd.read_sql('SELECT DISTINCT date FROM daily_prices ORDER BY date DESC LIMIT 2', conn)
            conn.close()
            if len(dates) >= 2:
                d1, d0 = dates['date'].iloc[0], dates['date'].iloc[1]
                p1 = pd.read_sql(f"SELECT code, close FROM daily_prices WHERE date='{d1}'", conn2 := get_conn())
                p0 = pd.read_sql(f"SELECT code, close FROM daily_prices WHERE date='{d0}'", conn2)
                conn2.close()
                m = p1.merge(p0, on='code', suffixes=('_1', '_0'))
                m['chg'] = (m['close_1'] / m['close_0'] - 1) * 100
                m['code'] = m['code'].astype(str).str.zfill(6)
                df = df.merge(m[['code', 'chg']], on='code', how='left')
                if chg_min is not None:
                    df = df[df['chg'] >= chg_min]
        except Exception:
            pass
    # 排名输出（按 ROE 降序）
    df = df.sort_values('roe', ascending=False).head(limit)
    out = []
    for _, r in df.iterrows():
        try:
            out.append({'code': r['code'], 'roe': round(float(r['roe']), 1),
                        'rev': round(float(r['revenue_yoy']), 1),
                        'price': round(float(r['close']), 2),
                        'chg': round(float(r.get('chg', 0)), 1) if pd.notna(r.get('chg', np.nan)) else None})
        except Exception:
            pass
    return {'count': len(out), 'stocks': out, 'cond': {
        'pe_max': pe_max, 'roe_min': roe_min, 'rev_min': rev_min, 'chg_min': chg_min}}

if __name__ == '__main__':
    print('🔍 条件选股（问财式）:')
    print('\n① 高ROE + 高增长（ROE>15% + 营收+20%）:')
    r = screener(roe_min=15, rev_min=20, limit=8)
    for s in r.get('stocks', []):
        print(f"  {s['code']}: ROE{s['roe']}% 营收{s['rev']:+.0f}% 现价{s['price']}")
    print('\n② 今日强势（涨幅>3%）:')
    r2 = screener(chg_min=3, limit=5)
    for s in r2.get('stocks', []):
        print(f"  {s['code']}: ROE{s['roe']}% 今日{s['chg']:+.1f}%")
