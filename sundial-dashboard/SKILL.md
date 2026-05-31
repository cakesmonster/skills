---
name: sundial-dashboard
description: 日晷 Sundial — A股市场数据看板（FastAPI SPA）。每日复盘、热榜、个股分析、策略回测、模拟账户。纯真实数据，零 mock 兜底。
version: 1.4.0
---

# 日晷 Sundial

## 架构

```\nFastAPI :8100 (0.0.0.0) → SPA 单页应用，分页按需加载\n  ├── /api/shared              meta + marketTape（启动时加载，~570 字节）\n  ├── /api/stock/brief/{code}  单只股票 PE/市值/换手/概念（hover card 按需）\n  ├── /api/page/daily-replay   每日复盘数据（~3KB）\n  ├── /api/page/stock-analysis 个股分析数据（~2KB）\n  ├── /api/page/strategy-backtest 策略回测数据（~0.6KB）\n  ├── /api/page/paper-account  模拟账户数据（~6KB）
  ├── /api/page/industry-chain 产业链图谱（JSON→D3 力导向图）
  ├── /api/industry/{id}       产业链数据（节点+边）\n  ├── /api/dashboard           旧版聚合端点（保留兼容，前端不再调用）\n  ├── /api/review              每日复盘（情绪+连板天梯）\n  ├── /api/hotrank             热榜（按 date+slot 查历史）\n  ├── /api/stock/{code}        个股 K 线 + 分时 + 动态队友 + 大单异动（mootdx）\n  ├── /api/backtest/*          策略回测（进程内直调引擎）\n  ├── /api/account             模拟账户（SQLite）\n  └── APScheduler              每小时整点采集热榜 + 每30秒大单采集（仅交易时段）\n```

**拆分原因**：旧版 `/api/dashboard` 一次返回全部 9 个模块（90KB），其中 `teammates` 独占 48KB。首屏加载卡死。

**拆分铁律：每个端点独立计算，互不牵连。** 不允许有任何形式的「先算全量再切一块返回」——那是假拆分。每个分页端点只 import 和调用自己需要的函数，不经过 `build_dashboard()`。

**stockMeta 按需加载**：72 只股票的 PE/市值/换手率（13KB）不再预加载到 `/api/shared`。改为 hover card 首次悬停时调 `/api/stock/brief/{code}`（~200 字节），查完缓存到 `state.data.stockMeta`。`_build_stock_brief()` 函数用 mootdx（行情+财务）+ Baostock（PE/换手率）+ sector_map（概念）实时构建。

**各端点独立实现**（无共享缓存）：

| 端点 | 只算 | 耗时 |
|------|------|------|
| `/api/shared` | meta(写死) + mootdx 4指数 | ~2s |
| `/api/page/daily-replay` | compute_sentiment + compute_ladder + compute_yesterday_perf | ~6s |
| `/api/page/stock-analysis` | `_build_stock_analysis` | ~2s |
| `/api/page/strategy-backtest` | `_build_strategy_backtest` | ~0.1s |
| `/api/page/paper-account` | `_build_paper_account`（纯SQLite） | ~0.1s |

**teammates (48KB) 不再被任何页面预计算**。队友数据只在 `/api/stock/{code}` 被调用时实时算一只。`_cached_build()` 和全局 TTL 缓存已删除。

**陷阱 — 假拆分（cosmetic split）**：创建分页端点时容易写出这种代码：
```python
# ❌ 假拆分：端点 URL 不同但内部都调同一个全量函数
@app.get("/api/page/daily-replay")
async def f():
    full = await build_dashboard()  # 算了完整 90KB
    return {"dailyReplay": full["dailyReplay"]}  # 实际上只返回 3KB

@app.get("/api/page/paper-account")
async def g():
    full = await build_dashboard()  # 又算了完整 90KB
    return {"paperAccount": full["paperAccount"]}  # 实际上只返回 6KB
```
点模拟账户也要等 sentiment+ladder+teams 全部算完——拆分形同虚设。正确做法是每个端点只 import 和调用自己需要的子函数，不共享全局缓存。

**前端加载流**：
- `bootstrap()` → `loadShared()` → `/api/shared`（~570 字节）
- 每次 `renderPage(pageId)` → `loadPageData(pageId)` → `/api/page/{pageId}`
- 悬停 stock chip → `renderHoverCard()`（async）→ `/api/stock/brief/{code}` → 缓存到 `state.data.stockMeta`
- hot-list 已有独立 `/api/hotrank` 端点，不走分页 API

### `/api/stock/brief/{code}` — stockMeta 按需查询

hover card 显示单只股票的总市值/流通市值/PE/换手率/概念。由 `dashboard.py:_build_stock_brief()` 实现：

- **行情**：mootdx `client.quotes()` → price, last_close → 自算 changePct = (price - last_close) / last_close × 100
- **市值**：mootdx `client.finance()` → 总股本/流通股本 × price / 1e8 → marketCap/floatCap（亿）
- **PE/换手率**：Baostock `query_history_k_data_plus(peTTM, turn)`，往回找 3 个交易日
- **概念**：`stock_sector_map.json` 本地缓存

**⚠️ mootdx `quotes` 字段名陷阱**：mootdx `quotes()` 返回的 DataFrame **没有 `name` 和 `changePct` 列**。列名是 `code`, `price`, `last_close`, `open`, `high`, `low`, `servertime`, `vol`, `amount` 等。name 需要从 DOM stock chip 取（`.stock-name` textContent），changePct 需要手动计算。

