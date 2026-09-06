---
name: product-hunt
description: 抓取 Product Hunt 日/周/月热门产品榜（votes 排名），输出中文 Markdown 简报。GraphQL API 主路径，Atom feed 零配置降级。当用户要"PH 榜单 / Product Hunt 今日热门 / 科技新品日报"时使用。
version: 1.0.0
---

# product-hunt — 获取 Product Hunt 热门产品

抓取 Product Hunt 榜单（日/周/月，按 votes 排名），输出中文 Markdown 简报。
结构对标 `github-trending`，但**抓取方法完全不同**：PH 网页被 Cloudflare 全面拦截，必须走 API 或 feed。

## 关键事实（2026-09-06 实测）

| 路径 | 可用性 | 说明 |
|------|--------|------|
| 浏览器打开 `producthunt.com/leaderboard/...` | ❌ | Cloudflare 交互式 Turnstile；CloakBrowser headless 和 Xvfb 有头（等 70s）均过不去。**不要再试浏览器路径** |
| `r.jina.ai` 等中转 | ❌ | 本机网络不通 |
| **GraphQL API v2**（`api.producthunt.com/v2/api/graphql`） | ✅ 主路径 | 需 API key；votes 排名完整；日/周/月/主题均可 |
| **`https://www.producthunt.com/feed`** | ✅ 降级路径 | curl 直连 200，无 key；~50 条近期条目，**无票数、非 votes 排名**，仅覆盖约 5 天 |

## 前置条件：API key（一次性）

1. boss 用 PH 账号登录 `developer.producthunt.com` → 创建 app（redirect URI 填 `http://localhost`）→ 得 `API Key` + `API Secret`（自动批准，无需审核）
2. **鉴权实测结论（2026-09-06）**：
   - ✅ **Developer Token 直用**：dashboard 里 "Developer Token"（43 字符，User Context: 本人账号，Expires: Never）**直接当 Bearer 用即可**，最简单，脚本首选（`PH_DEV_TOKEN`）
   - ❌ `client_credentials` 换 token：实测报 `invalid_client`（app 注册成 Confidential 也可能被拒，别在这上面浪费时间）
   - ❌ API Key / Secret 直接当 Bearer：`invalid_oauth_token`
3. 凭证存 `~/.hermes/profiles/news-friday/.env.ph`（权限 600，勿提交 git）：
   ```
   PH_DEV_TOKEN=***
   ```
   ⚠️ **粘贴长 token 进聊天/文件时警惕省略号截断**：实配中曾出现 token 被渲染为 `前6字符…后6字符`（仅 13 字符），API 报 invalid_oauth_token。落盘后先 `source` + `echo ${#PH_DEV_TOKEN}` 验长度（43），再打 API。
4. **没有 token 也能跑**（自动降级 feed），但输出须注明"无票数排名，仅近期条目"

token 换取流程（仅备用，实测不可用）：
```bash
curl -s -X POST https://api.producthunt.com/v2/oauth/token \
  -d grant_type=client_credentials -d client_id=$PH_API_KEY -d client_secret=$PH_API_SECRET
```
脚本已带 token 缓存（`/tmp/.ph_token`）与过期自动重取（仅 client_credentials 路径）。

## 使用方法

### 方式一：脚本一把梭（推荐 ⭐）

```bash
source ~/.hermes/profiles/news-friday/.env.ph   # 载入 key
SKILL_DIR=~/.hermes/profiles/news-friday/skills/developer-tools/product-hunt

bash $SKILL_DIR/scripts/ph_fetch.sh daily      # 近 24h top20 by votes
bash $SKILL_DIR/scripts/ph_fetch.sh weekly     # 近 7 天
bash $SKILL_DIR/scripts/ph_fetch.sh monthly    # 近 30 天
bash $SKILL_DIR/scripts/ph_fetch.sh feed       # 无 key 降级
PH_RANKING=ai bash $SKILL_DIR/scripts/ph_fetch.sh weekly   # 按主题过滤（topic slug，如 ai/dev-tools/productivity）
```

输出 JSON lines：`{rank, name, tagline, votes, comments, url, created, topics[], source}`。
`source=api` 有票数；`source=feed` 票数为 null。**拿到 JSON 后由 agent 格式化中文简报**（见下）。

