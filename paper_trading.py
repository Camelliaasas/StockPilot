"""策略模拟盘：MA(5,10) 趋势策略虚拟实盘——每日信号→模拟持仓→收益跟踪"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

CASH = 100000  # 初始资金
TRADES = [('600519', '贵州茅台'), ('300750', '宁德时代'), ('000858', '五粮液'),
          ('601318', '中国平安'), ('002594', '比亚迪'), ('600036', '招商银行'),
          ('603259', '药明康德'), ('601012', '隆基绿能')]

def init_sim():
    conn = get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS paper_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, code TEXT, name TEXT,
        action TEXT, price REAL, cash REAL, position INTEGER
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS paper_positions (
        code TEXT PRIMARY KEY, name TEXT, shares INTEGER, avg_cost REAL, last_price REAL
    )''')
    # 初始资金记录
    if conn.execute('SELECT COUNT(*) FROM paper_trades').fetchone()[0] == 0:
        conn.execute('INSERT INTO paper_trades (date, code, action, cash) VALUES (?,?,?,?)',
                     (pd.Timestamp.now().strftime('%Y-%m-%d'), 'INIT', 'start', CASH))
    conn.commit()
    conn.close()

def run_signal():
    conn = get_conn()
    positions = {r['code']: r for r in conn.execute('SELECT * FROM paper_positions').fetchall()}
    cash_row = conn.execute("SELECT cash FROM paper_trades ORDER BY id DESC LIMIT 1").fetchone()
    cash = cash_row['cash'] if cash_row else CASH
    today = pd.Timestamp.now().strftime('%Y-%m-%d')
    signals = []
    for code, name in TRADES:
        symbol = ('sh' if code.startswith('6') else 'sz') + code
        try:
            df = ak.stock_zh_a_daily(symbol=symbol, start_date='20260101', end_date='20260810', adjust='qfq')
            if df is None or len(df) < 15:
                continue
            c = df['close'].reset_index(drop=True)
            ma5 = c.rolling(5).mean()
            ma10 = c.rolling(10).mean()
            price = c.iloc[-1]
            prev_ma5, prev_ma10 = ma5.iloc[-2], ma10.iloc[-2]
            cur_ma5, cur_ma10 = ma5.iloc[-1], ma10.iloc[-1]
            has_pos = code in positions
            # 金叉买/死叉卖
            if cur_ma5 > cur_ma10 and prev_ma5 <= prev_ma10 and not has_pos:
                shares = int(cash * 0.5 / price / 100) * 100
                if shares > 0:
                    cost = shares * price
                    conn.execute('INSERT INTO paper_positions (code, name, shares, avg_cost, last_price) VALUES (?,?,?,?,?)',
                                 (code, name, shares, price, price))
                    conn.execute('INSERT INTO paper_trades (date, code, name, action, price, cash, position) VALUES (?,?,?,?,?,?,?)',
                                 (today, code, name, 'BUY', price, cash - cost, 1))
                    cash -= cost
                    signals.append(f'🔴 买入 {name} {shares}股 @{price:.2f}（¥{cost:,.0f}）')
            elif cur_ma5 < cur_ma10 and prev_ma5 >= prev_ma10 and has_pos:
                p = positions[code]
                proceeds = p['shares'] * price
                conn.execute('DELETE FROM paper_positions WHERE code=?', (code,))
                conn.execute('INSERT INTO paper_trades (date, code, name, action, price, cash, position) VALUES (?,?,?,?,?,?,?)',
                             (today, code, name, 'SELL', price, cash + proceeds, 0))
                cash += proceeds
                signals.append(f'🟢 卖出 {name} {p["shares"]}股 @{price:.2f}（¥{proceeds:,.0f}）')
            elif has_pos:
                p = positions[code]
                conn.execute('UPDATE paper_positions SET last_price=? WHERE code=?', (price, code))
        except Exception as e:
            print(f'  ⚠️ {code}: {str(e)[:40]}')
    # 更新现金
    if signals:
        conn.execute('INSERT INTO paper_trades (date, code, action, cash) VALUES (?,?,?,?)',
                     (today, 'MARK', 'cash', cash))
    conn.commit()
    # 汇总
    poss = conn.execute('SELECT * FROM paper_positions').fetchall()
    pos_value = sum(p['shares'] * p['last_price'] for p in poss)
    total = cash + pos_value
    ret = (total / CASH - 1) * 100
    print(f'\n💰 模拟盘净值: ¥{total:,.0f} | 收益 {ret:+.1f}%')
    print(f'   持仓: {len(poss)} 只 | 现金: ¥{cash:,.0f}')
    for p in poss:
        pl = (p['last_price'] / p['avg_cost'] - 1) * 100
        print(f'   {p["name"]}: {p["shares"]}股 成本{p["avg_cost"]:.2f} 现价{p["last_price"]:.2f} ({pl:+.1f}%)')
    if signals:
        print('\n今日信号:')
        for s in signals:
            print('  ' + s)
    else:
        print('\n今日无新信号（持仓不动）')
    conn.close()

if __name__ == '__main__':
    init_sim()
    run_signal()