**前端缓存**：`renderHoverCard` 改为 `async`，首次查询后写入 `state.data.stockMeta[code]`，后续同只股票不再请求。name 从 DOM 参数 `domName` 注入到 API 响应中。

项目路径：`/root/.hermes/projects/sundial/`
数据路径：`src/data/sundial.db`
systemd：`sundial.service`（开机自启，MemoryMax=600M）

## 数据源

| 数据 | API | 字段 |
|------|-----|------|
| 涨停/跌停/炸板/强势/昨涨停 | Eastmoney push2ex | `getTopicZTPool` 等 |
| 三大指数（上证/深成/创业板）| Baostock | `query_history_k_data_plus` |
| 科创50 | AkShare | `stock_zh_index_daily` |
| 热榜排名 + 概念 + 涨跌幅 | **同花顺 `dq.10jqka.com.cn`** | `rise_and_fall` 字段直接含涨跌幅，APScheduler 每小时采集 |
| 个股日K | **通达信 mootdx** | `get_daily(code)` — 与回测同源 |
| 分时图（个股） | **通达信 mootdx 1分钟K线** | `client.bars(frequency=7)` — 240根 |
| 找队友 | **通达信 mootdx 1分钟K线** | 双路径：热榜池预计算 + 单票动态 `/api/stock/{code}` 返回 `teammates` |
| 大单异动 | **通达信 mootdx 逐笔成交 → SQLite** | `client.transaction()` → 筛选 ≥1000万 → `big_order_snapshot` 表 |
| 策略回测数据 | mootdx → Parquet 缓存 | `sundial/data/cache/` |

参考文件：`references/backend-apis.md`（API 端点 + 字段映射）。

## 铁律

### 🚫 零 mock 兜底

**任何字段都不能用假数据填充。** 如果数据源（API、SQLite、Baostock）返回空，就返回空数组/空对象，不生成假值。前端遇到空值自行处理空白状态。

这是用户反复强调的最高优先级规则。mock 数据会污染判断——你不知道页面上哪个是真哪个是假。

### 🚫 不依赖 hermes cron

热榜定时采集、计划生成等周期性任务，**用程序内部调度器**（APScheduler BackgroundScheduler），不依赖 hermes cron。这样项目可以脱离 hermes 环境独立部署。

```python
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(collect_fn, "cron", minute=0)
scheduler.start()
```

### 🚫 TDD：先写测试，再写代码

**RED → GREEN → REFACTOR 顺序不可颠倒。** 不能先改业务代码再补测试。

- ✅ 正确：先写 `test_api_stock_includes_big_orders` → 跑 → FAIL → 再实现 `_fetch_big_orders`
- ❌ 错误：先写 `_fetch_big_orders` + 改 `api_stock` + 改前端，然后补测试

这是用户明确纠正过的。先上车后补票不算 TDD。

### 🚫 改设计前先查 docs/ 下设计文档

项目 `docs/` 下有 `DESIGN.md`、`DESIGN-sundial.md`、`PLAN-sundial.md`。涉及数据存储结构、API 设计、技术选型的决策时，**必须先查这些文档**找原文依据，不能凭经验推断。

例如：PLAN-sundial.md 第四部分规定 SQLite 只有 2 张表（`hot_rank_snapshot` + `account_snapshot`），数据存储原则是「不存历史，实时计算」。加新表前必须对照设计文档确认是否与原始设计冲突。

### 🚫 SPA 前端数据 shape 精确对齐

- hotList period keys 格式：`"HH:MM"`（带冒号），如 `"15:00"`
- defaultPeriod 必须是实时当前时段（`now.strftime("%H:00")`），不是写死的 `"15:00"`
- `dailyReplay` 需要 `emotionMetrics`（数组）、`yesterdayLimitUpPerformance`（含 bars/avg）、`ladder`（含 level/stocks）
- `stockAnalysis` 需要 `dayKFallback: []` 和 `intradayFallback: []` 字段（即使为空）

## 热榜页面设计（2026-05-27 重构）

**旧设计（已废弃）**：三个固定按钮 `11:30 | 15:00 | 21:00`，`_build_hot_list` 的 `slot_map` 四个 key 全指向同一份 API 数据 `items`，点哪个都一样。

**新设计**：`[📅 日期选择器] [小时▼ 00-23] :00 [当前]`

- 前端独立调用 `/api/hotrank?date=YYYY-MM-DD&slot=HH:00`，不依赖 dashboard bundle
- 每小时下拉切换时实时 fetch
- 空时段显示「该时段暂无热榜数据」
- 「当前」按钮一键跳回此刻

### `/api/hotrank` — 双源切换（2026-05-27）

```python
@app.get("/api/hotrank")
async def api_hotrank(date: str = Query(None), slot: str = Query("15:00")):
    d = date or _today_iso()
    now = datetime.now()
    current_hour = now.strftime("%H:00")

    # 当前时段 → 实时拉取 THS API（查 SQLite 最多滞后 59 分钟）
    if d == _today_iso() and slot == current_hour:
        try:
            items = await fetch_hot_rank()       # THS API 实时
            if items:
                return {"date": d, "slot": slot, "items": items, "source": "live"}
        except Exception:
            pass                                  # API 失败回退 SQLite

    # 历史时段 → SQLite
    return {"date": d, "slot": slot, "items": get_hot_rank(d, slot), "source": "db"}
```

