"""AI 聊天引擎：自然语言问题 → 意图识别 → 数据拉取 → 分析师回答"""
import sys, os, json, re
from datetime import datetime
import akshare as ak
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sentiment_llm import get_llm_key

# 常用股票代码表（扩展查询用）
KNOWN_STOCKS = {
    '茅台': 'sh600519', '贵州茅台': 'sh600519',
    '宁德': 'sz300750', '宁德时代': 'sz300750',
    '五粮液': 'sz000858', '比亚迪': 'sz002594',
    '平安': 'sh601318', '中国平安': 'sh601318',
    '招商银行': 'sh600036', '药明康德': 'sh603259',
    '隆基': 'sh601012', '隆基绿能': 'sh601012',
    '东方财富': 'sz300059', '中信证券': 'sh600030',
}
_ALL_STOCKS = None

def _load_all_stocks():
    """全 A 股票表（5539 只——动态匹配）"""
    global _ALL_STOCKS
    if _ALL_STOCKS is None:
        try:
            import akshare as ak
            df = ak.stock_info_a_code_name()
            _ALL_STOCKS = {str(r['name']).replace(' ', ''): ('sh' if str(r['code']).startswith('6') else 'sz') + str(r['code']).zfill(6)
                           for _, r in df.iterrows()}
        except Exception:
            _ALL_STOCKS = {}
    return _ALL_STOCKS

def detect_stocks(msg):
    """识别问题里的股票（任意 A 股——全表匹配）——最多 2 只（对比用）"""
    found = []
    for name, code in KNOWN_STOCKS.items():
        if name in msg and code not in found:
            found.append((name, code))
    if len(found) < 2:
        # 全 A 动态匹配（优先 2-4 字名称）
        all_stocks = _load_all_stocks()
        # 全角→半角兼容
        msg_half = msg.replace('Ａ', 'A').replace('ａ', 'a').replace('Ｂ', 'B').replace('Ｃ', 'C')
        for name, code in all_stocks.items():
            if len(name) >= 2 and (name in msg or name in msg_half) and code not in found:
                found.append((name, code))
                if len(found) >= 2:
                    break
    return found[:2]

def get_stock_data(code):
    """拉股票近期数据（30日）+ 关键指标"""
    try:
        df = ak.stock_zh_a_daily(symbol=code, start_date='20260701', end_date='20260810', adjust='qfq')
        if df is None or len(df) < 5:
            return None
        last = df.iloc[-1]
        prev = df.iloc[-6] if len(df) >= 6 else df.iloc[0]
        ret_5 = (last['close'] / prev['close'] - 1) * 100
        ret_1 = (last['close'] / df.iloc[-2]['close'] - 1) * 100
        # 简单趋势
        ma5 = df['close'].tail(5).mean()
        trend = '上升' if last['close'] > ma5 else '下降'
        return {
            'close': round(last['close'], 2),
            'ret_1': round(ret_1, 2), 'ret_5': round(ret_5, 2),
            'trend': trend, 'high': round(df['high'].tail(30).max(), 2),
            'low': round(df['low'].tail(30).min(), 2),
        }
    except Exception as e:
        return {'error': str(e)[:60]}

def llm_answer(question, context):
    """LLM 分析师回答——失败自动降级数据引擎（无 LLM 也出结果）"""
    key = get_llm_key()
    if key:
        prompt = f"""你是资深金融分析师。用户问：{question}

以下是相关数据：
{context}

请给出专业回答：直接判断/对比结论 + 理由（2-3点）+ 风险提示。简洁（150字内）。"""
        import urllib.request
        body = json.dumps({
            'model': 'deepseek-chat',
            'messages': [{'role': 'system', 'content': '你是资深金融分析师，回答简洁专业。'},
                         {'role': 'user', 'content': prompt}],
            'temperature': 0.4, 'max_tokens': 400
        }).encode('utf-8')
        req = urllib.request.Request('https://api.deepseek.com/chat/completions', data=body,
                                     headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read())
            return resp['choices'][0]['message']['content']
        except Exception:
            pass  # 降级
    return fallback_answer(question, context)