### 方式二：直接 GraphQL（自定义查询时）

```bash
TOKEN=*** -s -X POST https://api.producthunt.com/v2/oauth/token \
  -d grant_type=client_credentials -d client_id=$PH_API_KEY -d client_secret=$PH_API_SECRET | jq -r .access_token)
curl -s -X POST https://api.producthunt.com/v2/api/graphql \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  --data '{"query":"{ posts(order: VOTES, postedAfter: \"2026-09-01T00:00:00Z\", first: 10) { edges { node { name tagline votesCount commentsCount url topics(first:3) { edges { node { name } } } } } } }"}'
```

可查字段：`posts / products / topics / users / collections`。rate limit 按 complexity 计（6500/15min），榜单查询单次 ~30，日报量绝对安全。

## 输出格式（Cron 推送）

中文 Markdown 简报：
1. 标题 + 日期 + 来源说明（标注 `api`（含票数）还是 `feed` 降级（无票数））
2. 主榜表格：排名 | 产品 | 一句话简介（tagline 中译） | ⭐票数 | 💬评论 | 主题标签
3. **每个产品配 `📝` 一行中文简介**（硬性要求，tagline 直译不够时结合 topics 补语境）
4. 榜单后 3-5 条亮点解读（哪类产品在爆发、有没有值得注意的模式）
5. 末尾趋势观察（AI 占比、工具类 vs 消费类等维度归纳）

## Cron 注意事项

- 本 profile 下 terminal/curl 可用（不同于 github-trending 的 tirith 拦截环境）；如遇拦截，降级用 `browser_navigate` 打开 `https://www.producthunt.com/feed`（返回 XML，可在 console 里 DOMParser 解析——**这是唯一允许走浏览器的 PH 路径**）
- feed 的 Atom 解析不要依赖固定 entry 数（50 条上限，周末会变少）
- API 403 → 先 `rm /tmp/.ph_token` 再重试（token 过期）；仍 403 → key 被吊销，提示 boss 重新申请
- 时区：PH 按 PT 计算"一天"；`postedAfter` 用 UTC，daily 榜在 UTC 早晨跑会拿到"昨天下午起"的不完整榜单。最佳推送时间：北京早上（≈ PT 傍晚，当天榜单基本定型）

## 与 github-trending 的差异（迁移认知）

| 维度 | github-trending | product-hunt |
|------|-----------------|--------------|
| 页面抓取 | SSR HTML ✅ | Cloudflare ❌ 完全不可行 |
| 主数据源 | Trending 页 / Search API | GraphQL API（需 key） |
| 增量指标 | stars today | votesCount（绝对票数，非增速） |
| 无凭证降级 | Search API | /feed（无票数） |
| 垃圾污染 | 需过滤 spam repo | 基本不需要（PH 有人审） |

## 已知陷阱（2026-09-06 全部实测）

1. **topic slug 无效时静默返回 0 结果**（不报错）：`topic: "ai"` 是无效 slug，必须 `artificial-intelligence`。`mk_query.py` 内置常用短名映射表；表外主题先用 `topics(first: 50, slug: "xxx")` 查询验证。
2. **token 经聊天/渲染层粘贴会被省略号截断**：截断形态 = 前 6 字符 + `…` + 后 6 字符（共 13 字符）→ invalid_oauth_token。完整 token 恒为 **43 字符**，配置后必验 `${#PH_DEV_TOKEN}`。
3. **凭证文件里的 `…`（U+2026）肉眼难辨**：`write_file` 时若从对话复制，注意对话渲染可能已把长串截断——宁可让 boss 用代码块发原文，或逐段比对。
4. **bash 脚本中嵌套 GraphQL 引号地狱**：查询 JSON 一律交给 `mk_query.py` 生成，shell 只传 env 变量，不要在 .sh 里手写转义。
5. **feed 的 rank 只是 feed 顺序，不是 votes 排名**；输出简报时必须注明降级来源，禁止给 feed 条目编投票数。
6. `do_fetch` 的 header 写成 `"Bearer ***"` 会导致永远 401——真实脚本用 `${1}` 传 token。
