"""每日预测报告生成（08:00 推送——微信）"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def generate_report():
    conn = get_conn()
    # 最新预测
    preds = conn.execute("SELECT * FROM predictions WHERE date >= date('now','-2 day') ORDER BY date DESC, code LIMIT 10").fetchall()
    # 最近验证统计
    stats = conn.execute("SELECT COUNT(*), SUM(correct) FROM predictions WHERE correct IS NOT NULL").fetchone()
    # 最近规律（模型线索）
    lines = []
    lines.append('📊 **股票 AI 预测报告**')
    lines.append(f'（{os.popen("date /t 2>nul || date +%Y-%m-%d").read().strip()} 自动生成）')
    lines.append('')
    if preds:
        lines.append('### 🔮 最新预测')
        for p in preds:
            conf = f'{p["confidence"]*100:.0f}%' if p['confidence'] <= 1 else f'{p["confidence"]:.0f}%'
            lines.append(f'- {p["code"]}: **{p["direction"]}**（置信{conf}）')
            if p.get('reason'):
                lines.append(f'  📝 {p["reason"][:80]}')
    else:
        lines.append('- 暂无预测（预测引擎每日 20:00 自动跑）')
    lines.append('')
    if stats and stats[0]:
        acc = stats[1] / stats[0] * 100
        lines.append(f'### 📈 预测累计验证')
        lines.append(f'- 已验证 {stats[0]} 次 | 准确率 **{acc:.0f}%**')
    lines.append('')
    lines.append('---')
    lines.append('⚠️ 预测仅供参考，非投资建议。数据源：腾讯/AKShare（免费源延迟）。')
    conn.close()
    return '\n'.join(lines)

if __name__ == '__main__':
    print(generate_report())
