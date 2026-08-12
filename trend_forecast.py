"""分级预测引擎：事件级别 → 分层预测（大趋势区间 / 中期方向 / 短期波动）"""
import sys, os, json
import akshare as ak
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn
from sentiment_llm import llm_analyze, get_llm_key

def get_events():
    """从新闻库读事件（按级别）——大/中事件独立取（不被最新小事件挤出）"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT title, sector, impact, strength, level FROM news
        WHERE level IS NOT NULL AND level != ''
        ORDER BY id DESC LIMIT 40
    """).fetchall()
    big = conn.execute("""
        SELECT title, sector, impact, strength, level FROM news
        WHERE level = '大' ORDER BY id DESC LIMIT 8
    """).fetchall()
    mid = conn.execute("""
        SELECT title, sector, impact, strength, level FROM news
        WHERE level = '中' ORDER BY id DESC LIMIT 8
    """).fetchall()
    conn.close()
    small = [r for r in rows if r['level'] == '小']
    return big, mid, small

def llm_trend_forecast(big_events, target):
    """大事件 → 中期大趋势预测（LLM）"""
    key = get_llm_key()
    if not key or not big_events:
        return None
    ev_text = '\n'.join(f'- [{e["sector"]}] {e["impact"]}({e["strength"]}): {e["title"][:50]}' for e in big_events[:8])
    prompt = f"""你是资深金融策略分析师。以下是近期【大事件】（影响数周至数月）：

{ev_text}

请对 {target} 做【中期大趋势预测】（未来 1-3 个月）：
1. 大区间判断：高位区间/低位区间/震荡区间（价格或指数状态）
2. 核心驱动（大事件如何传导）
3. 关键观察点（什么信号会改变判断）
4. 置信度（高/中/低）

简洁专业，输出 JSON：
{{"range": "高位区间/低位区间/震荡区间", "driver": "...", "watch": "...", "confidence": "中"}}"""
    import urllib.request
    body = json.dumps({
        'model': 'deepseek-chat',
        'messages': [{'role': 'system', 'content': '你是资深金融策略分析师，输出严格 JSON。'},
                     {'role': 'user', 'content': prompt}],
        'temperature': 0.3, 'max_tokens': 500
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
        return {'error': str(e)[:60]}
    return None

def main():
    target = 'A股大盘'
    big, mid, small = get_events()
    print('=' * 56)
    print(f'📊 分级预测报告（{target}）')
    print('=' * 56)
    # 宏观环境（新增——预测输入）
    try:
        from macro_env import macro_env
        me = macro_env()
        print(f'\n🌐 【宏观环境】')
        for p in me.get('parts', []):
            print(f'  · {p}')
        print(f'  → {me.get("verdict", "")}')
    except Exception as e:
        print(f'\n🌐 宏观环境获取失败: {str(e)[:40]}')
    print(f'\n📰 事件分布：大 {len(big)} 条 | 中 {len(mid)} 条 | 小 {len(small)} 条')
    # 大事件 → 中期趋势
    if big:
        print('\n🔥 【大事件】→ 中期大趋势（1-3 个月）:')
        for e in big[:5]:
            print(f'  [{e["sector"]}] {e["impact"]}({e["strength"]}): {e["title"][:45]}')
        trend = llm_trend_forecast(big, target)
        if trend and 'range' in trend:
            print(f'\n  🎯 大区间判断: {trend["range"]}')
            print(f'  驱动: {trend.get("driver", "")[:80]}')
            print(f'  观察点: {trend.get("watch", "")[:80]}')
            print(f'  置信度: {trend.get("confidence", "")}')
    else:
        print('\n🔥 【大事件】: 近期无大级别事件——市场处于无大趋势催化状态')
        print('   → 中期判断：大概率维持震荡区间（无方向性驱动）')
    # 中事件 → 中期方向
    if mid:
        print(f'\n📌 【中事件】→ 1-4 周方向:')
        for e in mid[:6]:
            print(f'  [{e["sector"]}] {e["impact"]}({e["strength"]}): {e["title"][:40]}')
    else:
        print('\n📌 【中事件】: 无')
    # 小事件 → 短期
    if small:
        print(f'\n⚡ 【小事件】→ 短期（1-5 日）:')
        # 汇总板块情绪（利好-利空）
        sector_scores = {}
        for e in small:
            s = sector_scores.setdefault(e['sector'], 0)
            delta = e['strength'] if e['impact'] == '利好' else (-e['strength'] if e['impact'] == '利空' else 0)
            sector_scores[e['sector']] = s + delta
        top = sorted(sector_scores.items(), key=lambda x: -x[1])[:5]
        print('  板块短期情绪（利好正/利空负）:')
        for sec, score in top:
            bar = '█' * min(abs(score), 10)
            print(f'    {sec}: {"+" if score > 0 else ""}{score} {bar}')
    print('\n---')
    print('⚠️ 分级预测仅供参考——大趋势看大事件/短期看小事件——组合使用')

if __name__ == '__main__':
    main()