| 条件 | 来源 | 延迟 |
|------|------|------|
| `date == today && slot == current_hour` | THS API `fetch_hot_rank()` | 实时 |
| 历史日期或历史小时 | SQLite `get_hot_rank()` | N/A |
| THS API 异常 | 自动回退 SQLite | 同上 |

**`get_hot_rank()` 格式兼容**：SQLite 中 slot 格式不一致（APScheduler 某些时段写入 `"12:00"`，`_build_hot_list` 写入 `"1200"`）。`get_hot_rank()` 和 `_query_hot_rank_slot()` 均已加入双格式 fallback（先尝试精确匹配 → 冒号格式 → 无冒号格式）。

### 后端：`_build_hot_list` 时段逻辑

当前时段用 API 实时数据，固定时段从 SQLite 查历史：

```python
slot_map = {current_slot: items}  # 当前时段：API 实时
for slot in ["12:00", "15:00", "21:00"]:
    if slot not in slot_map:
        slot_items = _query_hot_rank_slot(iso, slot)
        if not slot_items:
            # 跨日回退：凌晨查昨日
            slot_items = _query_hot_rank_slot(yesterday, slot)
        slot_map[slot] = slot_items
```

### `_query_hot_rank_slot(date, slot)` — 兼容双格式

SQLite 中 slot 存储格式不一致（`"12:00"` vs `"1200"`），查询时尝试两种格式。

### `get_hot_rank(date, slot)` — db.py 同样兼容双格式

`/api/hotrank` 端点调用 `get_hot_rank()`，也已加入双格式 fallback。

## 个股分析动态查询

前端切换股票代码时：
- **K线**：如果 `stockAnalysis.dayK[code]` 不存在，调 `/api/stock/{code}` 拉取，存入 `state.data.stockAnalysis.dayK[code]`
- **队友**：如果 `teammates[code]` 不存在（非热榜票），`renderTeammates` 异步 fetch `/api/stock/{code}`，取 `d.teammates` 渲染并缓存到 `state.data.teammates[code]`
- **大单**：`renderStock` 中 dayK 未命中或 `blockTrades[code]` 缺失时，fetch `/api/stock/{code}` 取 `d.bigOrders`，缓存到 `stockPage.blockTrades[code]`，渲染 `#block-trade-body`

`/api/stock/{code}` 返回 `{code, klines, intraday, teammates, bigOrders}`。

### 模拟账户 — 双源合并 + 盘中同步 + 成交记录（2026-05-27）

**数据源**: 同花顺 API + monitor state.json 合并。

- **APScheduler**: 盘中每 30 分钟同步（`minute=0,30, hour=9-14, mon-fri`）+ 盘后 15:05 收尾。
- **`sync_to_db()`**: 合并 THS `fetch_positions()` + monitor `state.json` 当日买入，写入 `account_snapshot`。
- **`trade_record` 表**: monitor 每次买卖自动写入（`_log_trade()`），含 date/time/code/name/direction/price/quantity/amount/reason。
- **`_build_paper_account()`**: 读取 `account_snapshot`（指标+持仓）+ `trade_record`（成交记录），构建 `assetCurve`/`pnlTimeline`/`flowTimeline`/`positions`/`trades`。

**SQLite 表**:
| 表 | 用途 | 关键字段 |
|------|------|------|
| `account_snapshot` | 账户快照 | date, total_asset, available_cash, position_value, daily_pnl, holdings(JSON) |
| `trade_record` | 成交记录 | date, time, code, name, direction, price, quantity, amount, reason |
| `big_order_snapshot` | 大单异动 | date, code, time, price, vol, amount, side, buyorsell |

**已知限制**: THS 持仓 API (`/pt_web_qry_stock`) 盘中可能返回空或延迟。`sync_to_db()` 会回退到 monitor state.json 补当日买入，但价格用成本价（非实时）。

### 日期格式归一化（重要陷阱）

`trade_record` 表存 `20260528`（无分隔符），`account_snapshot` 表存 `2026-05-28`（带短横线）。`_build_paper_account()` 在比对当天成交时（`t["date"] == d`）会因格式不一致返回空。

**修复**: `_build_paper_account()` 在构建 `all_trades` 时统一归一化为 `YYYY-MM-DD` 格式：

```python
if len(raw_date) == 8 and '-' not in raw_date:
    normalized = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
```

### 买卖配对交易记录（`_build_trade_pairs`）

FIFO 配对买入→卖出，输出每笔完整交易记录。`_build_paper_account` 返回 `{"byDate": {...}, "tradePairs": [...]}`。

单条记录结构：
```json
{"code", "name", "buyDate", "buyTime", "buyPrice", "buyQty",
 "sellDate", "sellTime", "sellPrice", "sellQty", "pnl", "pnlPct"}
```
- 已平仓: sell* 字段完整，pnl 有值
- 未平仓: sellDate/sellTime/sellPrice/sellQty/pnl/pnlPct 均为 null

**持仓无买入记录补全**：买入发生在 `trade_record` 表创建前的股票，从最新 `account_snapshot.holdings` 中取 cost/shares，补一条 `buyDate="—"` 的「持仓中」条目。配对时名字优先取买入记录的 name（卖出记录可能把 code 填在 name 列）。

### 前端"今日成交"方向列字段名

后端返回 `t.direction`（`"买入"/"卖出"`），不是 `t.side`。JS 中需用 `t.direction === '买入'`。

