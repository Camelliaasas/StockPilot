"""AI 聊天引擎：自然语言问题 → 意图识别 → 数据拉取 → 分析师回答"""
import sys, os, json, re
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

def detect_stocks(msg):
    """识别问题里的股票（最多 2 只——对比用）"""
    found = []
    for name, code in KNOWN_STOCKS.items():
        if name in msg and code not in found:
            found.append((name, code))
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
    """主入口：处理用户问题"""
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
