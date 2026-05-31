# 成分股与龙头数据源

## 现状

产业链图谱的节点（石油、乙烯、塑料…）是经济结构知识，没有 A 股 API 能查询"石油→乙烯"的上下游关系。图谱骨架需人工维护。

但每个节点的 **龙头公司** 和 **成分股数量** 可以自动化。

## 可用数据

### 1. 同花顺概念板块成分股（已有）

日晷 `data/cache/raw_sectors.json`：465 个 THS 概念板块 → 成分股列表（倒排索引）。
`data/cache/stock_sector_map.json`：2011 只股票 → 所属板块（正排索引）。

数据链路：`q.10jqka.com.cn` 板块 AJAX → Cookie v_code（MiniRacer）→ HTML table → 倒排→正排。

### 2. akshare THS 板块函数（实测结论）

| 函数 | 能拿到什么 | 局限 |
|------|-----------|------|
| `stock_fund_flow_concept(symbol='即时')` | `公司家数`、`领涨股`（1只） | 只有 1 只领涨股，无 Top N，无权重 |
| `stock_board_industry_summary_ths()` | `领涨股`（1只）、`上涨家数`/`下跌家数` | 同上 |
| `stock_board_concept_info_ths(symbol)` | 理论上是成分股详情 | **pyarrow 版本兼容问题**，调用报 `IndexError` |
| `stock_board_concept_name_ths()` | 概念名→code 映射 | 纯元数据 |

**结论**：akshare THS 没有直接返回板块 Top N 龙头/权重的函数。必须自己按市值排。

### 3. 概念板块名称覆盖

27 个图谱节点对应的 THS 概念板块（不完全覆盖）：

| 图谱节点 | THS 概念板块 |
|----------|-------------|
| 石油 | （无直接对应。需用行业板块如"石油开采"？） |
| 天然气 | `天然气` (300358) |
| 煤炭 | `煤炭概念` (308716) |
| 乙烯/塑料/化纤/化肥/尿素 | `煤化工概念` (300084), `磷化工` (300098), `化肥` (301104) |
| 火电/新能源发电/电网 | `绿色电力` (308760) |
| 水泥 | `水泥概念` (307826) |
| 消费电子 | `消费电子概念` (308384) |
| 汽车制造 | `新能源汽车` (300008), `汽车电子` (301471) |

部分节点（石油、钢铁、有色金属、粮食、家电等）没有精确匹配的 THS 概念板块，需用行业板块或手动建立映射。

## 推荐方案：全市场基础信息表

不逐只调 mootdx，而是一次性批量拉全量，缓存到 SQLite：

```
mootdx stocks() → 全市场 4000+ 代码+名称
mootdx finance() → 总市值/流通市值
→ SQLite stock_basics(code, name, market_cap, float_cap)
```

查询龙头：
```sql
SELECT code, name FROM stock_basics
WHERE code IN ({板块成分股代码列表})
ORDER BY market_cap DESC LIMIT 3
```

2 次 mootdx 调用搞定所有板块的龙头查询。日晷 `_build_stock_brief()` 已有的 mootdx finance 逻辑可直接复用，只需改成批量模式。
