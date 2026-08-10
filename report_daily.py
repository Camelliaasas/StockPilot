"""预测日报增强版：三源预测详情 + 分级 + 宏观 + 验证统计（08:00 推送）"""
import sys, os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, 'C:/Users/23643/src_workflow/stock_predict')
from db import get_conn

def generate_report():
    conn = get_conn()
    # 最新预测
    preds = conn.execute("SELECT * FROM predictions WHERE date >= date('now','-2 day') ORDER BY date DESC, code LIMIT 12").fetchall()
    # 验证统计
    stats = conn.execute("SELECT COUNT(*), SUM(correct) FROM predictions WHERE correct IS NOT NULL").fetchone()
    # 分级预测（大事件）
    trend = conn.execute("SELECT title, sector, impact, strength FROM news WHERE level='大' ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    lines = []
    lines.append('📊 **股票 AI 预测日报**')
    lines.append(f'（{datetime.now().strftime("%Y-%m-%d")}）')
    lines.append('')
    # 宏观
    try:
        from macro_env import macro_env
        me = macro_env()
        lines.append('**🌐 宏观环境**')
        for p in me.get('parts', []):
            lines.append(f'· {p}')
        lines.append(f'→ {me.get("verdict", "")}')
        lines.append('')
    except Exception:
        pass
    # 分级预测（大事件）
    if trend:
        lines.append('**🔥 大事件（中期趋势参考）**')
        for t in trend:
            lines.append(f'· [{t["sector"]}] {t["impact"]}({t["strength"]}): {t["title"][:40]}')
        lines.append('')
    # 预测
    if preds:
        lines.append('**🔮 最新三源预测**')
        for p in preds:
            p = dict(p)
            conf = f'{p["confidence"]*100:.0f}%' if p['confidence'] <= 1 else f'{p["confidence"]:.0f}%'
            lines.append(f'- {p["code"]}: **{p["direction"]}**（置信{conf}）')
            if p.get('reason'):
                lines.append(f'  📝 {p["reason"][:80]}')
        lines.append('')
    else:
        lines.append('- 暂无预测（预测引擎每日 20:00 自动跑）')
        lines.append('')
    # 验证
    if stats and stats[0]:
        acc = stats[1] / stats[0] * 100
        lines.append(f'**📈 预测累计验证**')
        lines.append(f'- 已验证 {stats[0]} 次 | 准确率 **{acc:.0f}%**')
        lines.append('')
    lines.append('---')
    lines.append('⚠️ 预测仅供参考，非投资建议。数据源：腾讯/AKShare（免费源延迟）。')
    return '\n'.join(lines)

if __name__ == '__main__':
    print(generate_report())
