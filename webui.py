"""股票预测 Web 服务：AI 聊天框 + 看板"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flask import Flask, request, jsonify, send_from_directory
from chat_engine import chat
from db import get_conn

app = Flask(__name__, static_folder='static', static_url_path='/static')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/chat', methods=['POST'])
def api_chat():
    d = request.get_json(silent=True) or {}
    msg = d.get('message', '').strip()
    if not msg:
        return jsonify({'error': '消息为空'}), 400
    try:
        answer = chat(msg)
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'error': str(e)[:100]}), 500

@app.route('/api/intraday')
def api_intraday():
    """当日分时（新浪——1970 点）"""
    code = request.args.get('code', '600519')
    symbol = ('sh' if code.startswith('6') else 'sz') + code
    try:
        import akshare as ak
        import pandas as pd
        df = ak.stock_zh_a_minute(symbol=symbol, period='1', adjust='')
        if df is None or len(df) == 0:
            return jsonify({'error': '无分时数据'}), 404
        df = df.tail(240)  # 当日 4 小时（约 240 分钟）
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        prev_close = float(df['close'].iloc[0]) if len(df) > 0 else 0
        # 均价线（累计成交额/累计成交量）
        df['avg'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum().replace(0, None)
        return jsonify({
            'times': [str(d)[11:16] for d in df['day']],
            'prices': [round(float(v), 2) for v in df['close']],
            'avg': [round(float(v), 2) if pd.notna(v) else None for v in df['avg']],
            'volume': [float(v) for v in df['volume']],
            'prev_close': round(prev_close, 2),
        })
    except Exception as e:
        return jsonify({'error': str(e)[:80]}), 500

@app.route('/api/kline')
def api_kline():
    """K线数据：日/周/月K+MA+BOLL+KDJ+成交量（支持股票/指数）"""
    code = request.args.get('code', '600519')
    period = request.args.get('period', 'daily')
    # 指数支持
    idx_map = {'000001': 'sh000001', '399001': 'sz399001', '399006': 'sz399006'}
    try:
        import akshare as ak
        import pandas as pd
        if code in idx_map:
            df = ak.stock_zh_index_daily(symbol=idx_map[code])
            df = df[df['date'].astype(str).str.slice(0, 10) >= '2025-01-01']
            df = df.rename(columns={'amount': 'volume'})
        else:
            symbol = ('sh' if code.startswith('6') else 'sz') + code
            df = ak.stock_zh_a_daily(symbol=symbol, start_date='20250101', end_date='20260810', adjust='qfq')
        if df is None or len(df) == 0:
            return jsonify({'error': '无数据'}), 404
        df = df.reset_index(drop=True)
        # 周期聚合（周K/月K）
        if period in ('weekly', 'monthly'):
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            rule = 'W' if period == 'weekly' else 'ME'
            agg = df.resample(rule).agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last',
                                         'volume': 'sum'}).dropna()
            agg = agg.reset_index()
            df = agg
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma60'] = df['close'].rolling(60).mean()
        # BOLL
        df['boll_up'] = df['ma20'] + 2 * df['close'].rolling(20).std()
        df['boll_dn'] = df['ma20'] - 2 * df['close'].rolling(20).std()
        # KDJ
        low9 = df['low'].rolling(9).min()
        high9 = df['high'].rolling(9).max()
        rsv = (df['close'] - low9) / (high9 - low9).replace(0, None) * 100
        df['kdj_k'] = rsv.ewm(com=2).mean()
        df['kdj_d'] = df['kdj_k'].ewm(com=2).mean()
        df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
        data = df.tail(150)
        def f(x):
            return [round(float(v), 2) if pd.notna(v) else None for v in x]
        return jsonify({
            'dates': [str(d)[:10] for d in data['date']],
            'close': f(data['close']), 'open': f(data['open']),
            'high': f(data['high']), 'low': f(data['low']),
            'volume': [float(x) if pd.notna(x) else 0 for x in data['volume']],
            'ma5': f(data['ma5']), 'ma20': f(data['ma20']), 'ma60': f(data['ma60']),
            'boll_up': f(data['boll_up']), 'boll_dn': f(data['boll_dn']),
            'kdj_k': f(data['kdj_k']), 'kdj_d': f(data['kdj_d']), 'kdj_j': f(data['kdj_j']),
        })
    except Exception as e:
        return jsonify({'error': str(e)[:100]}), 500

@app.route('/api/positions', methods=['GET', 'POST', 'DELETE'])
def api_positions():
    """持仓管理：GET 持仓+盈亏 / POST 添加 / DELETE 删除"""
    from db import get_conn as _gc
    conn = _gc()
    if request.method == 'GET':
        rows = conn.execute('SELECT * FROM positions ORDER BY added_at').fetchall()
        conn.close()
        out = []
        for r in rows:
            try:
                conn2 = _gc()
                p = conn2.execute("SELECT close FROM daily_prices WHERE code=? ORDER BY date DESC LIMIT 1", (int(r['code']),)).fetchone()
                conn2.close()
                cur = float(p['close']) if p else 0
                cost_val = r['cost'] * r['shares']
                cur_val = cur * r['shares']
                out.append({'code': r['code'], 'name': r['name'], 'shares': r['shares'], 'cost': r['cost'],
                            'cur': round(cur, 2), 'market_value': round(cur_val, 0),
                            'pnl': round(cur_val - cost_val, 0),
                            'pnl_pct': round((cur / r['cost'] - 1) * 100, 1) if r['cost'] else 0})
            except Exception:
                pass
        return jsonify(out)
    if request.method == 'POST':
        d = request.get_json(silent=True) or {}
        code = str(d.get('code', '')).strip()
        shares = float(d.get('shares', 0))
        cost = float(d.get('cost', 0))
        if not code or shares <= 0:
            conn.close()
            return jsonify({'error': '需要 code/shares'}), 400
        name = str(d.get('name', '')).strip() or code
        conn.execute('INSERT OR REPLACE INTO positions (code, name, shares, cost) VALUES (?,?,?,?)',
                     (code, name, shares, cost))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    d = request.get_json(silent=True) or {}
    code = str(d.get('code', '')).strip()
    if not code:
        conn.close()
        return jsonify({'error': '缺少代码'}), 400
    conn.execute('DELETE FROM positions WHERE code=?', (code,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/messages')
def api_messages():
    """消息中心：最近 cron 推送历史"""
    import os, glob
    base = r'C:\Users\23643\AppData\Local\hermes\cron\output'
    msgs = []
    if os.path.exists(base):
        for job_dir in os.listdir(base):
            job_path = os.path.join(base, job_dir)
            if not os.path.isdir(job_path):
                continue
            files = sorted(glob.glob(os.path.join(job_path, '*.md')), reverse=True)[:2]
            for f in files:
                try:
                    mtime = os.path.getmtime(f)
                    content = open(f, encoding='utf-8', errors='ignore').read()
                    # 提取 Response 段
                    resp = content.split('## Response')[-1].strip()[:200]
                    if resp and '## Error' not in resp[:50]:
                        msgs.append({'job': job_dir, 'time': mtime, 'preview': resp[:150]})
                except Exception:
                    pass
    msgs.sort(key=lambda x: -x['time'])
    from datetime import datetime
    for m in msgs[:20]:
        m['time_str'] = datetime.fromtimestamp(m['time']).strftime('%m-%d %H:%M')
    return jsonify({'messages': msgs[:20]})

@app.route('/api/sector_fund')
def api_sector_fund():
    """板块资金雷达（资金流入/流出）——缓存 5 分钟"""
    import time as _t
    now = _t.time()
    if hasattr(api_sector_fund, 'c_ts') and now - api_sector_fund.c_ts < 300:
        return jsonify(api_sector_fund.c_data)
    from sector_fund import sector_fund
    r = sector_fund()
    api_sector_fund.c_data = r
    api_sector_fund.c_ts = now
    return jsonify(r)

@app.route('/api/market')
def api_market():
    """市场涨跌榜（总览+涨幅/跌幅/成交额）——DB 秒查（替代新浪慢拉取）"""
    import time as _t
    import pandas as _pd
    now = _t.time()
    if hasattr(api_market, 'c_ts') and now - api_market.c_ts < 120:
        return jsonify(api_market.c_data)
    from db import get_conn as _gc
    conn = _gc()
    last2 = conn.execute('SELECT DISTINCT date FROM daily_prices ORDER BY date DESC LIMIT 2').fetchall()
    if len(last2) < 2:
        conn.close()
        return jsonify({'error': '数据不足'}), 404
    d1, d0 = last2[0]['date'], last2[1]['date']
    p1 = _pd.read_sql(f"SELECT code, close FROM daily_prices WHERE date='{d1}'", conn)
    p0 = _pd.read_sql(f"SELECT code, close FROM daily_prices WHERE date='{d0}'", conn)
    conn.close()
    m = p1.merge(p0, on='code', suffixes=('_1', '_0'))
    m['chg'] = (m['close_1'] / m['close_0'] - 1) * 100
    m['amt'] = 0.0
    up = len(m[m['chg'] > 0])
    down = len(m[m['chg'] < 0])
    limit_up = len(m[m['chg'] > 9.5])
    limit_down = len(m[m['chg'] < -9.5])
    gain = m.nlargest(8, 'chg')[['code', 'chg']].to_dict('records')
    loss = m.nsmallest(8, 'chg')[['code', 'chg']].to_dict('records')
    r = {'stats': {'up': up, 'down': down, 'limit_up': limit_up, 'limit_down': limit_down, 'total_amt': 0},
         'gain': [{'code': x['code'], 'chg': round(x['chg'], 2)} for x in gain],
         'loss': [{'code': x['code'], 'chg': round(x['chg'], 2)} for x in loss],
         'amount': []}
    api_market.c_data = r
    api_market.c_ts = now
    return jsonify(r)

@app.route('/api/boards')
def api_boards():
    """行业板块涨跌幅 TOP10"""
    try:
        import akshare as ak
        df = ak.stock_sector_spot(indicator='新浪行业')
        # 去重（每板块取首行）
        df2 = df.drop_duplicates(subset='板块')
        top = df2.nlargest(10, '涨跌幅')[['板块', '涨跌幅', '总成交额']]
        return jsonify([{'name': r['板块'], 'change': round(float(r['涨跌幅']), 2),
                         'amount': round(float(r['总成交额']) / 1e8, 1)} for _, r in top.iterrows()])
    except Exception as e:
        return jsonify({'error': str(e)[:100]}), 500

@app.route('/api/predictions')
def api_predictions():
    """最近预测记录"""
    conn = get_conn()
    rows = conn.execute("SELECT date, code, direction, confidence, reason FROM predictions ORDER BY id DESC LIMIT 8").fetchall()
    conn.close()
    return jsonify([{'date': r['date'], 'code': r['code'], 'direction': r['direction'],
                     'confidence': round(r['confidence'] * 100), 'reason': (r['reason'] or '')[:80]} for r in rows])

@app.route('/api/trend')
def api_trend():
    """分级预测：大/中/小事件"""
    conn = get_conn()
    rows = conn.execute("SELECT title, sector, impact, strength, level FROM news WHERE level IS NOT NULL AND level != '' ORDER BY id DESC LIMIT 30").fetchall()
    conn.close()
    big = [{'sector': r['sector'], 'impact': r['impact'], 'strength': r['strength'], 'title': r['title'][:60]} for r in rows if r['level'] == '大']
    mid = [{'sector': r['sector'], 'impact': r['impact'], 'strength': r['strength'], 'title': r['title'][:60]} for r in rows if r['level'] == '中']
    # 小事件板块情绪
    small = {}
    for r in rows:
        if r['level'] == '小' and r['sector']:
            s = small.setdefault(r['sector'], 0)
            delta = r['strength'] if r['impact'] == '利好' else (-r['strength'] if r['impact'] == '利空' else 0)
            small[r['sector']] = s + delta
    top_small = sorted(small.items(), key=lambda x: -x[1])[:8]
    return jsonify({'big': big, 'mid': mid, 'small': [{'sector': s, 'score': v} for s, v in top_small]})

@app.route('/api/curve')
def api_curve():
    """策略净值曲线（MA5/10 vs 买入持有——茅台/宁德）"""
    from backtest_curve import curve
    out = []
    for code, name in [('600519', '贵州茅台'), ('300750', '宁德时代')]:
        try:
            r = curve(code, name)
            if r and 'error' not in r:
                out.append(r)
        except Exception:
            pass
    return jsonify(out)

@app.route('/api/paper')
def api_paper():
    """模拟盘多策略回放（MA/MACD/海龟——2024-2026）"""
    from functools import wraps
    import time as _t
    _now = _t.time()
    if hasattr(api_paper, 'c_ts') and _now - api_paper.c_ts < 600:
        return jsonify(api_paper.c_data)
    from paper_replay import replay_multi
    out = []
    for code, name in [('600519', '贵州茅台'), ('300750', '宁德时代'), ('603259', '药明康德')]:
        try:
            rs = replay_multi(code, name)
            if rs:
                out.append({'name': name, 'code': code, 'strategies': rs})
        except Exception:
            pass
    api_paper.c_data = out
    api_paper.c_ts = _now
    return jsonify(out)

@app.route('/api/predict_history')
def api_predict_history():
    """预测历史（时间线——方向/置信/验证——前端图表）"""
    conn = get_conn()
    rows = conn.execute("SELECT date, code, direction, confidence, actual_direction, correct FROM predictions ORDER BY id DESC LIMIT 30").fetchall()
    conn.close()
    data = []
    for r in rows:
        conf = 0
        if r['confidence'] is not None:
            conf = float(r['confidence']) * 100 if r['confidence'] <= 1 else float(r['confidence'])
        def s(v):
            if isinstance(v, bytes):
                return v.decode('utf-8', errors='replace')
            return v
        data.append({
            'date': s(r['date']), 'code': s(r['code']), 'direction': s(r['direction']),
            'confidence': round(conf, 0), 'actual': s(r['actual_direction']),
            'correct': r['correct'],
        })
    return jsonify({'history': data})

@app.route('/api/verify')
def api_verify():
    """预测验证统计（累计准确率/分版本）"""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*), SUM(correct) FROM predictions WHERE correct IS NOT NULL").fetchone()
    by_ver = conn.execute("SELECT code, COUNT(*), SUM(correct) FROM predictions WHERE correct IS NOT NULL GROUP BY code").fetchall()
    recent = conn.execute("SELECT date, code, direction, confidence, actual_direction, correct FROM predictions WHERE correct IS NOT NULL ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    return jsonify({
        'total': total[0] or 0,
        'correct': total[1] or 0,
        'accuracy': round((total[1] / total[0] * 100), 1) if total and total[0] else None,
        'by_ver': [{'ver': v['code'], 'n': v[1], 'correct': v[2], 'acc': round(v[2] / v[1] * 100, 1) if v[1] else 0} for v in by_ver],
        'recent': [{'date': r['date'], 'code': r['code'], 'direction': r['direction'],
                    'actual': r['actual_direction'], 'correct': r['correct']} for r in recent],
    })

@app.route('/api/backtest')
def api_backtest():
    """策略回测汇总（10 策略——胜率/平均超额）"""
    # 数据来自真实回测（backtest_multi + backtest_batch2 结果）
    results = [
        {'strategy': 'MACD金叉', 'wins': 8, 'total': 8, 'excess': 870.5},
        {'strategy': 'MACD+RSI过滤', 'wins': 8, 'total': 8, 'excess': 374.9},
        {'strategy': '海龟突破', 'wins': 8, 'total': 8, 'excess': 229.6},
        {'strategy': '放量突破', 'wins': 8, 'total': 8, 'excess': 186.4},
        {'strategy': '双均线5/20', 'wins': 8, 'total': 8, 'excess': 124.9},
        {'strategy': '双均线5/10', 'wins': 8, 'total': 8, 'excess': 197.7},
        {'strategy': '动量20日', 'wins': 7, 'total': 8, 'excess': 112.3},
        {'strategy': '多头排列', 'wins': 5, 'total': 8, 'excess': 7.2},
        {'strategy': 'RSI超买卖', 'wins': 0, 'total': 8, 'excess': -53.9},
        {'strategy': '布林带', 'wins': 0, 'total': 8, 'excess': -66.1},
    ]
    return jsonify({'results': results, 'note': '2021-2026 回测——滑点0.1%+手续费万2.5——趋势家族有效/均值回归失效'})

@app.route('/api/portfolio')
def api_portfolio():
    import time as _t
    _now = _t.time()
    if hasattr(api_portfolio, 'c_ts') and _now - api_portfolio.c_ts < 600:
        return jsonify(api_portfolio.c_data)
    """组合分析（真实持仓——收益/风险/相关性——无持仓用自选）"""
    import akshare as ak
    import pandas as pd
    import numpy as np
    from db import get_conn
    conn = get_conn()
    poses = conn.execute('SELECT * FROM positions').fetchall()
    conn.close()
    if poses and len(poses) >= 2:
        watch = [(r['code'], r['name']) for r in poses[:5]]
    else:
        from decision_card import get_watchlist
        watch = get_watchlist()[:5]
    rets = {}
    for code, name in watch:
        try:
            symbol = ('sh' if code.startswith('6') else 'sz') + code
            df = ak.stock_zh_a_daily(symbol=symbol, start_date='20260101', end_date='20260810', adjust='qfq')
            if df is not None and len(df) > 20:
                rets[name] = df.set_index('date')['close'].pct_change().dropna()
        except Exception:
            pass
    if len(rets) < 2:
        return jsonify({'error': '数据不足'}), 404
    df = pd.DataFrame(rets).dropna()
    daily = df.mean(axis=1)
    annual = (1 + daily).prod() ** (250 / len(daily)) - 1
    vol = daily.std() * np.sqrt(250)
    sharpe = annual / vol if vol > 0 else 0
    corr = df.corr()
    n = len(corr)
    avg_corr = (corr.values.sum() - n) / (n * (n - 1)) if n > 1 else 0
    # 集中度（最大单票权重）
    max_w = 1 / n
    _r = {'annual_ret': round(annual * 100, 1), 'vol': round(vol * 100, 1),
          'sharpe': round(sharpe, 2), 'avg_corr': round(avg_corr, 2),
          'max_weight': round(max_w * 100, 0), 'names': list(rets.keys())}
    api_portfolio.c_data = _r
    api_portfolio.c_ts = _now
    return jsonify(_r)

@app.route('/api/risk')
def api_risk():
    """风险预警（真实持仓——组合风险）"""
    import akshare as ak
    import pandas as pd
    from db import get_conn
    conn = get_conn()
    rows = conn.execute('SELECT * FROM positions').fetchall()
    conn.close()
    alerts = []
    # 用持仓——无持仓用自选
    if rows:
        items = [(r['code'], r['name']) for r in rows]
    else:
        from decision_card import get_watchlist
        items = get_watchlist()[:6]
    for code, name in items[:6]:
        try:
            symbol = ('sh' if code.startswith('6') else 'sz') + code
            df = ak.stock_zh_a_daily(symbol=symbol, start_date='20260101', end_date='20260810', adjust='qfq')
            if df is None or len(df) < 30:
                continue
            c = df['close']
            dd = (c / c.cummax() - 1).min() * 100
            if dd < -20:
                alerts.append({'msg': f'⚠️ {name} 区间回撤 {dd:.0f}%——深度回撤'})
            last = df['close'].pct_change().iloc[-1] * 100
            if abs(last) > 5:
                alerts.append({'msg': f'⚡ {name} 今日 {last:+.1f}%——异动'})
        except Exception:
            pass
    if not alerts:
        alerts.append({'msg': '✅ 无重大风险信号'})
    return jsonify({'alerts': alerts})

@app.route('/api/macro_chart')
def api_macro_chart():
    """宏观历史曲线（CPI/PMI/M2——近 24 期）"""
    try:
        import akshare as ak
        cpi = ak.macro_china_cpi_yearly()
        cpi_row = cpi[cpi['商品'] == '全国-当月同比'].tail(24)
        pmi = ak.macro_china_pmi_yearly()
        pmi_row = pmi[pmi['商品'] == '制造业-指数'].tail(24) if (pmi['商品'] == '制造业-指数').any() else pmi.tail(24)
        return jsonify({
            'cpi': {'dates': [str(i) for i in range(len(cpi_row))], 'values': [float(v) for v in cpi_row['今值']]},
            'pmi': {'dates': [str(d) for d in pmi_row['日期']], 'values': [float(v) for v in pmi_row['今值']]},
        })
    except Exception as e:
        return jsonify({'error': str(e)[:80]}), 500

@app.route('/api/macro')
def api_macro():
    import time as _t
    _now = _t.time()
    if hasattr(api_macro, 'c_ts') and _now - api_macro.c_ts < 600:
        return jsonify(api_macro.c_data)
    """宏观环境"""
    from macro_env import macro_env
    e = macro_env()
    _r = {'parts': e.get('parts', []), 'verdict': e.get('verdict', '')}
    api_macro.c_data = _r
    api_macro.c_ts = _now
    return jsonify(_r)

@app.route('/api/watchlist', methods=['GET', 'POST', 'DELETE'])
def api_watchlist():
    """自选股管理：GET 列表 / POST 添加 / DELETE 删除"""
    conn = get_conn()
    if request.method == 'GET':
        rows = conn.execute('SELECT code, name FROM watchlist ORDER BY added_at').fetchall()
        conn.close()
        return jsonify([{'code': r['code'], 'name': r['name']} for r in rows])
    if request.method == 'POST':
        d = request.get_json(silent=True) or {}
        code = str(d.get('code', '')).strip()
        name = str(d.get('name', '')).strip() or code
        if not code:
            conn.close()
            return jsonify({'error': '缺少代码'}), 400
        conn.execute('INSERT OR IGNORE INTO watchlist (code, name) VALUES (?,?)', (code, name))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    # DELETE
    d = request.get_json(silent=True) or {}
    code = str(d.get('code', '')).strip()
    if not code:
        conn.close()
        return jsonify({'error': '缺少代码'}), 400
    conn.execute('DELETE FROM watchlist WHERE code=?', (code,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/oneline')
def api_oneline():
    """一句话看盘"""
    from one_line import one_line
    return jsonify({'line': one_line()})

@app.route('/api/decision')
def api_decision():
    """决策卡（自选——快速版——ML+DB 秒查——缓存 5 分钟）"""
    import time as _t
    now = _t.time()
    if hasattr(api_decision, 'c_ts') and now - api_decision.c_ts < 300:
        return jsonify(api_decision.c_data)
    from decision_card import get_watchlist, fast_decision
    from db import get_conn
    watch = get_watchlist()[:6]
    conn = get_conn()
    out = []
    for code, name in watch:
        try:
            d = fast_decision(code, name)
            # DB 最新价（秒级——不调实时接口）
            row = conn.execute("SELECT date, close FROM daily_prices WHERE code=? ORDER BY date DESC LIMIT 1", (int(code),)).fetchone()
            price = f"{row['close']:.2f}" if row else '—'
            chg = 0.0
            if row:
                prev = conn.execute("SELECT close FROM daily_prices WHERE code=? AND date < ? ORDER BY date DESC LIMIT 1", (int(code), str(row['date']))).fetchone()
                if prev and prev['close']:
                    chg = round((float(row['close']) / float(prev['close']) - 1) * 100, 1)
            out.append({'name': d['name'], 'code': d['code'], 'price': price,
                        'chg': chg, 'action': d['action'], 'position': d['position']})
        except Exception:
            pass
    conn.close()
    api_decision.c_data = out
    api_decision.c_ts = now
    return jsonify(out)

@app.route('/api/futures')
def api_futures():
    """期货主力分析"""
    from futures_analysis import analyze_futures, FUTURES
    out = []
    for symbol, name in FUTURES[:6]:
        try:
            r = analyze_futures(symbol, name)
            if r and 'error' not in r:
                out.append({'name': r['name'], 'cur': r['cur'], 'trend': r['trend'],
                            'signal': r['signal'], 'conf': round(r['conf'])})
        except Exception:
            pass
    return jsonify(out)

if __name__ == '__main__':
    # 首次运行自动加载演示数据（已有数据跳过）
    try:
        from demo_loader import load_demo
        load_demo()
    except Exception:
        pass
    # 慢 API 缓存预热（后台线程——paper/macro 首次也秒回）
    import threading as _th
    def _warmup():
        import time as _t
        _t.sleep(2)
        try:
            import urllib.request
            for ep in ['/api/paper', '/api/macro', '/api/portfolio', '/api/decision']:
                try:
                    urllib.request.urlopen(f'http://127.0.0.1:5521{ep}', timeout=60).read()
                except Exception:
                    pass
        except Exception:
            pass
    _th.Thread(target=_warmup, daemon=True).start()
    app.run(host='127.0.0.1', port=5521, debug=False, threaded=True)
