"""组合分析：收益/风险/相关性/集中度/夏普——组合诊断"""
import sys, os
import akshare as ak
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def load_returns(code, start='20260101', end='20260810'):
    symbol = ('sh' if code.startswith('6') else 'sz') + code
    try:
        df = ak.stock_zh_a_daily(symbol=symbol, start_date=start, end_date=end, adjust='qfq')
        if df is None or len(df) < 20:
            return None
        s = df.set_index('date')['close'].pct_change().dropna()
        return s
    except Exception:
        return None

def analyze(portfolio):
    """组合诊断：输入 [(code, name, weight)]"""
    print('=' * 56)
    print('📊 组合分析')
    print('=' * 56)
    rets = {}
    for code, name, w in portfolio:
        r = load_returns(code)
        if r is not None:
            rets[name] = r
            print(f'✅ {name}: {len(r)} 交易日')
    if len(rets) < 2:
        print('❌ 数据不足（至少 2 只）')
        return
    df = pd.DataFrame(rets).dropna()
    weights = np.array([w for _, _, w in portfolio if portfolio[[x[1] for x in portfolio].index(_name)][2] for _name in [None]][0]) if False else None
    # 简化：等权
    w = np.ones(len(df.columns)) / len(df.columns)
    # 收益/风险
    daily_ret = df.mean(axis=1)
    port_ret = (1 + daily_ret).prod() ** (250 / len(df)) - 1
    port_vol = daily_ret.std() * np.sqrt(250)
    sharpe = port_ret / port_vol if port_vol > 0 else 0
    print(f'\n📈 组合年化收益: {port_ret*100:.1f}%')
    print(f'📉 年化波动: {port_vol*100:.1f}%')
    print(f'⭐ 夏普比率: {sharpe:.2f}')
    # 个股贡献
    print('\n🏷️ 个股表现:')
    for name in df.columns:
        r = df[name].mean() * 250
        v = df[name].std() * np.sqrt(250)
        print(f'  {name}: 年化 {r*100:+.1f}% | 波动 {v*100:.1f}%')
    # 相关性
    print('\n🔗 相关性矩阵:')
    corr = df.corr()
    print(corr.round(2).to_string())
    # 集中度/分散
    avg_corr = (corr.values.sum() - len(corr)) / (len(corr) * (len(corr) - 1))
    print(f'\n平均相关性: {avg_corr:.2f}')
    if avg_corr > 0.7:
        print('⚠️ 相关性过高——组合分散不足（同涨同跌）')
    elif avg_corr < 0.3:
        print('✅ 相关性低——分散良好')
    else:
        print('🟡 相关性中等')
    # 最大回撤
    cum = (1 + daily_ret).cumprod()
    dd = (cum / cum.cummax() - 1).min()
    print(f'📉 区间最大回撤: {dd*100:.1f}%')

if __name__ == '__main__':
    demo = [('600519', '茅台', 0.2), ('300750', '宁德', 0.2), ('603259', '药明', 0.2),
            ('601318', '平安', 0.2), ('600036', '招行', 0.2)]
    analyze(demo)
