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

@app.route('/api/kline')
def api_kline():
    """K线数据：日K+MA5/20/60+成交量"""
    code = request.args.get('code', '600519')
    symbol = ('sh' if code.startswith('6') else 'sz') + code
    try:
        import akshare as ak
        import pandas as pd
        df = ak.stock_zh_a_daily(symbol=symbol, start_date='20250101', end_date='20260810', adjust='qfq')
        if df is None or len(df) == 0:
            return jsonify({'error': '无数据'}), 404
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma60'] = df['close'].rolling(60).mean()
        data = df.tail(120)
        return jsonify({
            'dates': [str(d)[:10] for d in data['date']],
            'close': [round(float(x), 2) for x in data['close']],
            'open': [round(float(x), 2) for x in data['open']],
            'high': [round(float(x), 2) for x in data['high']],
            'low': [round(float(x), 2) for x in data['low']],
            'volume': [float(x) for x in data['volume']],
            'ma5': [round(float(x), 2) if not pd.isna(x) else None for x in data['ma5']],
            'ma20': [round(float(x), 2) if not pd.isna(x) else None for x in data['ma20']],
            'ma60': [round(float(x), 2) if not pd.isna(x) else None for x in data['ma60']],
        })
    except Exception as e:
        return jsonify({'error': str(e)[:100]}), 500

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

@app.route('/api/portfolio')
def api_portfolio():
    """组合分析（自选 5 只等权）"""
    import akshare as ak
    import pandas as pd
    import numpy as np
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
    return jsonify({'annual_ret': round(annual * 100, 1), 'vol': round(vol * 100, 1),
                    'sharpe': round(sharpe, 2), 'avg_corr': round(avg_corr, 2),
                    'names': list(rets.keys())})

@app.route('/api/risk')
def api_risk():
    """风险预警（自选）"""
    import akshare as ak
    import pandas as pd
    from decision_card import get_watchlist
    watch = get_watchlist()
    alerts = []
    for code, name in watch[:6]:
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

@app.route('/api/macro')
def api_macro():
    """宏观环境"""
    from macro_env import macro_env
    e = macro_env()
    return jsonify({'parts': e.get('parts', []), 'verdict': e.get('verdict', '')})

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
    """决策卡（8 只核心——简化版——快速）"""
    from decision_card import decision, WATCHLIST
    import akshare as ak
    try:
        news = [f'{r["标题"]}' for _, r in ak.stock_info_global_em().head(5).iterrows()]
    except Exception:
        news = []
    out = []
    for code, name in WATCHLIST[:5]:
        try:
            d = decision(code, name, news)
            out.append({'name': d['name'], 'price': '—', 'action': d['action'], 'position': d['position']})
        except Exception:
            pass
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
    app.run(host='127.0.0.1', port=5521, debug=False)
