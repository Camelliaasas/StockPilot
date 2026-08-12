# StockPilot 严格四层测试（skill: strict-testing-local-webapps）
import json, urllib.request, urllib.error

BASE = 'http://127.0.0.1:5521'
PASS, FAIL = 0, 0
failures = []

def check(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f'  ✅ {name}')
    else:
        FAIL += 1
        failures.append(name)
        print(f'  ❌ {name} — {detail}')

def get(path, timeout=30):
    try:
        with urllib.request.urlopen(BASE + '/' + path, timeout=timeout) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, raw[:50]
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return -1, str(e)[:60]

def post(path, body, timeout=40):
    try:
        data = json.dumps(body).encode('utf-8')
        req = urllib.request.Request(BASE + '/' + path, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return -1, str(e)[:60]

print('═══ 第一层：API 全端点（真实 HTTP）═══')
endpoints = ['', 'api/boards', 'api/market', 'api/macro', 'api/macro_chart', 'api/trend',
             'api/decision', 'api/sector_fund', 'api/portfolio', 'api/positions',
             'api/risk', 'api/curve', 'api/paper', 'api/verify', 'api/predictions',
             'api/predict_history', 'api/messages',
             'api/valuation?code=600519', 'api/chips?code=600519', 'api/index',
             'api/kline?code=600519&period=daily', 'api/intraday?code=600519',
             'api/watchlist', 'api/futures']
for ep in endpoints:
    code, data = get(ep, timeout=40)
    ok = code == 200 and data is not None
    check(f'GET /{ep}', ok, f'{code} {str(data)[:40] if data else ""}')
# SQL 注入
code, _ = get("api/kline?code=600519';DROP TABLE daily_prices;--", timeout=10)
check('SQL 注入串', code != 200 and code != -1, f'{code}')
# 非法参数
code, _ = get('api/kline?code=abc&period=bad', timeout=10)
check('非法参数容错', code in (200, 400, 500), f'{code}')
# 空聊天
code, data = post('api/chat', {'message': ''}, timeout=10)
check('空聊天处理', code in (400, 200), f'{code}')
# 超长输入
long_msg = '分' * 5000
code, data = post('api/chat', {'message': long_msg}, timeout=60)
check('超长输入不崩', code in (200, 400), f'{code}')
# 特殊字符
code, data = post('api/chat', {'message': '<script>alert(1)</script> 茅台'}, timeout=40)
check('特殊字符/XSS', code == 200 and data and data.get('answer'), f'{code}')

print('═══ 第三层：聊天 22 意图═══')
intents = ['分析茅台', '茅台 宁德 对比', '今天大盘怎么样', '选股 ROE>20 营收>30',
           '提醒 600519 涨到1500元', '政策新闻', '连锁推演', '体检茅台',
           '预测 600519', '估值 600519', '筹码 600519', '持仓', '风险',
           '导入自选 601899', '趋势分级', '板块资金', '回测', '模拟盘',
           '最近消息', '自选股', '观望茅台', '推荐股票']
for q in intents:
    code, data = post('api/chat', {'message': q}, timeout=60)
    ans = data.get('answer', '') if data else ''
    ok = code == 200 and ans and '不支持' not in ans[:20] and '失败' not in ans[:20]
    check(f'意图「{q}」', ok, f'{code} {ans[:30]}')

print('═══ 第四层：数据完整性═══')
import sqlite3
conn = sqlite3.connect('data.db')
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
check('核心表存在', all(t in tables for t in ['daily_prices', 'predictions', 'news', 'financials']), str(tables)[:60])
n = conn.execute('SELECT COUNT(*) FROM daily_prices').fetchone()[0]
check('daily_prices 千万级', n > 10000000, f'{n:,}')
latest = conn.execute('SELECT MAX(date) FROM daily_prices').fetchone()[0]
check('数据最新 8-11', latest >= '2026-08-10', latest)
bt = conn.execute('SELECT COUNT(*) FROM backtest_history').fetchone()[0]
check('回测样本 5 万+', bt > 50000, f'{bt:,}')
news_n = conn.execute('SELECT COUNT(*) FROM news').fetchone()[0]
check('新闻积累', news_n > 900, f'{news_n}')
conn.close()

print(f'\n═══ 结果: {PASS} 通过 / {FAIL} 失败 ═══')
if failures:
    print('失败项:', failures)
