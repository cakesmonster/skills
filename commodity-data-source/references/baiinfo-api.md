# 百川盈孚 API 参考

## 接入基础

```
PC站:   https://www.baiinfo.com
移动站: http://wap.baiinfo.cn  （注意：必须用 http）
```

## 首页文章列表（免费）

```
GET http://wap.baiinfo.cn/
```

返回 SSR HTML，直接嵌入 4 篇分析文。

## 价格行情（需登录）

```
GET http://wap.baiinfo.cn/price/getAllMarket?type=1
```

返回 JSON 价格数据。无需登录可访问时直接抓取；返回空说明需要 cookie。

## 登录墙

| 页面 | 内容 | 状态 |
|------|------|:---:|
| `/viewpoint/{id}/{cid}` | 分析文正文 | ❌ 需登录 |
| `/product-detail/{name}/{id}` | 产品详情 | ❌ 需登录 |

返回「您还没有登录，请先登录」时无法继续抓取，需解决登录态。
