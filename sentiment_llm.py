"""LLM 新闻分析：DeepSeek 分析师角色——真分析（非计分）"""
import urllib.request, json, os, sys

def get_llm_key():
    """读 LLM key（TradeFlow .env 复用——或环境变量）"""
    env_path = r'C:\Users\23643\src_workflow\tradeflow_copilot\.env'
    if os.path.exists(env_path):
        for line in open(env_path, encoding='utf-8'):
            if line.startswith('LLM_API_KEY='):
                return line.strip().split('=', 1)[1]
    return os.environ.get('LLM_API_KEY', '')

ANALYST_PROMPT = """你是资深金融分析师（CFA级·10年经验）。基于以下新闻信息，对【{target}】明日/近期走势做出专业判断。

今日新闻：
{news}

要求：
1. 分析每条新闻对 {target} 的影响（利好/利空/中性）——注意传导路径（现金流/折现率/增长/情绪）
2. 区分"预期中"与"超预期"
3. 主要影响因素 Top3 + 次要因素
4. 最终判断：看多/看空/观望 + 置信度（0-100）+ 理由（3句话内）
5. 风险提示（可能出错的地方）

输出 JSON 格式：
{{"direction": "看多/看空/观望", "confidence": 0-100, "top_factors": ["..."], "reason": "..."， "risk": "..."}}"""

def llm_analyze(target, news_list):
    """调用 DeepSeek 分析师角色分析"""
    key = get_llm_key()
    if not key:
        return {'direction': '观望', 'confidence': 50, 'top_factors': [], 'reason': 'LLM key 未配置', 'risk': '无法分析'}
    news_text = '\n'.join(f'- {n}' for n in news_list[:12])
    prompt = ANALYST_PROMPT.replace('{target}', target).replace('{news}', news_text)
    body = json.dumps({
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': '你是资深金融分析师，输出严格 JSON。'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.3,
        'max_tokens': 500
    }).encode('utf-8')
    req = urllib.request.Request('https://api.deepseek.com/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
        content = resp['choices'][0]['message']['content']
        # 提取 JSON
        import re
        m = re.search(r'\{.*\}', content, re.S)
        if m:
            return json.loads(m.group())
        return {'direction': '观望', 'confidence': 50, 'top_factors': [], 'reason': content[:200], 'risk': ''}
    except Exception as e:
        return {'direction': '观望', 'confidence': 50, 'top_factors': [], 'reason': f'LLM 调用失败: {str(e)[:80]}', 'risk': ''}

if __name__ == '__main__':
    news = [
        '特朗普倾向对伊朗经济施压而非军事打击——地缘风险下降',
        '港股科技反弹/南向抢筹半导体——云资本开支2027预计+29%',
        '药明康德创历史新高——港股医药外包全线上涨',
        '苹果折叠iPhone规划到第三代——全球份额或超华为',
        '台风致1943航班取消——北京启动防汛二级响应',
    ]
    r = llm_analyze('上证指数', news)
    print(json.dumps(r, ensure_ascii=False, indent=2))