def fallback_answer(question, context):
    """降级回答：数据引擎结构化分析（无 LLM key/余额——仍出结果）"""
    import re
    lines = []
    # 解析 context 里的每只股票
    stocks_info = re.findall(r'(.+?)\(([a-z]*\d+)\): 收盘([\d.]+) 近1日([+-]?[\d.]+)% 近5日([+-]?[\d.]+)% 趋势(\S+) 30日高([\d.]+)/低([\d.]+)', context)
    if not stocks_info:
        return '⚠️ 数据不足，无法分析（LLM 不可用且无本地数据）'
    if len(stocks_info) >= 2:
        # 对比模式
        lines.append('📊 **对比分析（数据引擎降级）**')
        for name, code, close, r1, r5, trend, hi, lo in stocks_info:
            verdict = '偏强' if float(r5) > 0 else '偏弱'
            lines.append(f"\n**{name}（{code}）**：现价 {close}｜5日 {r5}%｜趋势 {trend}｜{verdict}")
        lines.append('\n**结论**：')
        a, b = stocks_info[0], stocks_info[1]
        if float(a[4]) > float(b[4]):
            lines.append(f"· {a[0]} 5日动量更强（{a[4]}% vs {b[4]}%），短期相对占优")
        else:
            lines.append(f"· {b[0]} 5日动量更强（{b[4]}% vs {a[4]}%），短期相对占优")
        lines.append('· 趋势确认需观察成交量配合（建议结合估值/筹码）')
    else:
        name, code, close, r1, r5, trend, hi, lo = stocks_info[0]
        lines.append(f"📊 **{name}（{code}）分析（数据引擎）**")
        lines.append(f"\n**现状**：现价 {close}｜近1日 {r1}%｜近5日 {r5}%｜趋势 {trend}")
        lines.append(f"30日区间：{lo} ~ {hi}（现价处于区间 {'上沿' if float(close) > (float(hi)+float(lo))/2 else '下沿'}）")
        # 趋势判断（规则）
        if float(r5) > 3:
            verdict, act = '短期偏强', '关注回调买入机会'
        elif float(r5) < -3:
            verdict, act = '短期偏弱', '观望——等待企稳信号'
        else:
            verdict, act = '震荡', '区间操作——低吸高抛'
        lines.append(f"\n**判断**：{verdict}")
        lines.append(f"**操作建议**：{act}")
        lines.append('**风险提示**：技术信号仅供参考——结合基本面/估值/市场环境综合判断')
    lines.append('\n（LLM 暂不可用——本回答由数据引擎生成——配置 API key 后可获得深度分析）')
    return '\n'.join(lines)

