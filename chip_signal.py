"""筹码集中度引擎：股东户数变化 → 集中/分散信号（主力吸筹/派发）"""
import sys, os
import akshare as ak
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def chip_signal(code, name=''):
    """筹码信号：股东户数变化"""
    code = str(code).replace('sh', '').replace('sz', '').replace('bj', '').strip()
    result = {'code': code, 'name': name, 'signal': '', 'detail': ''}
    try:
        df = ak.stock_zh_a_gdhs_detail_em(symbol=code)
        if df is None or len(df) < 2:
            result['signal'] = '数据不足'
            return result
        latest = df.iloc[-1]  # 最新一期（接口按时间升序）
        change = latest.get('股东户数-增减比例')
        holders = latest.get('股东户数-本次')
        date = latest.get('股东户数统计截止日')
        if change is not None:
            try:
                chg = float(change)
            except Exception:
                chg = None
            if chg is not None:
                result['detail'] = f'{date} 户数 {holders:,.0f}（{chg:+.1f}%）'
                if chg < -5:
                    result['signal'] = f'🔴 筹码集中（户数{chg:+.1f}%——主力吸筹）'
                elif chg < -2:
                    result['signal'] = f'🟠 筹码趋集中（{chg:+.1f}%）'
                elif chg > 5:
                    result['signal'] = f'🟢 筹码分散（户数{chg:+.1f}%——散户涌入）'
                elif chg > 2:
                    result['signal'] = f'🟡 筹码趋分散（{chg:+.1f}%）'
                else:
                    result['signal'] = f'⚪ 筹码平稳（{chg:+.1f}%）'
        # 近 4 期趋势（最新 4 期）
        if len(df) >= 4:
            recent = df['股东户数-增减比例'].tail(4).tolist()
            result['detail'] += f' | 近4期: {[round(x,1) if x==x else None for x in recent]}'
    except Exception as e:
        result['signal'] = f'获取失败 {str(e)[:40]}'
    return result

if __name__ == '__main__':
    for code, name in [('600519', '贵州茅台'), ('300750', '宁德时代'), ('601318', '中国平安')]:
        r = chip_signal(code, name)
        print(f"\n📊 筹码：{r['name']}")
        print(f"  {r['signal']}")
        if r['detail']:
            print(f"  📝 {r['detail']}")
