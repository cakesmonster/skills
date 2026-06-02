---
name: taoguba-scraper
description: 淘股吧 (tgb.cn) 帖子抓取工具,使用 curl + AJAX API,规避 WAF。反爬要点:Chrome UA + JSESSIONID cookie + Referer + X-Requested-With。【免加载】仅在被 cron/agent 显式调用时加载。
---

# 淘股吧 (tgb.cn) 数据抓取

A股短线情绪社区(独立游资/打板选手聚集地),首页「今日推荐」等栏目可作为市场情绪侧的数据源。

**本 skill 只提供抓取工具,不做选股判断。情绪分析由调用方(cron/agent)自行完成。**

## 反爬要点

- **Browserbase 云浏览器 IP 被 WAF 拦截**(返回 502)。必须用 curl + 桌面 Chrome UA
- **Cookie**:`JSESSIONID`(30 分钟过期) + `acw_tc`(阿里云 WAF token),首次请求自动下发
- **User-Agent**:`Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0`
- **Referer**:`https://www.tgb.cn/`
- **X-Requested-With**:`XMLHttpRequest`(AJAX 标识)

## 脚本:scrape_today_recommend.py

路径:`scripts/scrape_today_recommend.py`

### 用法

```bash
# 默认:抓 2 页(每页 15 条) + 每篇正文(最多 3000 字)
python3 scripts/scrape_today_recommend.py

# 调整参数
python3 scripts/scrape_today_recommend.py --pages 3
python3 scripts/scrape_today_recommend.py --no-content      # 只取列表,不抓正文
python3 scripts/scrape_today_recommend.py --output out.json
python3 scripts/scrape_today_recommend.py --max-len 5000
```

### 行为

1. 首次请求 `https://www.tgb.cn/` 获取 cookie
2. 顺序请求 `https://www.tgb.cn/newIndex/getNowRecommend?pageNo=N` 抓列表
3. 按 `newTopicID` 去重
4. 逐篇请求 `https://www.tgb.cn/a/{newTopicID}` 抓正文,提取 `<div class="article-text">` 内容
5. 输出 JSON 数组到 stdout 或 `--output` 指定文件

### 失败处理

- Cookie 获取失败 → exit 1
- 任意单页失败 → 跳过继续,stderr 打 `[ERROR]`
- `status=false` → 跳过该页,打 `[WARN]`
- 连续失败由调用方决定是否重试(本脚本不内置 retry)

### 副作用

- Cookie 写到 `/tmp/tgb_cookies.txt`(每次覆盖)
- 数据目录 `/root/.hermes/data/taoguba/` 不需要预先建(本脚本不写这里,只是 DATA_DIR 常量)

## API 端点速查

| 栏目 | API 端点 | 分页 |
|------|----------|------|
| 综合推荐 | `/newIndex/getZh?pageNo=X` | 是 |
| 网友精选 | `/newIndex/getFriendsFeatured?pageNo=X&topID=Y` | 是 |
| **今日推荐** | `/newIndex/getNowRecommend?pageNo=X` | 是(perPageNum=15) |
| 淘县院子 | `/newIndex/getTxyz` | 否 |
| 淘县神评 | `/newIndex/getReplySP?pageNo=X&type=ALL` | 是 |
| 研股 | `/newIndex/getStockResearch?pageNo=X&type=1&sxType=1` | 是 |

返回格式 + 详细端点文档见 [`references/taoguba-api.md`](references/taoguba-api.md)。

## 与其他 skill 的边界

- **a-stock-data-apis**:本 skill 拆分自它,数据抓取相关的反爬/端点知识都在这里。a-stock-data-apis 现在不再包含 taoguba 资源
- **market-sentiment**:情绪判断框架在那个 skill,本 skill 只提供帖子数据
- **短线选股战法 skill**:选股不读淘股吧(用户原则:「选股唯一数据源是同花顺热榜」)

## 已知坑

1. **WAF 502 频发**:阿里云 WAF 对数据中心 IP 敏感,首次请求如果直接命中 `/newIndex/getNowRecommend` 不带 cookie 会 503。先 GET 一次首页再请求接口
2. **正文 div 嵌套**:`<div class="article-text">` 内部有大量 `<a>` 和样式 `<div>`,不能用第一个 `</div>` 截断。要找 `article-reward` 或 `article-topic` 作为结束标记
3. **API 偶发重复**:同 `newTopicID` 偶尔出现 2 次,脚本已用 set 去重
4. **Cookie 过期**:抓 30 分钟后 JSESSIONID 失效,长时间任务中途需重新获取 cookie
5. **请求频率**:正文抓取 sleep 0.3s,列表抓取 sleep 0.5s。脚本里已内置,不要去掉
