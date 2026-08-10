"""自主验证：每日对照预测 vs 实际——算准确率——校准置信度——闭环"""
import sys, os
import akshare as ak
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def verify():
    conn = get_conn()
    # 取未验证的预测（昨日之前的）
    preds = conn.execute("SELECT * FROM predictions WHERE actual_direction IS NULL AND date < date('now','localtime')").fetchall()
    if not preds:
        print('无待验证预测')
        return
    # 拉昨日上证实际涨跌
    idx = ak.stock_zh_index_daily(symbol='sh000001')
    last = idx.iloc[-1]
    prev = idx.iloc[-2]
    actual_ret = last['close'] / prev['close'] - 1
    if actual_ret > 0.005:
        actual_dir = '看多'
    elif actual_ret < -0.005:
        actual_dir = '看空'
    else:
        actual_dir = '观望'
    print(f'实际: {last["date"]} 涨跌 {actual_ret*100:+.2f}% → {actual_dir}')
    # 对照每个预测
    for p in preds:
        correct = 1 if p['direction'] == actual_dir else 0
        conn.execute('UPDATE predictions SET actual_direction=?, correct=? WHERE id=?',
                     (actual_dir, correct, p['id']))
        print(f'  {p["code"]}: 预测{p["direction"]} vs 实际{actual_dir} → {"✅" if correct else "❌"}')
    conn.commit()
    # 累计准确率
    stats = conn.execute("SELECT direction, COUNT(*), SUM(correct) FROM predictions WHERE correct IS NOT NULL GROUP BY direction").fetchall()
    print('\n📊 累计准确率:')
    total_c, total_w = 0, 0
    for d, n, c in stats:
        total_c += c; total_w += n
        print(f'  {d}: {c}/{n} ({c/n*100:.0f}%)')
    if total_w > 0:
        print(f'  总计: {total_c}/{total_w} ({total_c/total_w*100:.1f}%)')
    conn.close()

if __name__ == '__main__':
    verify()
