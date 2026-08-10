"""决策卡推送版：干净文本（禁进度条）——每日 08:30 推送微信"""
import os
os.environ['TQDM_DISABLE'] = '1'  # 禁进度条
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decision_card import decision, WATCHLIST, get_spot
import akshare as ak

def main():
    try:
        news = [f'{r["标题"]}' for _, r in ak.stock_info_global_em().head(8).iterrows()]
    except Exception:
        news = []
    lines = ['📋 **每日决策卡**', '']
    for code, name in WATCHLIST:
        try:
            spot = get_spot(code)
            d = decision(code, name, news)
            price = spot['price'] if spot else '—'
            chg = f" ({spot['change']:+.1f}%)" if spot and spot.get('change') is not None else ''
            icon = {'买入': '🔴', '持有': '🟡', '卖出': '🟢', '观望': '⚪'}[d['action']]
            lines.append(f"{icon} **{d['name']}** {price}{chg}")
            if d.get('inst'):
                lines.append(f"  🏦 {d['inst']}")
            lines.append(f"  → {d['action']} | 仓位 {d['position']}")
        except Exception:
            continue
    lines.append('')
    lines.append('⚠️ 仅供参考，非投资建议。')
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
