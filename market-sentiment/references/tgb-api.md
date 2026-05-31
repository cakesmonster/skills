# 淘股吧 API 逆向

## 栏目端点

```
GET https://www.taoguba.com/newIndex/getNowRecommend?pageNo=1
```

返回结构化热帖列表，包含标题、点赞数、评论数、发布时间。

## 帖子抓取

```
GET https://www.taoguba.com/a/{newTopicID}
```

正文在 `<div class="topic-content">` 内，需提取正文文字。

## 反爬处理

- 请求频率过快会触发验证码，建议每次抓取间隔 ≥2s
- 部分帖子需要登录才能访问正文，返回空则降级处理
- 推荐使用 session 保持cookie，提升访问成功率
