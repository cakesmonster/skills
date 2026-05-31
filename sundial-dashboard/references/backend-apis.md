# 日晷后端 API 参考

## Eastmoney push2ex 涨停池

Base: `https://push2ex.eastmoney.com`
Params: `ut=7eea3edcaed734bea9cbfc24409ed989`, `dpt=wz.ztzt`, `date=YYYYMMDD`

| 端点 | 说明 | sort |
|------|------|------|
| `/getTopicZTPool` | 涨停池 | fbt:asc |
| `/getTopicQSPool` | 强势池 | zdp:desc |
| `/getTopicZBPool` | 炸板池 | fbt:asc |
| `/getTopicDTPool` | 跌停池 | fund:asc |
| `/getYesterdayZTPool` | 昨日涨停池 | zs:desc |

### 字段映射

| 原始字段 | 含义 | 归一化 |
|----------|------|--------|
| `c` | 代码 | code |
| `n` | 名称 | name |
| `p` | 现价 | price |
| `zdp` | 涨跌幅 | change_pct |
| `amount` | 成交额 | amount |
| `hs` | 换手率 | turnover |
| `hybk` | 行业板块 | sector |
| `lbc` | 连板数 | board_count |
| `fbt` | 首次封板时间 | first_time |
| `lbt` | 最后封板时间 | last_time |
| `zbc` | 炸板次数 | broken_count |
| `fund` | 封板资金 | seal_amount |

## Baostock

### 指数日线

```python
bs.login()
rs = bs.query_history_k_data_plus("sh.000001", "date,close,amount",
    start_date="2026-05-18", end_date="2026-05-22")
```

指数代码：`sh.000001`(上证), `sz.399001`(深成), `sz.399006`(创业板)

### 科创50

Baostock 不支持 000688，走 AkShare：

```python
import akshare as ak
df = ak.stock_zh_index_daily(symbol="sh000688")
```

### 个股日K

```python
rs = bs.query_history_k_data_plus("sh.600519",
    "date,code,open,high,low,close,volume,amount,turn,pctChg",
    start_date=start, end_date=end)
```

代码格式：`sh.600519` / `sz.000001`（需加前缀）

## THS 热榜

详见 `sina-batch-quote.md`。
