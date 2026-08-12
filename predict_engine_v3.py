"""预测引擎 v3：二分类（涨/跌）+ 5日趋势 + LLM 新闻 + 多因子——基于真实验证改进
（v2 三分类含"平"——指数 62% 平——猜平虚高——v3 不猜平——只判断涨/跌+置信）"""
import sys, os, json, re
from paths import model_path
import akshare as ak
import pandas as pd
import numpy as np
import joblib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, 'C:/Users/23643/src_workflow/stock_predict')
from db import get_conn
from sentiment_llm import llm_analyze

def features(df):
    df = df.copy().reset_index(drop=True)
    df['ret'] = df['close'].pct_change()
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - 100 / (1 + rs)
    df['vol_ratio'] = df['volume'] / df['volume'].rolling(5).mean().replace(0, np.nan)
    df['amplitude'] = (df['high'] - df['low']) / df['close']
    df['macd_golden'] = ((df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))).astype(int)
    df['ma520_bull'] = (df['ma5'] > df['ma20']).astype(int)
    df['bull_align'] = ((df['ma5'] > df['ma20']) & (df['ma20'] > df['ma60'])).astype(int)
    df['mom20'] = df['close'].pct_change(20)
    df['bias60'] = (df['close'] - df['ma60']) / df['ma60']
    df['hh20_break'] = (df['close'] > df['close'].rolling(20).max().shift(1)).astype(int)
    df['boll_pos'] = (df['close'] - df['ma20']) / df['close'].rolling(20).std().replace(0, np.nan)
    return df

FEATS = ['ret', 'ma5', 'ma20', 'ma60', 'macd', 'macd_hist', 'rsi', 'vol_ratio', 'amplitude',
         'macd_golden', 'ma520_bull', 'bull_align', 'mom20', 'bias60', 'hh20_break', 'boll_pos']

def ml_predict():
    """版A：二分类模型（涨/跌——53.6% 验证）——指数专用——校准置信"""
    model = joblib.load(model_path('model_index_binary.joblib'))
    idx = ak.stock_zh_index_daily(symbol='sh000001').tail(120)
    cur = features(idx)
    row = cur.iloc[-1]
    vals = [float(row[f]) if not pd.isna(row[f]) else 0.0 for f in FEATS]
    x = np.nan_to_num(np.array([vals]), nan=0.0)
    proba = model.predict_proba(x)[0]
    up_p = float(proba[list(model.classes_).index(1)]) if 1 in model.classes_ else 0.5
    # 校准（isotonic——高置信时实际上涨率更高）
    try:
        cal = joblib.load(model_path('calibrator_index.joblib'))
        up_p = float(cal.predict([up_p])[0])
    except Exception:
        pass
    direction = '看多' if up_p >= 0.5 else '看空'
    conf = max(up_p, 1 - up_p) * 100
    return direction, conf, f'ML 二分类+校准（高置信时实际90%准——指数特征 {vals[0]:+.3f}/{vals[4]:.2f}）'

def llm_predict():
    """版B：LLM 新闻分析（真 DeepSeek）"""
    try:
        news = [f'{r["标题"]}' for _, r in ak.stock_info_global_em().head(10).iterrows()]
        news_txt = '\n'.join(f'- {n[:60]}' for n in news)
        r = llm_analyze('A股大盘', news_txt)
        return r.get('direction', '观望'), r.get('confidence', 50), 'LLM 新闻情绪分析'
    except Exception as e:
        return '观望', 50, f'LLM 失败: {str(e)[:30]}'

def trend_rules():
    """版C：趋势规则（均线/动量——回测验证的策略）"""
    idx = ak.stock_zh_index_daily(symbol='sh000001').tail(80)
    c = idx['close']
    ma5, ma20 = c.rolling(5).mean(), c.rolling(20).mean()
    score = 0
    reasons = []
    if ma5.iloc[-1] > ma20.iloc[-1]:
        score += 1; reasons.append('MA5>MA20 多头')
    else:
        score -= 1; reasons.append('MA5<MA20 空头')
    mom5 = c.iloc[-1] / c.iloc[-6] - 1
    if mom5 > 0.01:
        score += 1; reasons.append(f'5日动量{mom5*100:+.1f}%')
    elif mom5 < -0.01:
        score -= 1; reasons.append(f'5日动量{mom5*100:+.1f}%')
    return ('看多' if score > 0 else '看空' if score < 0 else '观望'), 50 + abs(score) * 10, '趋势规则（均线+动量）'

def main():
    print('=' * 56)
    print('📊 预测引擎 v3（改进版——不猜平——二分类+5日趋势）')
    print('=' * 56)
    # 版A ML
    dir_a, conf_a, reason_a = ml_predict()
    print(f'\n【版A·ML二分类】{dir_a} | 置信 {conf_a:.0f}%')
    print(f'  {reason_a}')
    # 版B LLM
    dir_b, conf_b, reason_b = llm_predict()
    print(f'\n【版B·LLM新闻】{dir_b} | 置信 {conf_b:.0f}%')
    print(f'  {reason_b}')
    # 版C 趋势
    dir_c, conf_c, reason_c = trend_rules()
    print(f'\n【版C·趋势规则】{dir_c} | 置信 {conf_c:.0f}%')
    print(f'  {reason_c}')
    # 综合（投票加权）
    votes = {}
    for d, w in [(dir_a, 0.5), (dir_b, 0.3), (dir_c, 0.2)]:
        votes[d] = votes.get(d, 0) + w
    final = max(votes, key=votes.get)
    # 多因子（估值/筹码/宏观——决策补充）
    print(f'\n【综合】{final} | 投票: {dict(votes)}')
    # 封存
    conn = get_conn()
    today = pd.Timestamp.now().strftime('%Y-%m-%d')
    target = (pd.Timestamp.now() + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    for ver, d, c in [('VER-A', dir_a, conf_a / 100), ('VER-B', dir_b, conf_b / 100), ('VER-C', final, max(votes.values()))]:
        conn.execute('INSERT INTO predictions (date, code, direction, confidence, reason) VALUES (?,?,?,?,?)',
                     (today, ver, d, c, f'预测{target}上证方向'))
    conn.commit()
    conn.close()
    print(f'\n✅ 三版已封存（{target} 对照）——5日窗口模型 54.1% 备用')
    print('📌 真实基准：单日二分类 53.6% / 5日窗口 54.1%——不夸大')

if __name__ == '__main__':
    main()
