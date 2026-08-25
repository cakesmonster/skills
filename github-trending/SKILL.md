---
name: github-trending
description: 抓取 GitHub Trending 日/周/月热门项目，输出 Markdown。浏览器 SSR HTML 解析（Cron 首选路径）。
version: 2.6.0
---

# github-trending — 获取 GitHub 热门项目

抓取 GitHub Trending 页面（日榜/周榜/月榜），输出中文 Markdown 简报。

## Cron 定时任务 — 方法优先级

| 优先级 | 方法 | 说明 |
|--------|------|------|
| 1 | 浏览器 → Trending 页面 | ✅ **首选**。SSR HTML，含增量星数，三榜均可。但 CDP 超时频率上升 |
| 2 | 浏览器 → Search API | ✅ **可靠回退**（2026-07-16 验证：Trending 全路径超时时唯一可用路径）。无增量星数；需过滤垃圾 repo |
| 3 | execute_code | ❌ Cron 下阻断 |
| 4 | terminal | ❌ tirith 拦截 |

## 使用方法

### 方式一：浏览器 Trending 页面（Cron 推荐 ⭐）

**注意**：全局 Trending（`?since=daily`，无语言筛选）偶尔 CDP 超时，**重试通常成功**。语言特定页面（如 `/trending/python?since=daily`）可能更稳定但也可能同步超时（2026-07-16 实测：全局+python 页面双双超时）。**全路径超时时直接回退方式二（Search API）**，不要反复重试。

```python
# 1. browser_navigate(url="https://github.com/trending?since=daily")
#    如超时 → 重试一次 → 仍超时 → 直接回退 Search API（不要试语言特定页面）
# 2. browser_console 执行 JS（已验证三榜正确提取）：
"""
JSON.stringify(Array.from(document.querySelectorAll('article.Box-row')).slice(0,15).map(a => {
    const h2 = a.querySelector('h2 a');
    const name = h2 ? h2.getAttribute('href').replace(/^\//, '') : '';
    const desc = a.querySelector('p')?.textContent.trim() || '';
    const lang = a.querySelector('[itemprop="programmingLanguage"]');
    const language = lang ? lang.textContent.trim() : '';
    const starsEl = a.querySelector('a[href*="/stargazers"]');
    const stars = starsEl ? starsEl.textContent.trim().replace(/,/g, '') : '';
    const allText = a.textContent;
    const m = allText.match(/([\\d,]+) stars? (today|this week|this month)/);
    return {name, desc: desc.substring(0,200), language, stars,
        stars_delta: m ? m[1].replace(/,/g, '') : ''};
}))
"""
# 3. 用返回的 JSON 格式化 Markdown
```

**JS 提取关键点**：使用 `a.textContent` + 简化正则 `([\\d,]+) stars? (today|this week|this month)`。**不要**用 `\\s+` 转义（在 `browser_console` 多层转义中失效）或 `Array.from(...).find(...)` 子元素遍历（只匹配 "today"）。`.slice(0,15)` + `.substring(0,200)` 防截断。

### 方式二：浏览器 Search API（可靠回退 ✅）

**2026-07-17 更新**：Search API 请求**必须顺序执行**（一次一个），不可并行 `browser_navigate`。`browser_console` 只在最后导航的页面上下文中执行——并行调用时前面的页面数据会丢失。

```python
# ⚠️ 必须逐个请求，不能并行！每次 browser_navigate 后紧跟 browser_console 提取
# 日榜：过去 2 天
browser_navigate("https://api.github.com/search/repositories?q=created:%3E2026-07-14&sort=stars&order=desc&per_page=50")
# → browser_console 提取
# 周榜：过去 7 天
browser_navigate("https://api.github.com/search/repositories?q=created:%3E2026-07-09&sort=stars&order=desc&per_page=50")
# → browser_console 提取
# 月榜：过去 30 天
browser_navigate("https://api.github.com/search/repositories?q=created:%3E2026-06-16&sort=stars&order=desc&per_page=50")
# → browser_console 提取
```

**提取 JS**（三榜通用，返回 JSON）：
```js
JSON.stringify(JSON.parse(document.body.textContent).items.slice(0, 50).map(r => ({
    name: r.full_name,
    desc: (r.description || '').substring(0, 200),
    language: r.language || '',
    stars: r.stargazers_count,
    forks: r.forks_count,
    url: r.html_url,
    created: r.created_at,
    topics: (r.topics || []).slice(0, 5)
})))
```

**限制**：无增量星数（stars_delta），按累计星数排序（非增速排名）。**已知**：`browser_navigate` 到 `api.github.com` 可能返回空 `<body>`（2026-07-15 实测），此时无法获取数据，需等待下次 cron 重试。

### Search API 垃圾 repo 过滤

Search API 返回的数据**任何一天都可能被垃圾仓库污染**（不仅仅是周末）。典型特征：
- 星数完全相同且偏低（如全部 28⭐）
- 描述含 "aimbot / wallhack / ESP / cheat / hack / undetected" 等游戏外挂关键词
- 仓库名为 `*-Script-2026`、`*-Aimbot-*`、`*-Hack-*` 等模式
- fork 数为 0，账号名含随机后缀

**2026-07-17 新增检测模式**（周榜实测）：
- 空描述 + 异常 fork/star 比（fork > star 且 fork > 1000）→ 典型 spam farm（如 x4gKing 系列）
- 描述含 "sniper / bot / bundler / arbitrage" 且 fork 数异常 → 加密诈骗 bot
- 标签含 "cheating-roblox / copy-game" 等游戏作弊标签 → 游戏作弊工具

**过滤策略**：三榜均取前 50 条后手动过滤，保留前 10-15 个真实项目。周榜/月榜同样需要过滤，不要假设"垃圾率低"。

## 输出格式（Cron 推送）

中文 Markdown 简报结构：
1. 标题 + 时间 + 来源说明（注明使用的方法路径和限制）
2. 三榜分开展示（今日/本周/本月），各一个表格
3. **每个项目配 `📝` 一行简介**（硬性要求，不含糊）
4. 每个榜单后 3-5 条亮点解读
5. 末尾跨榜趋势观察表（按主题维度归纳）

## 故障排除

关键修复（持续更新）：

1. **Trending 页面 CDP 超时 → Search API 回退**（2026-07-16 新增）：全局 Trending 超时 → 重试仍超时 → 语言特定页面也超时 → **直接回退 Search API**。不要再试第三种语言页面，浪费时间。
2. **Search API 空 body**：`api.github.com` 返回 `<body></body>` → 本次 cron 无法获取数据，等待下次重试。
3. **stars_delta 全空**：`\\s+` 在 `browser_console` 转义失效 → 用 `a.textContent.match(/([\\d,]+) stars? (today|this week|this month)/)`。
4. **周榜 Search API 垃圾 repo 污染**（2026-07-17 新增）：周榜同样含 spam farm（x4gKing 系列空描述 + fork 数异常）、加密 sniper bot、游戏作弊器。过滤时额外关注空描述 + fork/star 比异常、描述含 sniper/bot/bundler 的项目。
5. **Search API 并行 browser_navigate 数据丢失**（2026-07-17 新增）：`browser_console` 只在最后导航的页面执行——并行调用时之前页面的数据无法提取。必须逐次 navigate → console → navigate → console。
6. **JSON 截断**：内置 `.slice(0,15)` + `.substring(0,200)` 防护。
7. **terminal tirith 拦截**：Cron 下不可用，直接用浏览器路径。
8. **execute_code cron 阻断**：同上。
