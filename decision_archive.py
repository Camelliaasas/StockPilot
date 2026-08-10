"""决策卡存档：每日决策保存 reports/decision_YYYYMMDD.md——历史可查"""
import os
os.environ['TQDM_DISABLE'] = '1'
import sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, 'C:/Users/23643/src_workflow/stock_predict')
import akshare as ak
from decision_card import decision, get_watchlist, get_spot

def main():
    try:
        news = [f'{r["标题"]}' for _, r in ak.stock_info_global_em().head(6).iterrows()]
    except Exception:
        news = []
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
    os.makedirs(out_dir, exist_ok=True)
    lines = [f'# 每日决策卡 {datetime.now().strftime("%Y-%m-%d")}', '']
    for code, name in get_watchlist():
        try:
            d = decision(code, name, news)
            spot = get_spot(code)
            price = spot['price'] if spot else '—'
            lines.append(f"## {d['name']}（{d['code']}）现价 {price}")
            if d.get('inst'): lines.append(f"- 机构: {d['inst']}")
            if d.get('val'): lines.append(f"- 估值: {d['val']}")
            if d.get('chip'): lines.append(f"- 筹码: {d['chip']}")
            lines.append(f"- 技术[{d['tech']}] 基本面[{d['fund']}] 新闻[{d['news']}] 综合分[{d['score']:+d}]")
            lines.append(f"- **决策: {d['action']} | 仓位 {d['position']}**")
            lines.append('')
        except Exception as e:
            lines.append(f'## {name}: 生成失败 {str(e)[:40]}')
            lines.append('')
    lines.append('---')
    lines.append('⚠️ 仅供参考——非投资建议')
    fn = os.path.join(out_dir, f'decision_{datetime.now().strftime("%Y%m%d")}.md')
    with open(fn, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'✅ 决策卡已存档: {fn}')

if __name__ == '__main__':
    main()