## 策略回测

回测引擎以**库**形式集成在 sundial 进程内，不再独立启动服务。

- 端点：`POST /api/backtest/run`，body: `{strategy, stock_count, window_days, runs_per_stock}`
- 引擎：`quant_backtester.engine.backtest.run_one`
- 策略发现：`quant_backtester.strategies.registry.discover_strategies`
- 数据：mootdx → Parquet 缓存（`sundial/data/cache/*.parquet`）
- A股规则：T+1、涨跌停、手续费万三、滑点 0.1%、每手 100 股

## 常见问题

### 个股分析切换代码无数据

前端 `renderStock` 函数需要异步 fetch。已 patch `app.js`，但仍需确认 `dayKFallback: []` 字段存在于 API 返回中。

### 模每日复盘白屏

检查 API 返回的 `dailyReplay.byDate[date]` 下是否包含正确的 `emotionMetrics` 和 `ladder` 结构。常见原因：日期格式不匹配（API 返回 `20260525` 但前端期望 `2026-05-25`）。

### 热榜涨跌幅全是 0

THS API 不含 change_pct。检查 `ths_api.py` 中是否调用了 Sina 批量行情补查。

## 找队友（teammates）— 概念分组 + 1分钟K线滑动窗口互相关

**双路径设计**（2026-05-26）：

| 路径 | 触发 | 算法 | 数据流 |
|------|------|------|--------|
| 热榜池预计算 | `/api/dashboard` 构建时 | `_build_teammates` — 概念分组→组内两两互相关→连通分量 | hot_list + ladder → teammates dict |
| 单票动态计算 | `/api/stock/{code}` 查非热榜票时 | `_find_stock_teammates` — 目标 vs 热榜池逐对互相关 | THS API 实时拉池 → pool → 滑动窗口 r |

**不再使用 `teammatesFallback`**——不存在"兜底空数据"的概念。热榜票走预计算缓存，非热榜票走动态实时。

### 预计算路径（`_build_teammates`）

**算法来源**：board_monitor `signals/team.py` `compute_teammates()`，已内联到 `dashboard.py`。

**流程**：
1. `_collect_hotlist_pool` 收集热榜+ladder所有代码 + 概念标签
2. 按概念分组 → 每个概念组内两两计算
3. 通达信 mootdx `client.bars(frequency=7, offset=240)` 拉 1分钟K线（240根=4小时）
4. 方差过滤：`float(closes.std()) < 1e-6` 的跳过
5. `_sliding_corr` 分钟涨跌幅 → 滑动窗口 Pearson r（窗口=15min，步长=3，阈值≥0.6，含 `np.isnan(r)` 守卫）
6. 连通分量分组 → 输出 `{code: {byConcept: [...], byTrend: [...]}}`

### 动态计算路径（`_find_stock_teammates`）

**触发热榜内票**时：取目标概念 → 池内交集筛选同概念/同板块候选 → 互相关 → top 5。
**非热榜票**时：无法取概念（mootdx finance industry 返回数字代码，无法匹配中文概念名）→ 回退全池对比 → top 5。

1. `_build_dashboard_hot_list()` 实时拉 THS API → 得 hot_list
2. `_collect_hotlist_pool(hot_list)` → 池
3. `_find_stock_teammates(code, pool)` → 筛选同概念候选 → 拉1分钟线 → `_sliding_corr`
4. 返回 `[{code, name, changePct, corr, concepts}]` 按 corr 降序，top 5
5. 前端 `renderTeammates` 收到后缓存到 `state.data.teammates[code]`

### 核心可复用函数

| 函数 | 用途 |
|------|------|
| `_sliding_corr(a, b)` | 滑动窗口 Pearson r，返回最佳绝对值 |
| `_collect_hotlist_pool(hot_list, ladder)` | 收集热榜+连板股票池 `{code: {name, changePct, concepts}}` |
| `_find_stock_teammates(code, pool)` | 同概念/同板块筛选 → 互相关 → top 5 |

### 关键常量

`TEAM_WINDOW=15`, `TEAM_R_THRESHOLD=0.6`

### 找队友 UX（2026-05-26 更新）

- **热榜「找队友」按钮**：点击后跳转到个股分析页（`stock-analysis`），右边「找队友」面板自动加载分时叠加图和队友列表。**不再使用弹窗**。
- **已移除**：`teammate-modal` DOM（`index.html`）、`openTeammateModal` / `closeTeammateModal` / `buildTeammateList` 函数、相关事件监听。全部死代码已清理。

### 测试方法论 — 验证队友功能

**不要用热榜票测试队友**——热榜票有预计算缓存，测不出动态路径和概念匹配的真实性。

✅ **正确测试**：
1. 选一个**不在热榜上**的股票（如 `601857` 中国石油）
2. 调 `/api/stock/601857` 拿到 `teammates` 列表
3. 抽查队友的 `concepts` 字段，确认与目标股**共享至少一个概念/行业**
4. 用 `stock_sector_map.json` 验证概念一致性

❌ **错误测试**：只测热榜票 → 走预计算缓存 → 看不到概念补全效果 → 误判功能正常。

```bash
# 端到端验证示例
CODE=601857
curl -s "http://localhost:8100/api/stock/$CODE" | python3 -c "
import json, sys
d = json.load(sys.stdin)
mates = d.get('teammates', [])
print(f'{d[\"code\"]} -> {len(mates)} teammates')
for m in mates[:3]:
    print(f'  {m[\"code\"]} {m[\"name\"]} corr={m[\"corr\"]:.2f} concepts={m.get(\"concepts\", [])}')
"
```

