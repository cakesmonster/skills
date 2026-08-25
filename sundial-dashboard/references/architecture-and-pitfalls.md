# Quant System Architecture & Pitfalls

> Originally `trading/quant-system-roadmap` skill (consolidated here 2026-07).
> Covers both `board_monitor` (盘中, :8099, systemd) and `sundial` (盘后, :8100, SPA).
> Loaded when discussing architecture, planning features, or tracking known pitfalls.

---

# 量化交易系统 Roadmap

## 架构

```
盘中: board_monitor (FastAPI + systemd)  ← mootdx Level-2 + 逐笔成交
      项目路径: ~/.hermes/board_monitor/  (独立 Python 项目, src layout + pyproject.toml)
      源码: src/board_monitor/ → config / models / market / trading_api / state / monitor + signals/*
      部署: deploy/systemd/ → *.service + *.timer
      启停: systemd timer → curl POST /start (09:25) /stop (15:00)
      查询: GET http://127.0.0.1:8099/status  → 持仓/候选/信号
      日志: ~/.hermes/data/trading/logs/YYYYMMDD/monitor.log
      pip install -e . 安装开发模式, uvicorn board_monitor.main:app 启动
      
盘后: Agent 选股 → active_plan.json + 计划.md
      sell_check.py     (晚间热度排名确认)               ← 同花顺 API
      pnl_stats.py      (盈亏查询)                      ← 同花顺 API
数据: mootdx (行情+Level-2+逐笔), ths-hot-rank (热榜), xhs-scraper (内容采集)
交易: 同花顺模拟炒股 API (凭证在 .env)
```

## 项目快速参考

| 项目 | 端口 | 路径 | systemd |
|------|------|------|---------|
| board_monitor | 8099 | ~/.hermes/board_monitor/ | board-monitor.service + start/stop timer |
| 日晷 Sundial | 8100 | ~/.hermes/projects/sundial/ | sundial.service |
| quant-backtester | 已合并入日晷 | sundial/src/quant_backtester/ | 不再独立运行 |

## 日晷 Sundial 当前状态 (v0.5.2)

- FastAPI **:8100** 绑定 **127.0.0.1**，systemd: `sundial.service`
- SPA 单页应用：每日复盘 / 热榜 / 个股分析 / 策略回测 / 模拟账户
- `/api/dashboard` 聚合端点，`?code=` 支持动态个股查询
- **零 mock 兜底** — 所有数据来自真实 API，数据源失败返回空
- 数据源：push2ex（涨停/跌停/炸板）、Baostock（指数）、THS（热榜排名+概念）→ Sina 批量补涨跌幅、通达信 mootdx（个股K线/1分钟分时图/队友互相关，与回测同源）
- **找队友**：通达信1分钟K线 + 滑动窗口 Pearson r 互相关（算法来自 `board_monitor signals/team.py`）
- **内部 APScheduler** 每小时整点采集热榜 + 盘中每10分钟同步账户 + 盘后 15:05 同步，**不依赖 hermes cron**
- 前端 JS：搜索栏（点击/Ctrl+K → 输入 6 位代码回车 → 跳转个股分析）
- 右上角头像「道」字
- 模拟账户：直连同花顺 API（`trade.10jqka.com.cn:8088`，凭证在 .env），封装在 `ths_trade_api.py`，启动自动同步

---

## 陷阱清单（按发现时间倒序）

### 🚫 队友算法在 board_monitor，不在 sundial

**症状**：sundial 的 `_build_teammates` 最初用 `hash(code) % 30 / 100` 做人造 corr 值，`byTrend` 只是 changePct 差值排序。

**根因**：真正的队友算法（滑动窗口 Pearson r 互相关，1分钟K线）在 board_monitor `signals/team.py` `compute_teammates()` 中。文件叫 `signals/team.py`，不是 `teams.py`。

**修复（2026-05-25）**：
1. sundial `_build_teammates` 重写：通达信 `client.bars(frequency=7)` 拉1分钟K线 → 分钟涨跌幅 → 滑动窗口 Pearson r（窗口15，阈值0.6）→ 连通分量分组
2. 注意：board_monitor `signals/team.py` 是**盘中实时**用的；sundial `_build_teammates` 是**盘后/历史**用的，共用同一算法
3. `byConcept` 和 `byTrend` 用同一套真实 r 值（板块+走势合一），不再区分
4. **前端 JS 必须同步改**：`app.js` 中 `renderTeammates` 删「概念板块」列（后端不再返回 `concepts`）、`openTeammateModal` 合并「同概念」+「走势相似」双栏为单列表、删 `teammate-tabs` 切换逻辑和 `, 'concept'` mode 参数。改完必须 `node --check`
5. **搜文件名陷阱**：搜 `*team*` 而非 `teams.py` — 文件叫 `signals/team.py`，搜 `teams.py` 永远找不到

### 🚫 分时图必须用通达信 mootdx 1分钟，不用新浪 5分钟

**症状**：新浪 5分钟 K 线接口 `money.finance.sina.com.cn` 经常不通（从部分服务器返回空或超时），且 5分钟精度低。通达信 mootdx 有更精确的 1分钟 K 线且同一个数据源已在日K/回测中使用。

**修复（2026-05-25）**：`_fetch_intraday` 从新浪 5分钟换为 mootdx `client.bars(frequency=7, offset=240)`。频率=7表示1分钟线，240根覆盖全天交易。

### 🚫 盘后 1分钟K线方差为0 → 队友匹配失败

**症状**：盘后找队友结果极少（如30只热榜仅9只有队友），热门票如华天科技(002185)无队友。

