"""深度研报：一键生成机构级个股研报（书库+案例库+数据三源）"""
import sys, os, json
import akshare as ak
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn
from sentiment_llm import get_llm_key

def deep_report(code, name=''):
    """生成深度研报"""
    code = str(code).replace('sh', '').replace('sz', '').replace('bj', '').strip()
    symbol = ('sh' if code.startswith('6') else 'sz') + code
    key = get_llm_key()
    # 数据收集
    try:
        df = ak.stock_zh_a_daily(symbol=symbol, start_date='20240101', end_date='20260810', adjust='qfq')
        cur = df['close'].iloc[-1]
        ret_1y = (cur / df['close'].iloc[-250] - 1) * 100 if len(df) > 250 else None
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        ma60 = df['close'].rolling(60).mean().iloc[-1]
        tech = f'现价{cur:.2f} | 1年涨跌{ret_1y:+.0f}%' if ret_1y else f'现价{cur:.2f}'
        tech += f' | {"站上" if cur>ma20 else "跌破"}20日线 | {"多头" if ma20>ma60 else "空头"}排列'
    except Exception as e:
        tech = f'技术数据失败 {str(e)[:40]}'
    try:
        conn = get_conn()
        f = conn.execute("SELECT * FROM financials WHERE code=? ORDER BY report_date DESC LIMIT 1", (code,)).fetchone()
        conn.close()
        if f:
            fin = f'ROE {f["roe"]:.1f}%' if f['roe'] is not None else ''
            fin += f' | 营收增长 {f["revenue_yoy"]:.1f}%' if f['revenue_yoy'] is not None else ''
            fin += f' | 利润增长 {f["profit_yoy"]:.1f}%' if f['profit_yoy'] is not None else ''
        else:
            fin = '无财务数据'
    except Exception:
        fin = '无财务数据'
    # 新闻
    try:
        news = [f'{r["标题"]}' for _, r in ak.stock_info_global_em().head(10).iterrows()]
        news_txt = '\n'.join(f'- {n[:50]}' for n in news[:8])
    except Exception:
        news_txt = '无新闻'
    # LLM 研报
    prompt = f"""你是机构首席分析师（CFA级）。为【{name}（{code}）】撰写深度研报（800字内）：

## 数据
技术面：{tech}
基本面：{fin}
今日新闻：
{news_txt}

## 研报结构
1. 核心观点（一句话）
2. 基本面分析（估值/盈利质量/成长性——结合金融学框架）
3. 技术面研判（趋势/关键价位）
4. 催化剂与风险（什么会推动上涨/什么可能下跌）
5. 评级（强推/推荐/中性/回避）+ 逻辑

专业、客观、不吹捧。"""
    if not key:
        return f"# {name} 深度研报\n技术: {tech}\n财务: {fin}\n\n（LLM key 未配置——仅数据版）"
    import urllib.request
    body = json.dumps({
        'model': 'deepseek-chat',
        'messages': [{'role': 'system', 'content': '你是机构首席分析师，撰写专业研报。'},
                     {'role': 'user', 'content': prompt}],
        'temperature': 0.4, 'max_tokens': 1000
    }).encode('utf-8')
    req = urllib.request.Request('https://api.deepseek.com/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            resp = json.loads(r.read())
        return resp['choices'][0]['message']['content']
    except Exception as e:
        return f"# {name} 深度研报\n技术: {tech}\n财务: {fin}\n\n（LLM 调用失败: {str(e)[:60]}）"

if __name__ == '__main__':
    print(deep_report('600519', '贵州茅台'))
