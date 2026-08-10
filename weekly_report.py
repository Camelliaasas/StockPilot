"""准确率周报：每周公开预测战绩——建立信任"""
import sys, os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def weekly_report():
    conn = get_conn()
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    # 本周验证
    week = conn.execute("SELECT COUNT(*), SUM(correct) FROM predictions WHERE correct IS NOT NULL AND date >= ?", (week_ago,)).fetchone()
    total = conn.execute("SELECT COUNT(*), SUM(correct) FROM predictions WHERE correct IS NOT NULL").fetchone()
    # 分版本
    by_ver = conn.execute("SELECT code, COUNT(*), SUM(correct) FROM predictions WHERE correct IS NOT NULL GROUP BY code").fetchall()
    conn.close()
    lines = []
    lines.append('📊 **股票预测周报**')
    lines.append(f'（{datetime.now().strftime("%Y-%m-%d")}）')
    lines.append('')
    if week and week[0]:
        lines.append(f'### 📈 本周战绩')
        lines.append(f'- 验证 {week[0]} 次 | 正确 {week[1]} | **准确率 {week[1]/week[0]*100:.0f}%**')
    else:
        lines.append('- 本周暂无验证（预测每日积累中）')
    lines.append('')
    if total and total[0]:
        lines.append(f'### 📚 累计战绩')
        lines.append(f'- 累计验证 {total[0]} 次 | 准确率 **{total[1]/total[0]*100:.0f}%**')
        lines.append('')
        lines.append('### 🏷️ 分版本准确率')
        for v, n, c in by_ver:
            if n and n > 0:
                lines.append(f'- {v}: {c}/{n}（{c/n*100:.0f}%）')
    lines.append('')
    lines.append('---')
    lines.append('⚠️ 预测为参考——非投资建议。准确率公开=长期信任。')
    return '\n'.join(lines)

if __name__ == '__main__':
    print(weekly_report())
