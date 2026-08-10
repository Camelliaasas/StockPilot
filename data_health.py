"""数据健康检查：各表最新日期/行数/异常检测——每日监控"""
import sys, os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, 'C:/Users/23643/src_workflow/stock_predict')
from db import get_conn

def health_check():
    """数据健康——异常返回问题列表（正常返回空=静默）"""
    issues = []
    conn = get_conn()
    # 各表行数
    for table in ['daily_prices', 'financials', 'news', 'predictions', 'sentiment_daily']:
        try:
            cnt = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            if cnt == 0:
                issues.append(f'⚠️ {table} 表为空！')
        except Exception as e:
            issues.append(f'⚠️ {table} 读取失败: {str(e)[:30]}')
    # 日线最新日期（应接近今天）
    try:
        last = conn.execute("SELECT MAX(date) FROM daily_prices").fetchone()[0]
        if last:
            last_d = datetime.strptime(str(last)[:10], '%Y-%m-%d')
            diff = (datetime.now() - last_d).days
            if diff > 5:
                issues.append(f'⚠️ 日线数据停留 {str(last)[:10]}——{diff} 天未更新！')
    except Exception:
        pass
    # 新闻最新
    try:
        last_n = conn.execute("SELECT MAX(ts) FROM news").fetchone()[0]
        if last_n:
            print(f'✅ 新闻最新: {str(last_n)[:16]}')
    except Exception:
        pass
    conn.close()
    return issues

if __name__ == '__main__':
    issues = health_check()
    if issues:
        print('🚨 数据健康检查发现问题:')
        for i in issues:
            print(f'  {i}')
    # 无问题——输出正常状态（cron local 记录——不推送）
