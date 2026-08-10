"""财务数据入库：业绩报表（全市场季度）→ financials 表——基本面分析数据底座"""
import akshare as ak
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def pull_financials():
    """拉最新季度业绩报表（全市场——5894 只）入库"""
    conn = get_conn()
    # 最新报告期（2026 一季报）
    for report in ['20260630', '20260331', '20251231']:
        try:
            df = ak.stock_yjbb_em(date=report)
            n = 0
            for _, r in df.iterrows():
                code = str(r.get('股票代码', ''))
                name = str(r.get('股票简称', ''))
                eps = r.get('每股收益')
                revenue = r.get('营业总收入-营业总收入')
                rev_yoy = r.get('营业总收入-同比增长')
                profit = r.get('净利润-净利润')
                profit_yoy = r.get('净利润-同比增长')
                roe = r.get('净资产收益率')
                if not code:
                    continue
                conn.execute('INSERT OR REPLACE INTO financials (code, name, report_date, eps, revenue, revenue_yoy, profit, profit_yoy, roe) VALUES (?,?,?,?,?,?,?,?,?)',
                             (code, name, report, eps, revenue, rev_yoy, profit, profit_yoy, roe))
                n += 1
            conn.commit()
            print(f'✅ 报告期 {report}: {n} 只入库')
        except Exception as e:
            print(f'❌ {report}: {str(e)[:60]}')
    cnt = conn.execute('SELECT COUNT(*) FROM financials').fetchone()[0]
    conn.close()
    print(f'📊 财务库总计 {cnt} 行')

if __name__ == '__main__':
    pull_financials()