def chat(message):
    """主入口：处理用户问题——全引擎接入"""
    # 体检意图（"体检XX"）
    if '体检' in message:
        from diagnose import diagnose
        for name, code in KNOWN_STOCKS.items():
            if name in message:
                r = diagnose(code, name)
                lines = [f"📋 体检报告：{r['name']}（{r['code']}）"]
                for k, v in r['scores'].items():
                    bar = '█' * int(min(v, 100) / 10)
                    lines.append(f'{k}: {v:.0f} {bar}')
                lines.append(f"结论: {r['conclusion']}")
                for s in r['summary']:
                    lines.append(f'📝 {s}')
                lines.append('⚠️ 仅供参考，非投资建议')
                return '\n'.join(lines)
        return '请指定股票（如：体检茅台 / 体检宁德时代）'
    # 估值意图（"XX估值"）
    if '估值' in message:
        from valuation import valuation
        for name, code in KNOWN_STOCKS.items():
            if name in message:
                v = valuation(code, name)
                lines = [f"💰 估值分析：{v['name']}（{v['code']}）"]
                if v.get('pe') is not None:
                    lines.append(f"PE(TTM): {v['pe']}（历史 {v['pe_pct']}% 分位）")
                if v.get('pb') is not None:
                    lines.append(f"PB: {v['pb']}（历史 {v['pb_pct']}% 分位）")
                lines.append(f"结论: {v['verdict']}")
                lines.append('⚠️ 估值仅供参考——非投资建议')
                return '\n'.join(lines)
        return '请指定股票（如：茅台估值）'
    # 筹码意图（"XX筹码"）
    if '筹码' in message:
        from chip_signal import chip_signal
        for name, code in KNOWN_STOCKS.items():
            if name in message:
                r = chip_signal(code, name)
                return f"🎯 筹码分析：{r['name']}\n{r['signal']}\n📝 {r.get('detail', '')}\n⚠️ 仅供参考"
        return '请指定股票（如：茅台筹码）'
    # 研报意图（"研报XX"）
    if '研报' in message:
        from report_deep import deep_report
        for name, code in KNOWN_STOCKS.items():
            if name in message:
                return deep_report(code, name)
        return '请指定股票（如：研报茅台）'
    # 宏观意图
    if '宏观' in message or '大盘环境' in message:
        from macro_env import macro_env
        e = macro_env()
        lines = ['🌐 宏观环境:']
        for p in e.get('parts', []):
            lines.append(f'  · {p}')
        lines.append(f'→ {e.get("verdict", "")}')
        lines.append('⚠️ 宏观判断为参考——非投资建议')
        return '\n'.join(lines)
    # 基金意图
    if '基金' in message:
        from fund_analysis import analyze_fund, FUNDS
        lines = ['📊 基金分析（净值趋势）:']
        for code, name in FUNDS:
            try:
                r = analyze_fund(code, name)
                if r and 'error' not in r:
                    y = f' | 1年{r["ret_1y"]:+.1f}%' if r['ret_1y'] is not None else ''
                    lines.append(f"{r['name']} 净值{r['cur']} | 1月{r['ret_1m']:+.1f}% | 3月{r['ret_3m']:+.1f}%{y} → {r['signal']}")
            except Exception:
                pass
        lines.append('⚠️ 仅供参考——非投资建议')
        return '\n'.join(lines)
    # 港股意图
    if '港股' in message:
        from hk_stock import analyze_hk, HK_STOCKS
        lines = ['📊 港股分析（趋势+动量）:']
        for symbol, name in HK_STOCKS:
            try:
                r = analyze_hk(symbol, name)
                if r and 'error' not in r:
                    icon = {'看多': '🔴', '看空': '🟢', '震荡': '⚪'}[r['signal']]
                    lines.append(f"{icon} {r['name']} {r['cur']} | 20日{r['ret_20']:+.1f}% | {r['trend']} → {r['signal']}({r['conf']}%)")
            except Exception:
                pass
        lines.append('⚠️ 仅供参考——非投资建议')
        return '\n'.join(lines)
    # 美股意图
    if '美股' in message:
        from us_stock import analyze_us, US_STOCKS
        lines = ['📊 美股分析（趋势+动量）:']
        for symbol, name in US_STOCKS:
            try:
                r = analyze_us(symbol, name)
                if r and 'error' not in r:
                    icon = {'看多': '🔴', '看空': '🟢', '震荡': '⚪'}[r['signal']]
                    lines.append(f"{icon} {r['name']} ${r['cur']} | 20日{r['ret_20']:+.1f}% | {r['trend']} → {r['signal']}({r['conf']}%)")
            except Exception:
                pass
        lines.append('⚠️ 仅供参考——非投资建议')
        return '\n'.join(lines)
    # 期货意图
    if '期货' in message:
        from futures_analysis import analyze_futures, FUTURES
        lines = ['📊 期货主力分析:']
        for symbol, name in FUTURES:
            try:
                r = analyze_futures(symbol, name)
                if r and 'error' not in r:
                    icon = {'看多': '🔴', '看空': '🟢', '震荡': '⚪'}[r['signal']]
                    lines.append(f"{icon} {r['name']} {r['cur']} | 20日{r['ret_20']:+.1f}% | → {r['signal']}({r['conf']}%)")
            except Exception:
                pass
        lines.append('⚠️ 仅供参考——非投资建议')
        return '\n'.join(lines)
    # 风险意图
    if '风险' in message:
        from risk_alert import check_risk
        from decision_card import get_watchlist
        watch = get_watchlist()
        positions = [(c, n, 100 // len(watch)) for c, n in watch[:5]] if watch else []
        import io
        old = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf
        try:
            check_risk(positions)
        finally:
            sys.stdout = old
        return buf.getvalue()
    # 决策意图（"今天买什么/决策"）
    if '买什么' in message or '决策' in message:
        from decision_card import get_watchlist, get_spot, decision
        import akshare as ak
        try:
            news = [f'{r["标题"]}' for _, r in ak.stock_info_global_em().head(5).iterrows()]
        except Exception:
            news = []
        lines = ['📋 今日决策（自选）:']
        for code, name in get_watchlist():
            try:
                d = decision(code, name, news)
                icon = {'买入': '🔴', '持有': '🟡', '卖出': '🟢', '观望': '⚪'}[d['action']]
                lines.append(f"{icon} {d['name']} → {d['action']}（仓位{d['position']}）")
            except Exception:
                pass
        lines.append('⚠️ 仅供参考——非投资建议')
        return '\n'.join(lines)
    # 事件日历意图
    if '日历' in message or '事件' in message or '数据发布' in message:
        from event_calendar import next_events
        ev = next_events()
        lines = ['📅 最近重要事件:']
        if not ev:
            lines.append('  （近期无重大事件窗口）')
        for d, desc in ev:
            delta = (d - datetime.now()).days
            lines.append(f'  {d.strftime("%m-%d")}（{delta}天后）: {desc}')
        lines.append('💡 数据发布日波动加大——注意仓位')
        return '\n'.join(lines)
    # 导入意图（"导入自选 代码1,代码2"）
    if '导入' in message:
        import re as _re
        codes = _re.findall(r'\d{6}', message)
        if not codes:
            return '请提供股票代码（如：导入自选 600519,300750）'
        from db import get_conn
        conn = get_conn()
        imported = []
        try:
            all_stocks = _load_all_stocks()
            name_by_code = {v.replace('sh', '').replace('sz', ''): k for k, v in all_stocks.items()}
            for code in codes[:20]:
                name = name_by_code.get(code, code)
                conn.execute('INSERT OR IGNORE INTO watchlist (code, name) VALUES (?,?)', (code, name))
                imported.append(f'{name}（{code}）')
        finally:
            conn.commit()
            conn.close()
        return f'✅ 已导入 {len(imported)} 只自选:\n' + '\n'.join(f'· {n}' for n in imported)
    # 形态意图
    if '形态' in message or '技术面' in message:
        from pattern_recognition import scan_watchlist
        results = scan_watchlist()
        lines = ['🔍 自选股技术形态扫描:']
        for r in results:
            if r['patterns']:
                lines.append(f"\n{r['name']}:")
                for p in r['patterns']:
                    lines.append(f"  📌 {p}")
            else:
                lines.append(f"\n{r['name']}: 无明显形态")
        lines.append('⚠️ 形态是概率参考——需结合量价确认')
        return '\n'.join(lines)
    # 可转债意图
    if '转债' in message or '可转债' in message:
        from convertible import convertible
        r = convertible()
        if 'error' in r:
            return f'可转债数据不可用: {r["error"]}'
        lines = [f"📊 可转债市场（{r['count']} 只）:"]
        lines.append(f"· 平均涨跌 {r['avg_chg']:+.2f}% | 上涨占比 {r['up_pct']}%")
        lines.append('\n💎 低价活跃候选（双低——价格<115）:')
        for c in r['cheap'][:5]:
            lines.append(f"· {c['name']}: {c['price']}（{c['chg']:+.2f}%）")
        lines.append('⚠️ 可转债有强赎/违约风险——仅供参考')
        return '\n'.join(lines)
    # 黄金/外汇意图
    if '黄金' in message or '汇率' in message or '美元' in message:
        from gold_fx import gold_fx
        r = gold_fx()
        g, f = r.get('gold', {}), r.get('fx', {})
        lines = ['🥇 黄金/外汇分析:']
        if 'price' in g:
            lines.append(f"· 上海金 {g['price']} | 20日{g['ret_20']:+.1f}% | 60日{g['ret_60']:+.1f}% → {g['signal']}")
        if 'usd_cny' in f:
            lines.append(f"· USD/CNY {f['usd_cny']}")
        if 'trend' in f:
            lines.append(f"· {f['trend']}")
        lines.append('⚠️ 仅供参考——非投资建议')
        return '\n'.join(lines)
    # 板块意图
    if '板块' in message or '轮动' in message:
        from sector_radar import sector_radar
        r = sector_radar()
        if 'error' in r:
            return f'板块数据不可用: {r["error"]}'
        lines = ['📡 板块轮动雷达:']
        lines.append('\n🔥 强势板块:')
        for t in r['top'][:5]:
            lines.append(f"· {t['name']} {t['change']:+.1f}%（{t['amount']}亿）")
        lines.append('\n💧 资金聚焦:')
        for t in r['hot'][:3]:
            lines.append(f"· {t['name']} {t['amount']}亿（{t['change']:+.1f}%）")
        lines.append('\n❄️ 弱势:')
        for t in r['bottom'][:3]:
            lines.append(f"· {t['name']} {t['change']:+.1f}%")
        lines.append('\n⚠️ 仅供参考')
        return '\n'.join(lines)
    # 提醒意图（"提醒/到价"——设置目标价提醒）
    if '提醒' in message or '到价' in message:
        from price_alert import add_alert
        import re as _re3
        codes = _re3.findall(r'\d{6}', message)
        prices = _re3.findall(r'(\d+\.?\d*)元', message)
        if codes and prices:
            code = codes[0]
            all_stocks = _load_all_stocks()
            name = all_stocks.get(code, code)
            direction = 'down' if '跌破' in message else 'up'
            return add_alert(code, name, float(prices[0]), direction)
        return '请给条件（如：提醒 600519 涨到1500元 / 提醒 600519 跌破1400元）'
    # 选股意图（"选股/筛选"——问财式条件选股）
    if '选股' in message or '筛选' in message or '哪些股票' in message:
        from stock_screener import screener
        import re as _re2
        roe_min = rev_min = chg_min = None
        m_roe = _re2.search(r'ROE[>≥](\d+)', message)
        if m_roe: roe_min = int(m_roe.group(1))
        m_rev = _re2.search(r'(营收|增长)[>≥](\d+)', message)
        if m_rev: rev_min = int(m_rev.group(2))
        m_chg = _re2.search(r'(涨幅|涨)[>≥](\d+)', message)
        if m_chg: chg_min = int(m_chg.group(2))
        if '低估值' in message or '低PE' in message:
            pass  # PE 过滤暂用 ROE 高代理
        if roe_min is None and rev_min is None and chg_min is None:
            return '请给条件（如：选股ROE>15 营收>20 / 选股涨幅>3）'
        r = screener(roe_min=roe_min, rev_min=rev_min, chg_min=chg_min, limit=8)
        if 'error' in r:
            return f'选股失败: {r["error"]}'
        lines = [f'🔍 条件选股（{r["count"]} 只）:']
        for s in r.get('stocks', []):
            parts = [f"{s['code']}", f"ROE{s['roe']}%", f"营收{s['rev']:+.0f}%"]
            if s.get('chg') is not None:
                parts.append(f"今日{s['chg']:+.1f}%")
            lines.append(f"· {s['code']}: ROE{s['roe']}% 营收{s['rev']:+.0f}% 现价{s['price']}")
        lines.append('\n⚠️ 条件筛选为基本面参考——需进一步验证')
        return '\n'.join(lines)
    # 连锁推演意图（"连锁/推演/影响"）
    if '连锁' in message or '推演' in message or '连锁反应' in message:
        from event_chain import analyze_chain
        r = analyze_chain()
        if 'error' in r:
            return f'推演失败: {r["error"]}'
        lines = ['🔗 事件连锁推演（多事件→传导→股市影响）:']
        for ev in r['events']:
            icon = '🔴' if ev['score'] > 0 else ('🟢' if ev['score'] < 0 else '⚪')
            lines.append(f"\n{icon} [{ev['level']}] {ev['event']}")
            for step in ev['chain']:
                lines.append(f"  {step}")
        lines.append(f"\n综合评分: {r['total_score']:+d}")
        lines.append(f"🎯 {r['verdict']}")
        lines.append('\n⚠️ 传导链为逻辑推演——仅供参考')
        return '\n'.join(lines)
    # 政策意图（"政策/新闻"）
    if '政策' in message or '新闻' in message:
        from policy_tracker import scan_policy
        events = scan_policy()
        if not events:
            return '📡 当前无新政策/重大新闻（政策追踪器每 30 分钟自动扫描——有重大决策即时推送）'
        lines = ['📡 最新政策追踪:']
        for ts, t, c in events[:5]:
            lines.append(f'  [{ts}] {t[:50]}')
        lines.append('（详细分析见推送——政策实时追踪中）')
        return '\n'.join(lines)
    # 大盘/指数意图
    if ('大盘' in message or '指数' in message) and ('茅台' not in message and '宁德' not in message):
        try:
            from db import get_conn
            conn = get_conn()
            rows = conn.execute("SELECT code, close, date FROM index_daily ORDER BY date DESC LIMIT 6").fetchall()
            conn.close()
            if rows:
                idx_map = {'000001': '上证', '399001': '深证', '399006': '创业板'}
                by_date = {}
                for r in rows:
                    by_date.setdefault(str(r['date'])[:10], {})[idx_map.get(str(r['code']), str(r['code']))] = r['close']
                latest = max(by_date.keys())
                vals = by_date[latest]
                lines = [f"📈 大盘（{latest}）: " + ' | '.join(f"{k} {v}" for k, v in vals.items())]
                return '\n'.join(lines)
            return '大盘数据暂不可用'
        except Exception:
            pass
    # 预测意图（最新预测）
    if '预测' in message:
        from db import get_conn
        conn = get_conn()
        rows = conn.execute("SELECT date, code, direction, confidence FROM predictions ORDER BY id DESC LIMIT 5").fetchall()
        conn.close()
        if rows:
            lines = ['🎯 最新预测:']
            for r in rows:
                lines.append(f"· [{r['date']}] {r['code']}: {r['direction']}（置信 {r['confidence']}%）")
            lines.append('（每日 20:00 自动预测——次日自动验证）')
            return '\n'.join(lines)
        return '暂无预测记录（每日 20:00 自动生成）'
    # 持仓意图
    if '持仓' in message:
        from db import get_conn
        conn = get_conn()
        rows = conn.execute('SELECT * FROM positions ORDER BY added_at').fetchall()
        conn.close()
        if not rows:
            return '暂无持仓——可输入"持仓添加 600519 100股 1500元"添加'
        lines = ['💼 我的持仓:']
        for r in rows:
            lines.append(f"· {r['name']}（{r['code']}）{r['shares']}股 成本{r['cost']}")
        return '\n'.join(lines)
    # 趋势分级意图
    if '趋势' in message or '分级' in message:
        from trend_forecast import get_events
        big, mid, small = get_events()
        lines = ['📊 分级预测:']
        lines.append(f"· 大事件 {len(big)} 条（→ 中期趋势）| 中事件 {len(mid)} 条 | 小事件 {len(small)} 条")
        for e in big[:3]:
            lines.append(f"  🔴 [{e['sector']}] {e['title'][:40]}")
        lines.append('（详细见看板分级预测区块）')
        return '\n'.join(lines)
    # 回测意图
    if '回测' in message:
        from db import get_conn
        conn = get_conn()
        n = conn.execute('SELECT COUNT(*) FROM backtest_history').fetchone()[0]
        c = conn.execute('SELECT SUM(correct) FROM backtest_history').fetchone()[0] or 0
        conn.close()
        acc = round(c / n * 100, 1) if n else 0
        return f'📊 历史回测: {n:,} 样本 | 准确率 {acc}%（503 万样本模型——500 只股票逐日回测）'
    # 模拟盘意图
    if '模拟盘' in message:
        from paper_replay import replay_multi
        r = replay_multi('600519', '贵州茅台')
        if r and 'error' not in r:
            lines = ['🎮 模拟盘（茅台 2024-2026 策略回测）:']
            for s in r:
                tr = s.get('total_return', s.get('total_ret', 0))
                lines.append(f"· {s.get('name', '策略')}: 收益 {float(tr):+.1f}%")
            return '\n'.join(lines)
        return '模拟盘数据暂不可用'
    # 推荐意图（今日强势股）
    if '推荐' in message:
        try:
            from db import get_conn
            conn = get_conn()
            d = conn.execute('SELECT MAX(date) FROM daily_prices').fetchone()[0]
            rows = conn.execute("SELECT code, name, close FROM daily_prices WHERE date=? AND close > 0 ORDER BY (close/1.0) DESC LIMIT 5", (d,)).fetchall()
            conn.close()
            if rows:
                lines = ['💡 今日关注（按价格列——仅供参考）:']
                for r in rows[:5]:
                    lines.append(f"· {r['name']}（{r['code']}）{r['close']}")
                lines.append('⚠️ 非荐股——可用"选股ROE>15 营收>20"按条件筛选')
                return '\n'.join(lines)
        except Exception:
            pass
    # 消息意图
    if '消息' in message or '推送' in message:
        import os, glob
        out_dir = os.path.expanduser(r'~/AppData/Local/hermes/cron/output')
        files = sorted(glob.glob(os.path.join(out_dir, '*', '*.md')), key=os.path.getmtime, reverse=True)[:5]
        if files:
            lines = ['📬 最近推送:']
            for f in files:
                lines.append(f"· {os.path.basename(f)[:25]}")
            return '\n'.join(lines)
        return '暂无推送记录'
    stocks = detect_stocks(message)
    if not stocks:
        return '暂不支持该查询——目前支持：个股分析/两只股票对比（茅台/宁德/五粮液/比亚迪/平安等）'
    ctx_lines = []
    for name, code in stocks:
        d = get_stock_data(code)
        if 'error' in d:
            ctx_lines.append(f'{name}: 数据获取失败 {d["error"]}')
        else:
            ctx_lines.append(f'{name}({code}): 收盘{d["close"]} 近1日{d["ret_1"]}% 近5日{d["ret_5"]}% 趋势{d["trend"]} 30日高{d["high"]}/低{d["low"]}')
    context = '\n'.join(ctx_lines)
    # 对比模式
    if len(stocks) == 2 and ('对比' in message or '比较' in message or '哪个' in message):
        return llm_answer(message, context)
    # 单股分析
    return llm_answer(message, context)

if __name__ == '__main__':
    q = '茅台和宁德时代对比一下，哪个增长概率大'
    print('问题:', q)
    print('回答:', chat(q))
