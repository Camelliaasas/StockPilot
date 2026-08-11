"""P3 数据源管理器：多源自动切换（东财断→腾讯→新浪——稳定性加强）"""
import sys, os
import akshare as ak
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 统一行情获取（多源 fallback——稳定性）
def get_spot_multi(code):
    """获取实时行情：东财→腾讯→新浪 依次尝试"""
    symbol = ('sh' if code.startswith('6') else 'sz') + code
    # 源1：东财 spot（全市场一次拉——缓存）
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df['代码'] == code]
        if len(row) > 0:
            r = row.iloc[0]
            return {'price': float(r['最新价']), 'change': float(r['涨跌幅']),
                    'amount': float(r.get('成交额', 0) or 0), 'source': '东财'}
    except Exception:
        pass
    # 源2：新浪 spot
    try:
        df = ak.stock_zh_a_spot()
        row = df[df['代码'] == code]
        if len(row) > 0:
            r = row.iloc[0]
            return {'price': float(r['最新价']), 'change': float(r['涨跌幅']),
                    'amount': float(r.get('成交额', 0) or 0), 'source': '新浪'}
    except Exception:
        pass
    # 源3：腾讯日线（最后一天）
    try:
        df = ak.stock_zh_a_daily(symbol=symbol, start_date='20260801', end_date='20260810', adjust='qfq')
        if df is not None and len(df) > 0:
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            chg = (float(last['close']) / float(prev['close']) - 1) * 100
            return {'price': float(last['close']), 'change': chg, 'amount': 0, 'source': '腾讯日线'}
    except Exception:
        pass
    return None

def get_market_spot():
    """全市场行情（新浪优先——东财断时自动切换）"""
    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and len(df) > 1000:
            return df, '东财'
    except Exception:
        pass
    try:
        df = ak.stock_zh_a_spot()
        if df is not None and len(df) > 1000:
            return df, '新浪'
    except Exception:
        pass
    return None, '不可用'

if __name__ == '__main__':
    # 测试多源
    for code in ['600519', '300750', '601318']:
        r = get_spot_multi(code)
        if r:
            print(f"{code}: {r['price']} ({r['change']:+.2f}%) 源={r['source']}")
        else:
            print(f"{code}: 全部源失败")
