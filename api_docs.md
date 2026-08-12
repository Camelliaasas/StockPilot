# StockPilot 后端 API 接口文档（前端生成用）

> 服务地址: `http://127.0.0.1:5521`（本地 Flask——CORS 已开）
> 全部返回 JSON。深色金融看板主题（玻璃卡片/紫色光晕/发光按钮）。

## 核心接口

### 1. GET /api/boards — 涨跌榜
```json
{"up": [{"name": "股票名", "code": "600519", "pct": 3.21}], 
 "down": [{"name": "...", "pct": -2.1}], 
 "total": {"up_count": 3800, "down_count": 1400, "flat_count": 50}}
```
区块：沪深涨跌统计 + 涨幅榜/跌幅榜前 10。

### 2. GET /api/market — 市场总览
```json
{"indexes": [{"name": "上证指数", "value": 3456.78, "chg": 0.42}],
 "stats": {"up": 3800, "down": 1400, "limit_up": 45, "limit_down": 3}}
```
区块：三大指数 + 市场宽度。

### 3. GET /api/decision — 核心股决策卡
```json
[{"name": "贵州茅台", "code": "600519", "price": "1309.22", "chg": 0.1,
  "action": "卖出", "position": "0%",
  "val": "PE 20.35（12.4%分位）", "chip": "🟠 筹码趋集中（-5.0%）"}]
```
区块：6 只核心股——买卖信号 + 估值 + 筹码。action: 买入/持有/观望/卖出。

### 4. GET /api/trend — 分级预测
```json
{"big": [{"sector": "人工智能、数字经济", "impact": "利好", "strength": 4, "title": "..."}],
 "mid": [...], "small": [{"sector": "半导体", "score": 12}]}
```
区块：大事件（中期趋势）/小事件（短期情绪）。

### 5. GET /api/verify — 预测战绩
```json
{"accuracy": 34.9, "total": 43, "correct": 15,
 "backtest": {"samples": 54180, "acc": 54.0},
 "by_ver": [{"ver": "VER-A", "n": 13, "acc": 0.0}],
 "recent": [{"date": "2026-08-12", "code": "600519", "direction": "看多", "actual": "跌", "correct": false}]}
```
区块：历史回测 54,180 样本 54.0% 大字 + 实盘验证记录。

### 6. GET /api/predictions — 最新预测
```json
[{"date": "2026-08-12", "code": "VER-A", "direction": "看多", "confidence": 60, "reason": "..."}]
```

### 7. GET /api/predict_history — 预测历史时间线
```json
[{"date": "2026-08-11", "code": "600519", "direction": "看多", "confidence": 85, "actual": "跌", "correct": false}]
```
区块：预测时间线散点 + 准确率趋势。

### 8. GET /api/valuation?code=600519 — 估值
```json
{"pe": 20.35, "percentile": "12.4%", "name": "贵州茅台", "conclusion": "低估"}
```

### 9. GET /api/chips?code=600519 — 筹码
```json
{"signal": "🟠 筹码趋集中（-5.0%）", "holders": 160000, "conclusion": "主力吸筹"}
```

### 10. GET /api/kline?code=600519&period=daily — K线（period: daily/weekly/monthly）
```json
{"dates": ["2026-01-02"], "opens": [1300], "closes": [1310], "highs": [1320], "lows": [1290],
 "volumes": [30000], "ma5": [1305], "ma20": [1280], "boll_up": [...], "boll_mid": [...], "boll_low": [...],
 "kdj_k": [...], "kdj_d": [...], "kdj_j": [...]}
```
区块：K线图（蜡烛图+MA+BOLL+KDJ）+ 周期切换按钮。

### 11. GET /api/intraday?code=600519 — 分时
```json
{"times": ["09:30"], "prices": [1300], "avg": [1299.5]}
```

### 12. GET /api/index — 指数行情
```json
{"shanghai": 3456.78, "shenzhen": 10876.5, "chinext": 2256.3, "trend": "震荡"}
```

### 13. GET /api/sector_fund — 板块资金雷达
```json
{"hot": [{"name": "电子信息", "amt": 1800.4, "chg": 1.6}],
 "cold": [{"name": "有色金属", "amt": -4922.3, "chg": -1.2}]}
```
区块：资金流入（红）/流出（绿）进度条。

### 14. GET /api/portfolio — 组合分析
```json
{"annual_ret": 12.3, "vol": 25.4, "sharpe": 0.48, "avg_corr": 0.62, "max_weight": 0.4,
 "assets": [{"code": "600519", "name": "贵州茅台", "weight": 0.4, "ret": 8.2}]}
```

### 15. GET /api/positions — 持仓
```json
[{"code": "600519", "name": "贵州茅台", "shares": 100, "cost": 1500, "cur": 1309.22,
  "market_value": 130922, "pnl": -19078}]
```
POST /api/positions — 添加持仓 `{"code":"600519","shares":100,"cost":1500}`
DELETE /api/positions?code=600519 — 删除

### 16. GET /api/risk — 风险预警
```json
{"alerts": [{"level": "高", "msg": "持仓集中度过高（茅台占比 40%）"}],
 "score": 65}
```

### 17. GET /api/macro — 宏观环境
```json
{"cpi": 0.5, "pmi": 49.4, "m2": 18.9, "lpr": 3.0, "verdict": "偏冷"}
```

### 18. GET /api/macro_chart — 宏观趋势图
```json
{"cpi": [{"date": "2026-01", "value": 0.8}], "pmi": [...], "lpr": [...]}
```

### 19. GET /api/curve — 策略净值曲线
```json
[{"name": "贵州茅台", "dates": [...], "ma_strategy": [...], "buy_hold": [...]}]
```

### 20. GET /api/paper — 模拟盘
```json
[{"name": "贵州茅台", "strategies": [{"name": "MA均线", "total_return": 65.0}, {"name": "MACD", "total_return": 55.4}, {"name": "海龟", "total_return": 35.9}]}]
```

### 21. GET /api/backtest — 回测对比
```json
[{"strategy": "MA5/10", "win_rate": 45, "total_return": 32.5, "max_drawdown": 18.2}]
```

### 22. GET /api/messages — 消息中心
```json
[{"time": "2026-08-12 08:30", "title": "晨报", "content": "..."}]
```

### 23. POST /api/chat — AI 聊天
请求: `{"message": "分析茅台"}`
返回: `{"answer": "**判断**：短期观望..."}`
支持意图：个股分析/对比/大盘/选股/提醒/政策/推演/体检/预测/持仓/估值/筹码/回测/模拟盘/推荐/趋势分级/消息/自选股/风险/板块资金

### 24. GET /api/watchlist — 自选
```json
[{"code": "600519", "name": "贵州茅台"}]
```

## 设计规范（重要）
- 深色主题（背景 #0d1117 附近）——玻璃卡片（rgba 白 + backdrop-blur）
- 紫色/青色光晕（radial-gradient）——发光按钮
- 数字纯色（禁渐变文字——会糊）——-webkit-font-smoothing: antialiased
- 红涨绿跌（A 股习惯）——卡片 hover 微动效
- 响应式（桌面优先——1500px 宽三栏看板）
- 所有区块独立异步加载（fetch + try-catch + 加载/空态提示）
- 顶部：指数行情条 + 数据更新时间 + 免责声明小字