### 陷阱

- 🚫 **盘后1分钟线方差为0**：收盘后部分股票返回平坦数据，必须方差过滤
- 🚫 **NaN 守卫**：`np.corrcoef` 遇零方差窗口返回 NaN（不抛异常），`abs(NaN) >= 0.6` 永远 False，需 `if np.isnan(r): continue`
- 🚫 **offfset=240 必须**：盘后/周末 offset=60 只拉到重复收盘价（方差=0），必须 offset=240 覆盖全天交易
- 🚫 **同事名陷阱**：算法文件在 `board_monitor/src/board_monitor/signals/team.py`，不是 `teams.py`
- 🚫 **不要用 fallback**：用户明确要求非热榜票实时计算，不要用空数组兜底
- 🚫 **同概念/同板块过滤**：`_find_stock_teammates` 必须用 `target_concepts & candidate_concepts` 交集筛选候选股，不能遍历全池所有股票。用户要求「同板块或者同概念下的所有股和当前的股进行对比，找到最相似的5个」。只有热榜内票才有概念；非热榜票回退全池对比
- 🚫 **mootdx industry 不可用**：`client.finance()` 的 `industry` 字段返回数字代码（如 `37`），无法匹配 THS 的中文概念名。不要试图用它来取非热榜票的概念
- 🚫 **SQLite slot 格式不一致**：`_build_hot_list` 写入用 `datetime.now().strftime("%H%M")`（如 `"1200"`），但 APScheduler 某些时段写入 `"HH:MM"` 格式（如 `"12:00"`）。`get_hot_rank()` 和 `_query_hot_rank_slot()` 必须同时尝试两种格式，否则历史查询返回空

## 大单异动 — mootdx 逐笔成交 ≥1000万（SQLite 持久化）

**双路径设计**（2026-05-26）：

| 路径 | 触发 | 数据流 |
|------|------|--------|
| 采集 | APScheduler 每30秒（仅交易时段 Mon-Fri 09:30-15:00） | `_collect_big_orders_job()` → 拉热榜池 → `_collect_big_orders_from_pool(pool)` → mootdx `client.transaction(offset=200)` → 筛选 ≥1000万 → `save_big_orders()` → SQLite `big_order_snapshot` |
| 查询 | `/api/stock/{code}` 被调用时 | `_fetch_big_orders(code)` → `get_big_orders(today, code)` → SQLite 读 → 返回 `[{time, side, volume, amount, price}]` |

**mootdx 逐笔是滚动缓冲区**（仅保留最近 200-500 条），必须高频采集才能覆盖全天。30秒间隔 + offset=200 确保不遗漏。

**SQLite 表**：`big_order_snapshot(date, code, time, price, vol, amount, side, buyorsell)` PK=`(date, code, time, vol, price)`，`INSERT OR IGNORE` 去重。

**前端**：`renderStock` → fetch `/api/stock/{code}` → 缓存 `data.bigOrders → stockPage.blockTrades[code]` → 渲染 `#block-trade-body` 表格。

**HTML**：`stock-analysis.html` 第 54-75 行，表头「时间 | 方向 | 数量(手) | 金额 | 成交价」。

### 陷阱

- 🚫 **mootdx 盘后无逐笔数据**：`client.transaction()` 只在交易时段返回数据，盘后为空。**这就是为什么要存 SQLite**
- 🚫 **采集间隔不能太长**：mootdx 缓冲区小，5 分钟采集会丢失大量数据。30秒 + offset=200 是实测合理的
- 🚫 **金额计算**：`vol × price × 100`，vol 单位是**手**（mootdx 协议），×100 转股数，×price 转金额
- 🚫 **`blockTradesFallback` 是死数据**：`dashboard.py` 返回 `blockTrades: {}` 和 `blockTradesFallback: []`，从未被填充。前端不走这个路径

## 前端样式

CSS 文件：`static/css/app.css`，HTML 入口：`index.html`。

### 设计方向

浅色系 modern-minimal，基于 Pulse Intel 设计系统，配色用 oklch 色彩空间。
完整规范见 [`references/design-system.md`](references/design-system.md)。

### 颜色规则（铁律）

**红涨绿跌仅用于小角标**（涨跌幅、trend 箭头）。大卡片指标、横条、进度条全部走设计系统色。

| 场景 | 正确色 | 来源 |
|------|--------|------|
| `.trend.up` / `.price-up` / `.pct.up` | 红 `--positive` | 中国A股惯例 |
| `.trend.down` / `.price-down` / `.pct.down` | 绿 `--negative` | 中国A股惯例 |
| `.tag.group`（涨停标签）| 红色背景+文字 | 市场专用 |
| `.limit-up-row`（涨停行）| 浅红底 | 市场专用 |
| `.kpi-value`（KPI 大数字）| 中性 `--fg` | 设计系统 |
| `.rt-fill.up`（情绪横条涨）| accent 蓝 → violet 渐变 | 设计系统 |
| `.rt-fill.down`（情绪横条跌）| cyan → teal 渐变 | 设计系统 |
| `.progress-fill.loss` | warn → amber 渐变 | 设计系统 |
| `.metric .value`（回测指标）| accent-strong / violet / warn | 设计系统 |
| `.pulse`（交易状态点）| success 绿 | 设计系统 |

