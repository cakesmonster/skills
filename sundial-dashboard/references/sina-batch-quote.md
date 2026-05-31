# Sina 批量行情接口 — THS 热榜涨跌幅补查

## 问题

同花顺热榜 API (`eq.10jqka.com.cn/open/api/hot_list/v1/hot_stock/a/hour/data.txt`)
返回的字段中**不含涨跌幅**。需要在获取热榜后，批量补查。

## 方案

新浪行情接口 `hq.sinajs.cn/list=` 支持一次查最多约 50 只股票。

## 请求

```
GET http://hq.sinajs.cn/list=sh600519,sz000001,sh600030,sz002594
Referer: https://finance.sina.com.cn
```

## 响应格式（GBK 编码）

```
var hq_str_sh600519="贵州茅台,1310.95,1311.00,1290.20,1311.91,1290.12,..."
var hq_str_sz000001="平安银行,10.70,10.70,10.68,10.73,..."
```

## 字段顺序

| 索引 | 含义 | 示例 |
|------|------|------|
| 0 | 名称 | 贵州茅台 |
| 1 | 今开 | 1310.95 |
| 2 | 昨收 | 1311.00 |
| 3 | 当前价 | 1290.20 |
| 4 | 最高 | 1311.91 |
| 5 | 最低 | 1290.12 |

涨跌幅 = (当前价 - 昨收) / 昨收 × 100

## 完整实现（ths_api.py）

```python
import re, httpx

SINA_URL = "http://hq.sinajs.cn/list="

async def _batch_fetch_change_pct(codes: list[str]) -> dict[str, float]:
    """新浪批量行情 → {code: change_pct}"""
    # 代码 → 新浪格式
    def to_sina(c):
        return f"sh{c}" if c.startswith(("6","5")) else f"sz{c}"

    sina_codes = [to_sina(c) for c in codes]
    result = {}

    # 分批，每批最多 50
    for i in range(0, len(sina_codes), 50):
        batch = sina_codes[i:i+50]
        url = SINA_URL + ",".join(batch)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers={"Referer": "https://finance.sina.com.cn"})
                r.encoding = "gbk"
                text = r.text
        except Exception:
            continue

        for line in text.split("\n"):
            m = re.match(r'var hq_str_(s[hz]\d+)="(.+)"', line.strip())
            if not m:
                continue
            sina_code = m.group(1)
            fields = m.group(2).split(",")
            if len(fields) < 4:
                continue
            try:
                prev_close = float(fields[2])
                cur_price = float(fields[3])
                pct = round((cur_price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0.0
            except (ValueError, IndexError):
                pct = 0.0
            result[sina_code[2:]] = pct

    return result
```

## 注意事项

- **非交易时间**返回的是上一交易日收盘数据，涨跌幅可能为 0 是正常的
- **单次最多约 50 只**，超过必须分批
- **GBK 编码**必须设 `r.encoding = "gbk"`，否则中文名称乱码
- 代码格式：6xxxx/5xxxx → `sh`，0xxxx/3xxxx → `sz`
- 不需要 API Key，纯 HTTP GET
