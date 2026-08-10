"""新闻时钟：多源全球新闻抓取入库（每30分钟自动跑）"""
import sys, os
import akshare as ak
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

SOURCES = [
    ('东财全球快讯', lambda: ak.stock_info_global_em()),
    ('财联社电报', lambda: ak.stock_info_global_cls()),
    ('新浪快讯', lambda: ak.stock_info_global_sina()),
    ('同花顺快讯', lambda: ak.stock_info_global_ths()),
    ('富途快讯', lambda: ak.stock_info_global_futu()),
]

def pull():
    conn = get_conn()
    total = 0
    for src, fn in SOURCES:
        try:
            df = fn()
            n = 0
            for _, r in df.head(30).iterrows():
                title = str(r.get('标题', '') or r.get('title', '') or '')
                content = str(r.get('摘要', '') or r.get('内容', '') or '')[:300]
                ts = str(r.get('发布时间', '') or r.get('时间', '') or r.get('date', '') or '')
                if not title:
                    continue
                # 去重插入（标题唯一）
                cur = conn.execute('SELECT COUNT(*) FROM news WHERE title=?', (title,)).fetchone()[0]
                if cur == 0:
                    conn.execute('INSERT OR IGNORE INTO news (date, title, content, source) VALUES (?,?,?,?)',
                                 (ts[:10], title, content, src))
                    n += 1
            total += n
            print(f'✅ {src}: +{n} 条')
        except Exception as e:
            print(f'❌ {src}: {str(e)[:60]}')
    conn.commit()
    cnt = conn.execute('SELECT COUNT(*) FROM news').fetchone()[0]
    conn.close()
    print(f'📰 本次入库 {total} 条 | 新闻库总计 {cnt} 条')
    # 自动分析新新闻（LLM——板块/利好利空）
    try:
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'news_analyze.py')],
                           capture_output=True, text=True, timeout=180)
        print(r.stdout.strip())
        if r.returncode != 0:
            print('分析错误:', r.stderr[-200:])
    except Exception as e:
        print(f'分析调用失败: {str(e)[:60]}')

if __name__ == '__main__':
    pull()