### 字体

只用系统字体栈，**不依赖 Google Fonts**。

### 圆角/阴影体系

见 `references/design-system.md` 中的 `--r-*` 和 `--sh-*` 变量表。

### 注意事项

- **所有 HTML class 名保持不变**：`app.js` 动态生成大量 class，CSS 通过 class 选择器覆盖
- **Topbar 毛玻璃**：`oklch(100% 0 0 / 0.82)` + `backdrop-filter`
- **Card 背景**：纯白，页面背景浅灰

## 常见前端问题

### stockMeta 移除后 `byCode()` 抛出 TypeError（不是返回 null）

拆分 API 后 `stockMeta` 不再预加载到 `/api/shared`。`byCode(code)` 行 `return state.data.stockMeta[code] || null` **直接抛 `TypeError: Cannot read properties of undefined (reading 'XXXXXX')`**，因为 `state.data.stockMeta` 本身是 `undefined`——不是返回 null，是炸了。

**修复**：加空保护 `&&`：
```js
function byCode(code) {
    return (state.data.stockMeta && state.data.stockMeta[code]) || null;
}
```

**影响**：`renderStockInfoCard(code)` 开头 `byCode(code)` 返回 null → `if (!stock || !infoRoot) return;` → 卡片不渲染。

**兜底方案**：`renderStockInfoCard` 在 `byCode` 为 null 时从 DOM stock chip 取 name（`.querySelector('[data-stock-code="CODE"] .stock-name')`），市值/PE/concepts 填 0 或空数组。不阻塞页面其余部分（K 线图、队友面板、大单表格仍正常渲染）。

```js
if (!stock) {
    const nameEl = document.querySelector(`[data-stock-code="${code}"] .stock-name`);
    stock = {
        code, name: nameEl ? nameEl.textContent.trim() : code,
        marketCap: 0, floatCap: 0, pe: 0, turnover: 0, concepts: [],
    };
}
```

此兜底仅用于个股分析页（`renderStockInfoCard`）。hover card（`renderHoverCard`）走 `/api/stock/brief/{code}` 按需查询，不受影响。

### 浏览器 console 调试 state

`state` 在 IIFE 内，console 不可直接访问。在 `const state = {` 后加 `window.__state = state;` 即可从 console 访问 `window.__state.data`。调试完记得删除此行并 bump 版本号。

```js
const state = { ... };
window.__state = state;  // DEBUG
```

### 页面刷新报"初始化失败"

常见原因：`app.js` 中有 DOM 查询引用已删除的 HTML 元素。

- **检查 `resize` 事件处理**：当删除页面中的 canvas/元素后，务必同时清理 `resize` handler 中对该元素的引用。即使有 `if (el)` 守卫，引用链上的属性访问（如 `snap.assetCurve`）可能先于判空执行。
- **检查 `el` 对象初始化**：`const el = { updatedAt: document.getElementById('updated-at'), ... }` 在 IIFE 顶部执行，如果对应元素在 `index.html` 中缺失会导致后续 `el.updatedAt.textContent` 抛空指针。

### 前端缓存旧版 CSS/JS

部署后用户看到旧样式，是因为浏览器缓存了 `/static/css/app.css` 和 `/static/js/app.js`。

**修复**: 在 `index.html` 中给静态资源加版本号 query：`href="/static/css/app.css?v=2"`、`src="/static/js/app.js?v=2"`。每次部署改版号。

### 模拟账户页只显示 KPI、表格空白

检查 `_build_paper_account()` 中日期格式是否归一化（见上文"日期格式归一化"陷阱）、以及前端 `tradeBody` 使用的是 `t.direction` 还是 `t.side`。

### 持仓结构环形图显示 0.0%

**根因**: `app.js` 中的 `parseMvToNum()` 只处理字符串类型（`typeof text !== 'string'` 时直接返回 0）。后端 `_build_paper_account()` 的 `mv` 字段现为 `round(shares * price / 10000, 2)` 生成的是数字而非字符串。

**修复**: 在 `parseMvToNum` 开头加 `if (typeof text === 'number') return text;`。

### 可用资金与实际不符（卖出后现金不涨）

**根因**: `sync_to_db()` 的 `available_cash` 从同花顺 `fetch_account()` API 的 `zjye` 字段取值。同花顺 API 不知道 board_monitor 的买卖交易，所以卖出后现金余额不更新。

**修复**: 在 `ths_trade_api.py` 的 `sync_to_db()` 中，不依赖 THS 的现金数据，改用 `total_asset - position_value` 推算：
```python
total_asset = acct.get("total_asset", 0)
available_cash = total_asset - pos_value
```

### 页面刷新时先闪"每日复盘"再跳转到目标 Tab

**根因**: `app.js` 中 `state.activePage` 初始化为硬编码 `'daily-replay'`。`bootstrap()` 流程：`bindGlobalEvents()` → `await loadData()`（慢）→ `getInitialPage()`（读 hash）→ `renderPage(page)`。在 `loadData()` 等待期间，骨架屏按 `activePage` 显示每日复盘。

**修复**: `activePage` 初始化时从 `location.hash` 读取：
```js
activePage: (() => {
  const h = location.hash.replace('#', '').trim();
  const known = ['daily-replay','hot-list','stock-analysis','strategy-backtest','paper-account','industry-chain'];
  return known.includes(h) ? h : 'daily-replay';
})(),
```

### 产业链 Tab（industry-chain）

