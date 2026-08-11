"""P1 交易提醒：到价提醒（设置目标价——价格触发推送微信）"""
import os, sys, json
os.environ['TQDM_DISABLE'] = '1'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, 'C:/Users/23643/src_workflow/stock_predict')
import akshare as ak
from db import get_conn

def add_alert(code, name, target_price, direction='up'):
    """设置提醒（up=涨到目标价 / down=跌到目标价）"""
    conn = get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, name TEXT,
        target_price REAL, direction TEXT, triggered INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.execute('INSERT INTO alerts (code, name, target_price, direction) VALUES (?,?,?,?)',
                 (code, name, target_price, direction))
    conn.commit()
    conn.close()
    return f'✅ 已设置 {name} {("涨到" if direction == "up" else "跌破")} {target_price} 提醒'

def check_alerts():
    """检查提醒（30 分钟 cron）——触发则输出推送文本"""
    conn = get_conn()
    alerts = conn.execute("SELECT * FROM alerts WHERE triggered=0").fetchall()
    if not alerts:
        conn.close()
        return ''
    triggered = []
    for a in alerts:
        try:
            symbol = ('sh' if a['code'].startswith('6') else 'sz') + a['code']
            df = ak.stock_zh_a_daily(symbol=symbol, start_date='20260801', end_date='20260810', adjust='qfq')
            if df is None or len(df) == 0:
                continue
            cur = float(df['close'].iloc[-1])
            if (a['direction'] == 'up' and cur >= a['target_price']) or \
               (a['direction'] == 'down' and cur <= a['target_price']):
                triggered.append(a)
        except Exception:
            pass
    if triggered:
        for a in triggered:
            conn.execute("UPDATE alerts SET triggered=1 WHERE id=?", (a['id'],))
        conn.commit()
    conn.close()
    if not triggered:
        return ''
    lines = ['🚨 **到价提醒**']
    for a in triggered:
        lines.append(f"· {a['name']}（{a['code']}）已{a['direction'] == 'up' and '涨到' or '跌破'}目标价 {a['target_price']}")
    return '\n'.join(lines)

def main():
    out = check_alerts()
    if out:
        print(out)
    # 无触发——静默（cron 不推送）

if __name__ == '__main__':
    main()
