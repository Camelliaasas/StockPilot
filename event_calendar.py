"""事件日历：最近的重要事件（宏观数据/央行会议——未来30天内最近5个）"""
import sys, os
from datetime import datetime, timedelta
import calendar
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def next_events(days=30):
    """未来 30 天内的最近重要事件"""
    today = datetime.now()
    events = []
    # 每种事件找未来 30 天内的发生日
    rules = [
        (lambda d: d.day == 1, '📊 PMI 制造业指数发布'),
        (lambda d: d.day == 9, '📊 CPI/PPI 通胀数据'),
        (lambda d: d.day == 20, '🏦 LPR 利率报价公布'),
        (lambda d: d.day == 31, '📊 月度宏观数据确认'),
        (lambda d: d.day == calendar.weekday(d.year, d.month, min(x for x in range(1, 8) if calendar.weekday(d.year, d.month, x) == 4)) if False else (lambda dd: dd.day == min(x for x in range(1, 8) if calendar.weekday(dd.year, dd.month, x) == 4))(d), '🇺🇸 美国非农就业数据'),
        (lambda d: (d.month == 4 and d.day == 30) or (d.month == 8 and d.day == 31) or (d.month == 10 and d.day == 31), '📋 财报披露截止'),
    ]
    for i in range(days):
        d = today + timedelta(days=i)
        for cond, desc in rules:
            try:
                if cond(d):
                    events.append((d, desc))
            except Exception:
                pass
    return events[:8]

def main():
    print('📅 最近重要事件（未来 30 天内）:')
    print('=' * 50)
    ev = next_events()
    if not ev:
        print('  （近期无重大事件窗口）')
    for d, desc in ev:
        delta = (d - datetime.now()).days
        print(f'  {d.strftime("%m-%d")}（{delta}天后）: {desc}')
    print()
    print('💡 事件提醒：数据发布日市场波动加大——注意仓位管理')

if __name__ == '__main__':
    main()
