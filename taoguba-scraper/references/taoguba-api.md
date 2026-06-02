# 淘股吧 (tgb.cn) 数据抓取

## 反爬要点

- **浏览器工具不可用**：Browserbase IP 被淘股吧 WAF 拦截，返回 502。但 curl 加 Chrome UA 正常返回 200
- **Cookie**：首次请求会自动获得 `JSESSIONID` 和 `acw_tc`，后续请求需带 cookie
- **User-Agent**：必须伪装浏览器，`Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36`
- **Referer + X-Requested-With**：AJAX 请求建议带 `Referer: https://www.tgb.cn/` 和 `X-Requested-With: XMLHttpRequest`

## 域名

- `taoguba.com.cn` → 301 → `tgb.cn`
- 所有API都在 `www.tgb.cn` 下

## 首页栏目 API 端点

通过逆向 `res/js/spmatch/default2022_spmatch.min.9c92462f.js` 中的 `DefaultAjax(type, pageNo)` 函数得到：

| type | 栏目 | API 端点 | 备注 |
|:----:|------|----------|------|
| 1 | 综合推荐 | `/newIndex/getZh?pageNo=X` | 默认首页 |
| 2 | 网友精选 | `/newIndex/getFriendsFeatured?pageNo=X&topID=Y` | |
| 3 | **今日推荐** | `/newIndex/getNowRecommend?pageNo=X` | perPageNum=15 |
| 4 | 淘县院子 | `/newIndex/getTxyz` | 不分页 |
| 5 | 淘县神评 | `/newIndex/getReplySP?pageNo=X&type=ALL` | |
| 6 | 研股 | `/newIndex/getStockResearch?pageNo=X&type=1&sxType=1` | |

## 返回格式

```json
{
  "status": true,
  "dto": {
    "perPageNum": 15,
    "pageNo": 1,
    "list": [
      {
        "userID": 14258882,
        "userName": "作者名",
        "topicID": 8382620,
        "subject": "标题",
        "subinfo": "摘要",
        "newTopicID": "2s7D3eqcEwN",
        "totalViewNum": 352,
        "totalReplyNum": 0,
        "usefulNum": 0,
        "imgurl": ["https://image.tgb.cn/..."],
        "type": "2",
        "dateTime": 1779838652000,
        "topicType": "T"
      }
    ]
  }
}
```

## 帖子内容抓取

帖子 URL：`https://www.tgb.cn/a/{newTopicID}`

正文提取：HTML 中 `<div class="article-text p_coten" id="first" style="">` 的内容。提取时注意：
- **不要用正则 `</div>` 截断**：正文内部有大量嵌套 div（a 标签、样式 div），第一个 `</div>` 不是正文结束
- 用 `article-reward` 或 `article-topic` 作为结束标记
- 标签清理：`<br/>` → 换行，`<a>` → 保留链接文字，`<img>` → `[图]`，其余删除
- **不要**用 `unicode_escape` 解码——内容是直接 UTF-8 中文，不需要转义

```python
start = html.find('class="article-text')
if start >= 0:
    tag_end = html.find('>', start)
    end = html.find('class="article-reward', tag_end)
    if end < 0:
        end = html.find('class="article-topic"', tag_end)
    raw = html[tag_end+1:end]
    raw = re.sub(r'<br\s*/?>', '\n', raw)
    raw = re.sub(r'<a[^>]*>([^<]*)</a>', r'\1', raw)
    raw = re.sub(r'<img[^>]*>', '[图]', raw)
    raw = re.sub(r'<[^>]+>', '', raw)
```

## 去重

API 偶尔返回重复帖子（同 `newTopicID` 出现 2 次），需要去重。