基于同花顺概念/行业板块构建的全产业超级图谱。61 个节点、81 条关联、9 大分组。

**规则**：只有同花顺有独立板块的产业环节才能成为节点。节点名 = THS 板块名。详情见 `industry-chain-platform` skill。

**数据文件**：`data/industry_data/macro-industry.json` + `index.json`

**前端**：`static/pages/industry-chain.html` + `app.js` 中 `renderIndustryChain()`（D3 力导向图 + 涟漪效应 + 搜索）

### 连板天梯 — 非连续性涨停模式（`zttj` 字段）

Eastmoney push2ex 涨停池 API 返回 `zttj` 对象（`{days: N, ct: M}`），表示「N 天内 M 次涨停」。非连续性模式（如 `days=11, ct=7` → "11天7板"）此前被完全忽略，只看 `lbc`（连板数）。

**数据抽取**（`eastmoney_api.py` `_normalize`）：
```python
zb = item.get("zttj", {}) or {}
row.update({
    "total_days": zb.get("days", item.get("lbc", 1)),
    "total_boards": zb.get("ct", item.get("lbc", 1)),
    ...
})
```

**分组**（`ladder.py` `compute_ladder`）：按实际模式 label 分组（`f"{td}连板" if td == tb else f"{td}天{tb}板"`），不再按纯数字分组。

**前端**: `_build_daily_replay` 的 `level` 字段现为完整 label 字符串（如 `"4连板"` / `"11天7板"`），JS 直接显示 `${group.level}`，不再硬拼"连板"后缀。

### 交易时段显示「已收盘」/ 状态文案错误

前端 `app.js` 的 `tradingStatus()` 函数根据当前小时判断交易状态。注意 A 股交易时段为 **09:30-11:30 和 13:00-15:00**，判断条件应覆盖全部时段：

```js
// 正确：覆盖全部交易时段
if (h >= 9 && h < 11 || (h === 11 && m <= 30)) → 早盘
### patch 工具可能破坏 Python docstring

当用 `patch` 工具替换文件头部内容时，如果 `old_string` 以 `"""` 开头且 target 恰好是 docstring，可能产生 `"""\n"""content..."""` 的畸形结果——第一行直接闭合 docstring，第二行变成含 em dash 的裸字符串字面量，触发 `SyntaxError: invalid character '—' (U+2014)`。

**检查**：patch 后 `read_file(limit=5)` 确认 docstring 完整；`python3 -c "import ast; ast.parse(...)"` 验证语法。

### 删除/重构功能：四层同步 + 版本号 + grep 验证

Sundial SPA 的功能分散在 HTML/JS/Python/CSS 四层。删除任何功能时必须四层同步处理，完毕后 `grep -rn "功能名" src/` 确认零残留，然后 bump CSS/JS 版本号（`?v=N`）并重启。

### 删除 HTML 元素后 resize 事件报错

当从 HTML 模板中删除 canvas/DOM 元素时，必须同时清理 `app.js` 中 `window.addEventListener('resize', ...)` 里对该元素的引用。即使有 `if (el)` 守卫，链式属性访问（如 `snap.assetCurve`）可能在判空前就执行了。

### API 拆分后 `state.data.teammates` 为 undefined

拆分 API 后，`state.data.teammates` 不再在 `loadShared()` 中预加载（48KB 太大了）。前端代码中任何对 `state.data.teammates[code]` 的直接访问都会抛 `TypeError: Cannot read properties of undefined`。

**修复**：
```js
// 访问前加守卫
let source = (state.data.teammates && state.data.teammates[code]) || null;

// 写入前初始化
if (!state.data.teammates) state.data.teammates = {};
state.data.teammates[code] = source;
```

### 页面模板中 `<script>` 标签不会执行（innerHTML 注入）

SPA 的 `renderPage` 通过 `el.pageHost.innerHTML = template` 加载页面模板。**`innerHTML` 不会执行模板中的 `<script>` 标签**，这是浏览器安全特性。如果页面依赖外部库（如 D3.js），必须用 `document.createElement('script')` 动态注入。

**复现**：在 `pages/xxx.html` 中写 `<script src="https://d3js.org/d3.v7.min.js"></script>` → 页面切换后 `typeof d3 === 'undefined'`。

**正确做法**（在 renderer 函数中）：
```js
function renderXxxPage() {
  if (typeof d3 === 'undefined') {
    const script = document.createElement('script');
    script.src = 'https://d3js.org/d3.v7.min.js';
    script.onload = () => doRender();
    script.onerror = () => showError('D3 加载失败');
    document.head.appendChild(script);
    return;
  }
  doRender();

  function doRender() {
    // 实际渲染逻辑
  }
}
```

此模式适用于产业链图谱（D3）、Charts.js 等任何需要外部库的页面。

## 产业链 tab（2026-05-30 集成，已完整迁移）

日晷第六个 tab。原 `/root/projects/industry-chain/` 项目的全部数据、代码、样式已迁移到日晷内部，原项目已删除。

**当前状态**：仅保留全产业超级图谱（macro-industry），55节点/92边/12个行业组。进来直接就是 D3 力导向图，无列表页。

**架构**：
- 数据：`sundial/data/industry_data/macro-industry.json`（项目内自包含）
- API：`/api/industry/macro-industry` 返回节点+边
- 前端：`renderIndustryChain()` 动态加载 D3 CDN，硬编码加载 macro-industry
- 样式：**日晷浅色主题**（白底 + `var(--surface)` + `var(--fg)` + 连线 `#d1d5db`），与日晷其他页面完全统一

