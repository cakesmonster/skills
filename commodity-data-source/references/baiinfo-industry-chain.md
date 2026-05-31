# 百川盈孚行业链页面

## 页面结构

`http://wap.baiinfo.cn/industry-chain` 是 Nuxt SSR + 客户端 hydration。

**问题**：初始 HTML 只有空壳 Vue 组件，切换 tab 后的品种名只能靠 Playwright 执行 JS 后提取。

## 可直接提取的范围

- 第一个 tab（汽车）：53 个品种名 + `/product-detail/{品种}/{id}` 链接
- 正则：`re.findall(r'href="/product-detail/([^"]+)"[^>]*>([^<]+)<', html)`

## 必须用 Playwright 的范围

- 其余 8 个 tab（造纸77/医药82/光伏76/电池41/钢铁37/水处理28/轮胎20/饲料添加剂12）
- 视点详情页 `/viewpoint/{id}/{cid}`

## 采集脚本

`/root/.hermes/data/baiinfo/collect_chains.js`：playwright-core 调用 9 个 tab，输出 JSON。

**9 大频道品种数**（原始）：汽车53/造纸77/医药82/光伏76/电池41/钢铁37/水处理28/轮胎20/饲料添加剂12，合计约302个。
