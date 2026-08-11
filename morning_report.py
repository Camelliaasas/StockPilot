"""每日全景晨报：宏观+决策卡+估值+筹码+风险+一句话——完整推送版"""
import os
os.environ['TQDM_DISABLE'] = '1'
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import akshare as ak
from decision_card import decision, get_watchlist, get_spot

def main():
    try:
        news = [f'{r["标题"]}' for _, r in ak.stock_info_global_em().head(6).iterrows()]
    except Exception:
        news = []
    lines = ['🌅 **每日全景晨报**', '']
    # 宏观
    try:
        from macro_env import macro_env
        me = macro_env()
        lines.append('**🌐 宏观环境**')
        for p in me.get('parts', []):
            lines.append(f'· {p}')
        lines.append(f'→ {me.get("verdict", "")}')
    except Exception:
        pass
    # 一句话
    try:
        from one_line import one_line
        lines.append('')
        lines.append(f'**📌 一句话看盘**: {one_line()}')
    except Exception:
        pass
    # 事件日历
    try:
        from event_calendar import next_events
        ev = next_events()
        if ev:
            lines.append('')
            lines.append('**📅 近期事件提醒**')
            for d, desc in ev[:3]:
                delta = (d - datetime.now()).days
                lines.append(f'· {d.strftime("%m-%d")}（{delta}天）: {desc}')
    except Exception:
        pass
    # 决策卡
    lines.append('')
    lines.append('**📋 自选决策**')
    for code, name in get_watchlist():
        try:
            spot = get_spot(code)
            d = decision(code, name, news)
            price = spot['price'] if spot else '—'
            chg = f" ({spot['change']:+.1f}%)" if spot and spot.get('change') is not None else ''
            icon = {'买入': '🔴', '持有': '🟡', '卖出': '🟢', '观望': '⚪'}[d['action']]
            lines.append(f"{icon} {d['name']} {price}{chg} → {d['action']}（仓位{d['position']}）")
        except Exception:
            pass
    # 持仓盈亏
    try:
        from db import get_conn
        conn = get_conn()
        poses = conn.execute('SELECT * FROM positions').fetchall()
        conn.close()
        if poses:
            lines.append('')
            lines.append('**💼 我的持仓**')
            total_pnl = 0
            for r in poses[:6]:
                try:
                    p = conn2 = get_conn()
                    pr = p.execute("SELECT close FROM daily_prices WHERE code=? ORDER BY date DESC LIMIT 1", (int(r['code']),)).fetchone()
                    p.close()
                    if pr:
                        cur = float(pr['close'])
                        pnl = (cur - r['cost']) * r['shares']
                        total_pnl += pnl
                        icon = '🔴' if pnl >= 0 else '🟢'
                        lines.append(f"{icon} {r['name']} ×{r['shares']:.0f} 现价{cur:.2f} 盈亏{pnl:+,.0f}")
                except Exception:
                    pass
            if total_pnl != 0:
                lines.append(f"· 持仓总盈亏: **{total_pnl:+,.0f}**")
    except Exception:
        pass
    # 风险预警
    try:
        from risk_alert import load_hist
        alerts = []
        for code, name in get_watchlist():
            df = load_hist(code)
            if df is not None and len(df) > 30:
                c = df['close']
                dd = (c / c.cummax() - 1).min() * 100
                if dd < -20:
                    alerts.append(f'⚠️ {name} 回撤{dd:.0f}%')
        if alerts:
            lines.append('')
            lines.append('**🚨 风险提醒**')
            lines.extend(f'· {a}' for a in alerts[:3])
    except Exception:
        pass
    lines.append('')
    lines.append('---')
    lines.append('⚠️ 仅供参考，非投资建议。数据：腾讯/AKShare（免费源）。')
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
