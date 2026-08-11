"""事件连锁推演引擎：多事件 → 传导链 → 股市影响（连锁反应分析）
规则知识库（不依赖 LLM——余额不足可用）"""
import sys, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

# 传导链知识库：事件 → 一级影响 → 二级影响 → 三级影响（股市）
CHAINS = [
    # 货币政策
    {'trigger': ['降息', '降准', '宽松', '放水', 'MLF', 'LPR下调'],
     'chain': ['货币政策宽松 → 市场流动性↑ → 资金成本↓',
               '→ 利好金融(银行息差承压但券商受益)、地产(融资成本↓)、成长股(折现率↓)',
               '→ 大盘偏多——尤其利好高估值成长板块'],
     'impact': '利好'},
    {'trigger': ['加息', '收紧', '缩表', 'LPR上调', '美联储加息'],
     'chain': ['货币政策收紧 → 流动性↓ → 资金成本↑',
               '→ 利空高估值成长股(折现率↑)、地产、债市',
               '→ 大盘承压——资金转向防御(红利/公用事业)'],
     'impact': '利空'},
    # 大宗商品
    {'trigger': ['油价上涨', '原油上涨', 'OPEC减产', '石油涨价'],
     'chain': ['原油价格↑ → 生产成本↑ → 通胀预期↑',
               '→ 利空航空/物流/化工下游(成本↑)、利好石油开采/油服',
               '→ 通胀↑ → 加息预期↑ → 股市整体承压'],
     'impact': '结构性（利好石油/利空航空）'},
    {'trigger': ['金价上涨', '黄金新高', '避险'],
     'chain': ['黄金↑ → 避险情绪↑ → 风险偏好↓',
               '→ 资金从股市流向避险资产',
               '→ 股市承压（尤其高风险板块）；利好黄金股'],
     'impact': '利空（风险偏好下降）'},
    # 地缘
    {'trigger': ['战争', '冲突', '制裁', '地缘', '军事'],
     'chain': ['地缘冲突 → 避险情绪↑ → 供应链风险↑',
               '→ 利好军工/黄金/原油；利空外贸/航空/消费',
               '→ 风险偏好↓ → 大盘承压（短线）'],
     'impact': '利空（短期避险——军工黄金受益）'},
    # 科技产业
    {'trigger': ['AI突破', '人工智能', '大模型', '芯片突破', '科技革命'],
     'chain': ['科技突破 → 产业革命预期↑ → 资本开支↑',
               '→ 利好AI/算力/半导体/软件——带动创业板/科创',
               '→ 产业升级 → 大盘偏多（结构性——科技领涨）'],
     'impact': '利好（科技成长结构性）'},
    # 政策
    {'trigger': ['国常会', '政策支持', '产业政策', '补贴', '扶持'],
     'chain': ['产业政策支持 → 行业景气预期↑ → 资金流入',
               '→ 利好受扶持行业（新能源/半导体/医药等——按政策方向）',
               '→ 政策市特征：大盘获支撑'],
     'impact': '利好（受扶持板块）'},
    # 贸易
    {'trigger': ['关税', '贸易战', '出口管制', '限制出口'],
     'chain': ['贸易摩擦 → 出口受限 → 外需预期↓',
               '→ 利空出口链(电子/纺织/机械)；利好国产替代',
               '→ 经济预期↓ → 大盘承压'],
     'impact': '利空（出口链——国产替代受益）'},
    # 消费
    {'trigger': ['消费刺激', '消费补贴', '以旧换新', '促消费'],
     'chain': ['消费刺激 → 内需预期↑ → 消费板块景气↑',
               '→ 利好消费(白酒/家电/汽车/零售)',
               '→ 内需拉动 → 大盘偏多'],
     'impact': '利好（消费板块）'},
]

def extract_events(limit=8):
    """从新闻库取最新事件（有 sector 分析的）——强度按级别默认"""
    conn = get_conn()
    rows = conn.execute("SELECT title, sector, impact, strength, level FROM news WHERE level != '' ORDER BY id DESC LIMIT 30").fetchall()
    conn.close()
    out = []
    for r in rows[:limit]:
        strength = r['strength'] if r['strength'] else {'大': 4, '中': 3, '小': 2}.get(r['level'], 2)
        out.append({'title': r['title'][:40], 'sector': r['sector'], 'impact': r['impact'],
                    'strength': strength, 'level': r['level']})
    return out

def analyze_chain(events=None):
    """多事件连锁推演：每个事件 → 传导链 → 叠加汇总"""
    if events is None:
        events = extract_events()
    if not events:
        return {'error': '暂无事件数据'}
    results = []
    total_score = 0
    for ev in events:
        title = ev['title']
        matched = None
        for chain in CHAINS:
            if any(t in title for t in chain['trigger']):
                matched = chain
                break
        if matched:
            s = ev.get('strength', 3)
            score = s if matched['impact'] in ('利好',) else -s
            if '结构性' in matched['impact']:
                score = s * 0.5 if '利好' in matched['chain'][-1] else -s * 0.5
            total_score += score
            results.append({'event': title, 'level': ev.get('level', '小'), 'strength': s,
                            'chain': matched['chain'], 'impact': matched['impact'], 'score': score})
        else:
            # 未匹配——用新闻自身的 sector/impact
            s = ev.get('strength', 2)
            score = s if ev.get('impact') == '利好' else (-s if ev.get('impact') == '利空' else 0)
            total_score += score
            results.append({'event': title, 'level': ev.get('level', '小'), 'strength': s,
                            'chain': [f'[{ev.get("sector", "其他")}板块事件] → {ev.get("impact", "中性")}(强度{s})'],
                            'impact': ev.get('impact', '中性'), 'score': score})
    # 汇总判断
    if total_score >= 5:
        verdict = '🟢 多方占优——多个利好事件共振——大盘偏多'
    elif total_score <= -5:
        verdict = '🔴 空方占优——多个利空事件叠加——大盘承压'
    elif total_score > 0:
        verdict = '🟡 偏多——利好略占优（事件影响有限）'
    elif total_score < 0:
        verdict = '🟠 偏空——利空略占优'
    else:
        verdict = '⚪ 多空平衡——事件互相抵消——震荡'
    return {'events': results, 'total_score': total_score, 'verdict': verdict}

def main():
    print('🔗 事件连锁推演（多事件 → 传导链 → 股市影响）')
    print('=' * 56)
    r = analyze_chain()
    if 'error' in r:
        print('❌', r['error'])
        return
    for ev in r['events']:
        icon = '🔴' if ev['score'] > 0 else ('🟢' if ev['score'] < 0 else '⚪')
        print(f"\n{icon} [{ev['level']}·强度{ev['strength']}] {ev['event']}")
        for step in ev['chain']:
            print(f"   {step}")
    print(f"\n{'=' * 56}")
    print(f"综合评分: {r['total_score']:+d}")
    print(f"🎯 最终判断: {r['verdict']}")

if __name__ == '__main__':
    main()
