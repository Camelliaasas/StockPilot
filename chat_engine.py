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
    """LLM 分析师回答"""
    key = get_llm_key()
    if not key:
        return 'LLM key 未配置'
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
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
        return resp['choices'][0]['message']['content']
    except Exception as e:
        return f'LLM 调用失败: {str(e)[:60]}'

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
    stocks = detect_stocks(message)
    if not stocks:
        return '暂不支持该查询——目前支持：个股分析/两只股票对比（茅台/宁德/五粮液/比亚迪/平安等）'
    # 拉数据
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