**根因**：
1. **关键根因**：`client.bars(frequency=7, offset=60)` 在盘后只拉到最近60分钟数据——全是重复收盘价（方差=0）。改为 `offset=240`（覆盖全天4小时交易时段）即可拉到真实交易数据。
2. 辅助措施：拉完 1分钟K线后加方差检查 `if float(closes.std()) < 1e-6: continue`，零方差的票直接跳过。

**验证**：改完后队友从9只恢复到20只，corr 值从0.6提升到0.97。

**注意**：分时图 `/api/stock/{code}` 用的也是 `offset=240`，队友和分时图必须保持一致。不要换数据源（用户明确要求用1分钟线，不要 5分钟/新浪）。

### 🚫 策略回测 metrics 格式必须用数组

**症状**：`Cannot read properties of undefined (reading 'length')`；刷新策略清空下拉框。

**根因**：
1. 前端 `backtest.results[selectedId] || backtest.results.default` — `results: {}` 时 undefined
2. API 返回 `metrics: {sharpe, maxDrawdown, ...}` 对象，前端 `.map()` 遍历对象报错
3. 刷新策略调 `/api/backtest/strategies` 返回 `{strategies: [...], details: {name: {description}}}`，前端把数组字符串当对象用

**修复**：
1. 前端兜底 `|| {curves:[],metrics:[],details:[]}`，去掉自动触发
2. **metrics 必须数组** `[{label, value, suffix}]`，前后端统一
3. 刷新策略用 `data.details[name].description`

### 🚫 模拟账户字段名必须精确对齐前端期望

**症状**：账户页面空白但 API 返回了真实数据。

**根因**：后端 `holdings{shares/price/pnl}` vs 前端 `positions{qty/last/mv/pnlAmt}`。

**修复**：`_build_paper_account` 输出 `positions` 含 `qty/last/mv/pnlAmt/pnlPct`。`assetCurve` value 单位「万」，`mv`=shares×price/10000，`pnlAmt`=pnl/10000。

### 🚫 前端 JS 动画让真实数据看起来像 mock

**症状**：marketTape 数据在动、封单条自动变化，用户以为数据是假的。

**修复**：`runMarketTapePulse()` 和 `pulseRealtimeBars()` 改为空函数。

### 🚫 JS patch 后必须 `node --check` 验证

**症状**：页面全白但 API/HTML 正常。

**根因**：字符串替换误伤函数声明（`.catch()` 错加到 function 声明上）。

**铁律**：每次改 `app.js` 后跑 `node --check <file>`。

### 🚫 THS 热榜不含涨跌幅 — Sina 批量补查

**症状**：热榜 changePct 全为 0。

**修复**：`fetch_hot_rank` 拉完热榜 → Sina `hq.sinajs.cn/list=` 批量查（50只/批，GBK 编码），fields[2]=昨收 fields[3]=现价。

### 🚫 热榜 is_limit_up 以实际涨跌幅为准

**症状**：京能电力 0.49% 显示涨停绿色背景。

**修复**：`is_limit_up` = 实际 changePct ≥ 9.5%（主板）/ ≥ 19.5%（科创创业），不用 THS 标签。

### 🚫 个股 K 线统一走通达信 mootdx

**修复**：`/api/stock/{code}` → `get_daily(code).tail(30)`，与回测同源。

### 🚫 SPA 前端数据 shape 必须精确对齐

**症状**：SPA 页面报 `Cannot read properties of undefined`。

**修复流程**：读 data.json → grep JS 找 `state.data.xxx` → 后端 key 逐层匹配。

### 🚫 FastAPI Query 对象直接 asyncio.run 调用会出错

**症状**：`asyncio.run(api_func(date='2026-06-22', top_n=5))` 时，函数内 `top_n` 是 `Query(5)` 实例不是 `5`，传给 SQLite 时报 `sqlite3.ProgrammingError: Error binding parameter 3: type 'Query' is not supported`。`slice indices must be integers` 也是同类（`rising[:top_n]` 把 Query 对象当切片下标）。

**根因**：FastAPI 的 `Query(default, ...)` 默认值在请求路径里会被 Pydantic 解包成字面量，但**直接 import 后调用（不走 HTTP）**时参数仍是 Query 对象。

**修复**（sundial `main.py` 端点统一套路）：

```python
n = int(top_n) if not isinstance(top_n, int) else top_n
slot = slot if isinstance(slot, str) or slot is None else slot.default
```

或者用 `from fastapi import Query; def endpoint(top_n: int = 5)` —— 但这样失去 Query 文档能力。

**适用范围**：sundial 所有 `/api/...` 端点参数都加这个 guard，**特别是**会被 `asyncio.run` 在测试/脚本里直接调的端点。

### 🚫 禁止 subprocess / shell 调用

tirith 安全层拦截 `subprocess.run` / `os.system`。用 `urllib.request` 直连 API。

### 🚫 持仓票不在候选名单时卖出监控遗漏

`self._codes` 必须 = targets ∪ holdings。

### 🚫 check_lead_signal 需检查 leader 在 tick_logs 中

加 guard `if leader not in tick_logs: return False, ""`。

### 🚫 架构合并后必须更新 README + pyproject.toml

**症状**：合并 quant-backtester 到 sundial 后，READEME 仍描述独立 quant-backtester 服务架构、端口 8200。pyproject.toml 缺 mootdx/numpy/scipy/apscheduler 等依赖。

**修复清单**：
1. README 标题 → 日晷 Sundial，架构图 → 合并单进程 8100，删独立回测服务描述
2. pyproject.toml 补 `mootdx` `numpy` `scipy` `apscheduler`
3. deploy service `host` → `127.0.0.1`（与 config.py 一致）
4. `.env` 文档化同花顺模拟账户凭证

---

_2026-05-25: v2.10 — 盘后 offset=60 陷阱 + 前端 JS 同步步骤 + 搜文件名陷阱。_