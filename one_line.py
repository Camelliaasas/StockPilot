"""一句话看盘：LLM 综合今日新闻+板块+情绪 → 1 句核心判断"""
import sys, os, json
import akshare as ak
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn
from sentiment_llm import get_llm_key

def one_line():
    """生成一句话看盘"""
    key = get_llm_key()
    if not key:
        return 'LLM key 未配置'
    # 数据
    try:
        news = [f'{r["标题"]}' for _, r in ak.stock_info_global_em().head(10).iterrows()]
    except Exception:
        news = []
    try:
        boards = ak.stock_sector_spot(indicator='新浪行业')
        top3 = boards.drop_duplicates(subset='板块').nlargest(3, '涨跌幅')['板块'].tolist()
    except Exception:
        top3 = []
    conn = get_conn()
    senti = conn.execute("SELECT COUNT(*), SUM(CASE WHEN impact='利好' THEN 1 ELSE 0 END), SUM(CASE WHEN impact='利空' THEN 1 ELSE 0 END) FROM news WHERE impact IS NOT NULL").fetchone()
    conn.close()
    pos = senti[1] or 0
    neg = senti[2] or 0
    # LLM
    prompt = f"""你是资深财经主编。基于以下信息，用【一句话】总结今天的市场核心判断（30字内——直击要害——像财经头条）：

今日重要新闻：
{chr(10).join(f'- {n[:40]}' for n in news[:8])}

领涨板块：{', '.join(top3) if top3 else '无'}
新闻情绪：利好{pos} / 利空{neg}

输出格式：一句话（含方向判断——偏多/偏空/震荡）+ 一个核心关注点"""
    import urllib.request
    body = json.dumps({
        'model': 'deepseek-chat',
        'messages': [{'role': 'system', 'content': '你是资深财经主编，输出精炼一句话。'},
                     {'role': 'user', 'content': prompt}],
        'temperature': 0.5, 'max_tokens': 200
    }).encode('utf-8')
    req = urllib.request.Request('https://api.deepseek.com/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
        return resp['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f'LLM 调用失败: {str(e)[:60]}'

if __name__ == '__main__':
    print('📌 一句话看盘：')
    print(one_line())
