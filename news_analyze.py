"""新闻分析层：LLM 自动分析新入库新闻——影响板块/利好利空——供预测使用"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn
from sentiment_llm import get_llm_key

def analyze_batch(news_list):
    """新闻分析：LLM 优先——余额不足自动降级关键词规则"""
    try:
        result = _llm_analyze(news_list)
        if result:
            return result
    except Exception:
        pass
    return _rule_analyze(news_list)

# 关键词规则（降级用——不依赖 LLM）
_POS = ['利好', '增长', '突破', '创新', '中标', '回购', '增持', '获批', '超预期', '涨价', '景气', '扩产', '降息', '宽松']
_NEG = ['利空', '下跌', '亏损', '减持', '违规', '处罚', '调查', '退市', '下滑', '裁员', '收缩', '加息', '风险', '违约']
_SECTORS = {'半导体': ['芯片', '半导体', '存储', '晶圆'], '人工智能': ['AI', '人工智能', '大模型', '算力', '机器人'],
            '新能源': ['光伏', '锂电', '电池', '新能源', '储能'], '医药': ['医药', '药', '医疗', '创新药', '疫苗'],
            '金融': ['银行', '证券', '保险', '央行', '利率', 'LPR'], '地产': ['房地产', '楼市', '房价', '房企'],
            '消费': ['消费', '白酒', '食品', '零售', '餐饮'], '汽车': ['汽车', '新能源车', '特斯拉'],
            '石油': ['石油', '原油', '油'], '军工': ['军工', '国防', '航空'], '农业': ['农业', '粮食', '养殖', '猪肉']}

def _rule_analyze(news_list):
    """关键词规则分析（降级）"""
    result = {}
    for i, (t, c) in enumerate(news_list[:15]):
        text = f'{t} {c or ""}'
        pos = sum(1 for w in _POS if w in text)
        neg = sum(1 for w in _NEG if w in text)
        if pos > neg:
            direction, strength = '利好', min(5, 1 + pos)
        elif neg > pos:
            direction, strength = '利空', min(5, 1 + neg)
        else:
            direction, strength = '中性', 2
        sector = '其他'
        for s, kws in _SECTORS.items():
            if any(k in text for k in kws):
                sector = s
                break
        # 级别：央行/政策/国际 = 大；行业/公司 = 中；其余 = 小
        level = '小'
        if any(k in text for k in ['央行', '国务院', '政策', '美联储', '关税', '利率', '制裁', '法案']):
            level = '大'
        elif any(k in text for k in ['行业', '龙头', '中标', '获批', '减持', '回购', '增持', '调查']):
            level = '中'
        result[str(i + 1)] = {'sector': sector, 'direction': direction, 'strength': strength, 'level': level}
    return result

def _llm_analyze(news_list):
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
