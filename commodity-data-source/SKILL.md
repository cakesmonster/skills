---
name: commodity-data-source
description: 大宗商品/原材料数据源——百川盈孚产业链（主力）+ 期货品种实时行情。用于日晷产业链图谱原材料节点定义与价格接入。数据唯一真相源：macro-industry.json。
version: 4.0.0
---

# 大宗商品原材料数据源

两个有实际接入的数据源：

| 数据源 | 作用 | 品种数 | 接入方式 |
|--------|------|:---:|------|
| 百川盈孚 baiinfo.cn | 产业链上下游链路关系（核心） | ~200垂直频道 | curl + API |
| 期货交易所 | 实时价格接入 | 63 | mootdx Quotes(market='future') |

**铁律**：禁止使用 mock 数据。数据源失败时返回空，不降级填充。

---

## 百川盈孚产业链 API（主力数据源）

百川盈孚是 A 股产业链数据最全平台：22 个产业频道、200 个垂直行业频道，每篇分析文包含完整的**原材料→中间体→产品**链路关系。

### 接入方式

```
PC站:   https://www.baiinfo.com
移动站: http://wap.baiinfo.cn  （注意：必须用 http，https 证书不覆盖 wap 子域名）
```

```bash
# 首页文章列表（免费，不需要 cookie，必须用 http）
curl -sL -A "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36" \
  "http://wap.baiinfo.cn/"

# 价格行情（需要登录，返回空则说明需要 cookie）
curl -sL -A "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36" \
  "http://wap.baiinfo.cn/price/getAllMarket?type=1"
```

### 百川首页分析文（免费直抓）

`http://wap.baiinfo.cn/` 是 SSR 页面，HTML 里直接嵌入 4 篇完整分析文，**不需要 cookie，不需要登录**。

**HTML 结构**：
```html
<p class="tab-title" data-v-xxx>   → 文章标题（含品种名）
<p class="tab-content" data-v-xxx> → 文章摘要正文（含完整链路描述）
<p class="tab-data" data-v-xxx>     → 发布日期
```

```python
import requests, re

HEADERS = {"User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36"}

def fetch_baiinfo_articles(url="http://wap.baiinfo.cn/", timeout=10) -> list[dict]:
    """抓取百川首页产业链分析文列表"""
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    html = r.text
    titles   = re.findall(r'<p class="tab-title" data-v-[^>]+>([^<]+)</p>', html)
    contents = re.findall(r'<p class="tab-content" data-v-[^>]+>(.*?)</p>', html, re.DOTALL)
    dates    = re.findall(r'<p class="tab-data" data-v-[^>]+>([^<]+)</p>', html)
    hrefs   = re.findall(r'<a href="(/viewpoint/\d+/\d+)"', html)
    articles = []
    for i, t in enumerate(titles):
        content_text = re.sub(r'<[^>]+>', '', contents[i]).strip() if i < len(contents) else ''
        articles.append({
            "title": t,
            "date": dates[i].strip() if i < len(dates) else '',
            "content": content_text,
            "url": f"http://wap.baiinfo.cn{hrefs[i]}" if i < len(hrefs) else ''
        })
    return articles
```

**已验证链路品种**：

| 品种 | newsId | 链路摘要 |
|------|--------|---------|
| PVC | 39658437 | 电石法（石灰石+焦炭）→电石→PVC；乙烯法（原油裂解）→PVC |
| 白刚玉 | 39668713 | 氧化铝+石墨电极→电熔白刚玉 |
| 吡虫啉 | 39668942 | 丙烯/丙烯醛→2-氯-5-氯甲基吡啶→咪唑烷→吡虫啉 |
| 金属汞 | 39663965 | 冶炼矿石→金属汞；炼金领域主导消费 |
| 石油树脂 | 39658680 | 石脑油裂解C5→C5石油树脂 |

### 9 大产业链产品目录（302 品种，已采集）

百川盈孚 `/industry-chain` 页面是 Nuxt SSR + 客户端渲染。

**采集脚本**：`/root/.hermes/data/baiinfo/collect_chains.js`（playwright-core 调用 9 个 tab，输出 JSON）

**9 大频道产品数**（原始）：

| 频道 | 品种数 |
|------|-------|
| 汽车原料辅料 | 53 |
| 造纸原辅料 | 77 |
| 医药原辅料 | 82 |
| 光伏行业相关 | 76 |
| 电池原辅料 | 41 |
| 钢铁原辅料 | 37 |
| 水处理原辅料 | 28 |
| 轮胎 | 20 |
| 饲料添加剂 | 12 |

**数据文件**：`/root/.hermes/data/baiinfo/industry_chains.json`（去重后 302 个品种，含 name + baiinfo ID）

### ⚠️ 登录墙限制（未解决）

| 页面 | 内容 | 状态 |
|------|------|:---:|
| `/viewpoint/{id}/{cid}` | 分析文正文 | ❌ 需登录 |
| `/product-detail/{name}/{id}` | 产品详情含完整链路 | ❌ 需登录 |

---

## 期货品种实时行情

```python
from mootdx.quotes import Quotes
# 中国期货全品种
client = Quotes(market='future')
df = client.security()
# 63 个标准合约品种，期货代码如 cu/al/ni/lc/si/pp/ma/...
# 实时价格
df = client.real(['cu2601', 'al2601'])
```

---

## 数据结构

原材料节点统一用 `⛏️原材料` 分组，写入 macro-industry.json：

```json
{
  "id": "氧化铝",
  "group": "⛏️原材料",
  "r": 17,
  "summary": "铝的氧化物，氧化铝厂炼铝用原料，上游是铝土矿（进口为主）。期货合约代码：al。",
  "futures_code": "al",
  "baiinfo_category": "有色金属"
}
```

---

## 数据接入工作流（已验证可行）

1. **全量写入节点**：品种 name + id 从百川行业链页面直接抓取，全部写入 macro-industry.json，不逐个审查
2. **批量建立链路**：基于工业产业链常识批量添加 links，不依赖数据源自带关系
3. **消除游离节点**：优先按组内 hub 节点连接；跨组用高频品种（如硫酸/原油/甲醇）搭桥；剩余孤立节点就近挂接相邻组。**禁止创建锚点/类别节点**

> ⚠️ 锚点节点（如精细化工/医药中间体/食品添加剂等）不是具体产品，其边会导致双向边泛滥。禁止在 macro-industry.json 中创建锚点/类别节点。

**关键原则**：节点 summary 由人工撰写（每条约 40-60 字，说明品种定义+产业链位置+主要应用），链路关系基于工业常识建立。

---

## 已知限制

- **登录墙**：品种完整链路正文需要登录态，当前无法自动抓取
- **客户端渲染**：9 大频道中只有第一个 tab（汽车，53 个品种）可用正则从 HTML 直接提取；其余 8 个 tab 必须用 Playwright 执行 JS 后提取