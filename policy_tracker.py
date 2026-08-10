"""政策实时追踪器：各国政府决策跟踪 → 影响分析 → 重大政策即时推送"""
import sys, os, json, re
import akshare as ak
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn
from sentiment_llm import get_llm_key

# 政策关键词（政府/央行/监管决策）
POLICY_KEYWORDS = [
    '政策', '央行', '美联储', '降息', '加息', '降准', '国常会', '发改委', '证监会',
    '财政部', '白宫', '欧央行', '日央行', 'OPEC', '关税', '制裁', '法案', '决议',
    '讲话', '会议', '放水', '缩表', '加息', '利率', 'LPR', 'MLF', '监管', '新规',
    '国务院', '商务部', '工信部', '住建部', '新能源补贴', '出口管制',
    'Trump', 'Fed', 'ECB', 'BOJ', 'Congress', 'White House', 'tariff', 'sanction'
]

def is_policy(title):
    """判断是否为政策类新闻"""
    return any(k.lower() in title.lower() for k in POLICY_KEYWORDS)

def scan_policy():
    """扫描最新新闻——找政策类——LLM 分析——重大推送"""
    conn = get_conn()
    # 抓最新新闻（多源）
    all_news = []
    sources = [
        ('东财', lambda: ak.stock_info_global_em()),
        ('财联社', lambda: ak.stock_info_global_cls()),
        ('同花顺', lambda: ak.stock_info_global_ths()),
    ]
    for src, fn in sources:
        try:
            df = fn()
            for _, r in df.head(20).iterrows():
                t = str(r.get('标题', '') or '')
                c = str(r.get('摘要', '') or r.get('内容', '') or '')[:200]
                ts = str(r.get('发布时间', '') or '')[:16]
                if t:
                    all_news.append((ts, t, c, src))
        except Exception:
            pass
    # 过滤政策类
    policy_news = [n for n in all_news if is_policy(n[1])]
    if not policy_news:
        conn.close()
        return []  # 静默（无政策不推送）
    # 去重入库（标题唯一）
    new_events = []
    for ts, t, c, src in policy_news[:12]:
        cur = conn.execute('SELECT COUNT(*) FROM news WHERE title=?', (t,)).fetchone()[0]
        if cur == 0:
            conn.execute('INSERT OR IGNORE INTO news (date, title, content, source, level) VALUES (?,?,?,?,?)',
                         (ts[:10], t, c, src, '政策'))
            new_events.append((ts, t, c))
    conn.commit()
    if not new_events:
        conn.close()
        return []  # 无新政策——静默
    print(f'📡 发现 {len(new_events)} 条新政策/决策:')
    for ts, t, c in new_events:
        print(f'  [{ts}] {t[:60]}')
    # LLM 分析新政策（影响）
    if new_events:
        analyze_policy(new_events)
    conn.close()
    return new_events

def analyze_policy(events):
    """LLM 分析政策：影响板块/品种 + 方向 + 强度 + 传导逻辑"""
    key = get_llm_key()
    if not key:
        print('LLM key 未配置——跳过分析')
        return
    news_text = '\n'.join(f'- [{t}] {c[:60]}' for _, t, c in events[:10])
    prompt = f"""你是政策研究员+金融分析师。分析以下最新政策/决策：

{news_text}

对每一条：
1. 政策主体（哪个政府/央行/机构）
2. 政策内容一句话概括
3. 影响方向（利好/利空/中性）+ 影响强度（1-5）
4. 影响哪些板块/品种（A股板块/期货品种）
5. 传导逻辑（政策→经济→市场）

输出 JSON：{{"1": {{"body": "美联储", "summary": "...", "direction": "利好", "strength": 4, "sectors": ["黄金", "有色"], "logic": "..."}}, ...}}"""
    import urllib.request
    body = json.dumps({
        'model': 'deepseek-chat',
        'messages': [{'role': 'system', 'content': '你是政策研究员+金融分析师，输出严格 JSON。'},
                     {'role': 'user', 'content': prompt}],
        'temperature': 0.3, 'max_tokens': 900
    }).encode('utf-8')
    req = urllib.request.Request('https://api.deepseek.com/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            resp = json.loads(r.read())
        content = resp['choices'][0]['message']['content']
        m = re.search(r'\{.*\}', content, re.S)
        if m:
            raw = m.group()
            # JSON 容错：单引号→双引号
            fixed = raw.replace("'", '"')
            try:
                result = json.loads(fixed)
            except Exception:
                # 再试：去换行
                result = json.loads(fixed.replace('\n', '').replace('  ', ' '))
            # 打印分析结果
            for k, v in result.items():
                print(f"\n🏛️ 政策分析[{k}]:")
                print(f"  主体: {v.get('body', '')}")
                print(f"  内容: {v.get('summary', '')[:60]}")
                print(f"  方向: {v.get('direction', '')} 强度{v.get('strength', '')}")
                print(f"  影响: {', '.join(v.get('sectors', [])) if isinstance(v.get('sectors'), list) else v.get('sectors', '')}")
                print(f"  传导: {v.get('logic', '')[:70]}")
            return result
    except Exception as e:
        print(f'政策分析失败: {str(e)[:60]}')
    return None

if __name__ == '__main__':
    scan_policy()
