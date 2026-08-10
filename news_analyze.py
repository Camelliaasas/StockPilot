"""新闻分析层：LLM 自动分析新入库新闻——影响板块/利好利空——供预测使用"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn
from sentiment_llm import get_llm_key

def analyze_batch(news_list):
    """LLM 批量分析新闻：每条 → 影响板块 + 方向 + 强度 + 事件级别"""
    key = get_llm_key()
    if not key:
        return {}
    news_text = '\n'.join(f'{i+1}. {t}' for i, (t, c) in enumerate(news_list[:15]))
    prompt = f"""你是金融新闻分析员。分析以下新闻，输出每条的影响：
1. 影响哪些板块/行业（A股板块名）
2. 利好还是利空（利好/利空/中性）
3. 影响强度（1-5，5最强）
4. 事件级别（大/中/小）：
   - 大=影响市场数周至数月的大趋势（政策转向/宏观数据拐点/地缘危机/央行行动/行业革命）
   - 中=影响一周至数周（行业政策/龙头业绩/重大合同/监管变化）
   - 小=影响数日（日常新闻/个股消息/常规数据）

新闻：
{news_text}

输出 JSON：{{"1": {{"sector": "半导体", "direction": "利好", "strength": 4, "level": "大"}}, ...}}（编号对应新闻序号）"""

    import urllib.request
    body = json.dumps({
        'model': 'deepseek-chat',
        'messages': [{'role': 'system', 'content': '你是金融新闻分析员，输出严格 JSON。'},
                     {'role': 'user', 'content': prompt}],
        'temperature': 0.2, 'max_tokens': 800
    }).encode('utf-8')
    req = urllib.request.Request('https://api.deepseek.com/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
        content = resp['choices'][0]['message']['content']
        import re
        m = re.search(r'\{.*\}', content, re.S)
        if m:
            return json.loads(m.group())
    except Exception as e:
        print(f'LLM 分析失败: {str(e)[:60]}')
    return {}

def main():
    conn = get_conn()
    # 取未分析的新闻（最新 15 条——按 id 倒序）
    rows = conn.execute("SELECT id, title, content FROM news WHERE (sector IS NULL OR sector='') ORDER BY id DESC LIMIT 15").fetchall()
    if not rows:
        print('无新新闻待分析')
        conn.close()
        return
    print(f'待分析 {len(rows)} 条')
    result = analyze_batch([(r['title'], r['content']) for r in rows])
    n = 0
    for i, r in enumerate(rows):
        info = result.get(str(i + 1))
        if info:
            conn.execute('UPDATE news SET sector=?, impact=?, strength=?, level=? WHERE id=?',
                         (info.get('sector', ''), info.get('direction', '中性'), info.get('strength', 0), info.get('level', '小'), r['id']))
            n += 1
    conn.commit()
    cnt = conn.execute("SELECT COUNT(*) FROM news WHERE sector IS NOT NULL AND sector != ''").fetchone()[0]
    conn.close()
    print(f'✅ 分析完成 {n}/{len(rows)} | 已分析总数 {cnt}')

if __name__ == '__main__':
    main()
