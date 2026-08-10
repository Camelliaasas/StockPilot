"""深度财务：300 只核心股全指标入库（ROE/毛利率/净利率/负债/现金流/周转）"""
import akshare as ak
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

# 关键指标（从同花顺财务分析指标选）
KEY_METRICS = [
    '摊薄每股收益(元)', '每股净资产_调整前(元)', '净资产收益率(%)', '加权净资产收益率(%)',
    '销售毛利率(%)', '销售净利率(%)', '营业利润率(%)', '总资产利润率(%)',
    '主营业务收入增长率(%)', '净利润增长率(%)', '总资产增长率(%)',
    '资产负债率(%)', '流动比率', '速动比率', '总资产周转率(次)',
    '应收账款周转率(次)', '存货周转率(次)', '经营现金净流量与净利润的比率',
]

def main():
    conn = get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS deep_financials (
        code TEXT, name TEXT, report_date TEXT,
        eps REAL, bps REAL, roe REAL, gross_margin REAL, net_margin REAL,
        op_margin REAL, rev_yoy REAL, profit_yoy REAL, asset_yoy REAL,
        debt_ratio REAL, current_ratio REAL, quick_ratio REAL,
        asset_turnover REAL, ar_turnover REAL, inv_turnover REAL,
        ocf_ratio REAL, PRIMARY KEY (code, report_date)
    )''')
    # 核心股票池（沪深300 代码）
    stocks = ['600519','300750','000858','601318','600036','000333','600900','002594','601899','600030',
              '601012','002415','600276','000651','601888','002475','600809','603288','000725','600887',
              '002714','601166','000002','600585','601398','600028','601857','600050','601668','000001',
              '688981','002230','603259','300059','601211','600104','002352','600690','002027','601628',
              '300760','002304','603501','300124','600570','002460','600438','300014','002371','601088',
              '600309','002142','601601','002050']
    ok = 0
    for code in stocks:
        try:
            df = ak.stock_financial_analysis_indicator(symbol=code, start_year='2023')
            if df is None or len(df) == 0:
                continue
            latest = df.iloc[-1]
            date = str(latest.get('日期', ''))[:10]
            def g(col):
                v = latest.get(col, None)
                try:
                    return float(v) if v is not None and v == v else None  # 去 NaN
                except Exception:
                    return None
            conn.execute('INSERT OR REPLACE INTO deep_financials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                         (code, '', date, g('摊薄每股收益(元)'), g('每股净资产_调整前(元)'),
                          g('净资产收益率(%)'), g('销售毛利率(%)'), g('销售净利率(%)'),
                          g('营业利润率(%)'), g('主营业务收入增长率(%)'), g('净利润增长率(%)'),
                          g('总资产增长率(%)'), g('资产负债率(%)'), g('流动比率'), g('速动比率'),
                          g('总资产周转率(次)'), g('应收账款周转率(次)'), g('存货周转率(次)'),
                          g('经营现金净流量与净利润的比率')))
            ok += 1
            time.sleep(0.5)
        except Exception as e:
            pass
        if ok % 25 == 0 and ok > 0:
            conn.commit()
            print(f'进度: {ok}/54', flush=True)
    conn.commit()
    cnt = conn.execute('SELECT COUNT(*) FROM deep_financials').fetchone()[0]
    conn.close()
    print(f'✅ 深度财务入库 {ok} 只 | 库 {cnt} 行')

if __name__ == '__main__':
    main()