**铁律 — 外部项目集成到日晷**：
1. **完整迁移**，不桥接。数据、代码、样式全部复制到日晷项目内，不读外部路径
2. **删除原项目**，不留冗余端口或目录
3. **样式必须统一**为日晷设计系统（浅色系 modern-minimal，不用暗色/独立主题）
4. 如果只需要其中一部分功能（如只要全产业不要单行业），删掉不需要的，不保留冗余

**添加新 tab 的标准步骤**（四层同步）：
1. `index.html` — 加 `<button class="nav-tab" data-page="xxx">` 
2. `app.js` — 加 `PAGE_FILES['xxx']`、`PAGE_API['xxx']`、`known` hash 列表（含 `'industry-chain'`）、`runPageRenderer` 映射、renderer 函数
3. `static/pages/xxx.html` — 页面模板（⚠️ 模板中 `<script>` 标签不执行，需 renderer 中动态注入）
4. `static/css/app.css` — 样式（**必须用日晷设计系统变量**，不另起暗色主题）
5. `main.py` — 如有数据需要，加分页 API 端点
6. bump CSS/JS 版本号（`?v=N`），重启服务

### patch 工具可能破坏 Python docstring

当用 `patch` 工具替换文件头部内容时，如果 `old_string` 以 `"""` 开头且 target 恰好是 docstring，可能产生 `"""\n"""仪表盘...""` 的畸形结果——第一行直接闭合 docstring，第二行变成含 em dash 的裸字符串字面量，触发 `SyntaxError: invalid character '—' (U+2014)`。

**检查**：patch 后 `read_file(limit=5)` 确认 docstring 完整；`python3 -c "import ast; ast.parse(...)"` 验证语法。

## 故障排查

### 快速健康检查

```bash
curl http://127.0.0.1:8100/health          # → {"status":"ok","name":"sundial"}
systemctl restart sundial                   # 重启服务
journalctl -u sundial -f                    # 查看日志
```

### Port 8100 被占用

```bash
ss -tlnp | grep 8100                        # 查看谁在监听
kill -9 <pid>                               # 杀掉占用进程
systemctl restart sundial
```

### Uvicorn 缓存旧代码

uvicorn 缓存模块，旧进程可能还在跑旧代码：

```bash
pkill -9 -f "uvicorn sundial" 2>/dev/null
find /root/.hermes/projects/sundial -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
cd /root/.hermes/projects/sundial && python3 -B -m uvicorn sundial.main:app --host 127.0.0.1 --port 8100
```

### `main.py` 中用 `datetime.now()` 要补 import

`main.py` 的 import 行是 `from datetime import date, timedelta`，不含 `datetime` 类。如果代码里用了 `datetime.now()`，必须改成 `from datetime import date, datetime, timedelta`。

### SQLite 测试数据污染

单元测试可能写入真实数据库。排查和清理：

```bash
sqlite3 /root/.hermes/projects/sundial/src/data/sundial.db "SELECT date, slot, COUNT(*) FROM hot_rank_snapshot GROUP BY date, slot"
sqlite3 /root/.hermes/projects/sundial/src/data/sundial.db "DELETE FROM hot_rank_snapshot"  # 必要时清空
```

### 机器资源限制

服务器 1.8G RAM，无 swap。Sundial + LSP 进程同时运行可能导致 IO 抖动。崩溃后先 `free -h`，<200MB 时先杀 LSP。Sundial 自身 ~130MB RSS。

### 搜文件名用通配符，不要猜精确名

board_monitor 队友算法在 `signals/team.py`（不是 `teams.py`）。用 `find ... -name "*team*"` 或 `grep -rl "关键词" --include="*.py"`。

### 数据源网络状态速查

| 域名 | 用途 | 状态 |
|------|------|:---:|
| `push2ex.eastmoney.com` | 涨停池/炸板池/跌停池 | ✅ |
| `push2.eastmoney.com` | 实时行情/板块 | ❌ HTTP 000 |
| `eq.10jqka.com.cn` | THS 热榜 | ✅ |
| `q.10jqka.com.cn` | THS 板块成分股 AJAX | ✅ |
| `d.10jqka.com.cn` | THS 实时行情 | ✅ |
| `hq.sinajs.cn` | Sina 补涨跌幅 | ✅ |
| `vip.stock.finance.sina.com.cn` | Sina 板块分类 | ✅ |
| Baostock | 指数K线/PE/换手率 | ✅ |
| mootdx | 通达信K线/分时/财务 | ✅ |

## 测试

```bash
cd ~/.hermes/projects/sundial && python -m pytest -q  # 246 passed
```

### temp_db fixture 隔离 — monkeypatch 两处

**症状**: SQLite 测试间数据泄漏（test A 写入的数据被 test B 读到）。

**根因**: `db.py` 顶部 `from .config import DB_PATH` 在模块 import 时绑定到 `config.DB_PATH` 的**值**。fixture 中 `cfg.DB_PATH = db_path` 只改了 `config` 模块，但 `db.DB_PATH` 仍指向旧路径 → 所有测试共享同一个真实 DB 文件。

**修复**: fixture 必须 monkeypatch **两个**模块：
```python
monkeypatch.setattr(cfg, "DB_PATH", db_path)
monkeypatch.setattr("sundial.db.DB_PATH", db_path, raising=False)
```
