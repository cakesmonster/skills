# 连板天梯 label 格式 — SKILL 文档与测试对齐

## 分组逻辑

`compute_ladder()` 使用 `item["total_days"]` 和 `item["total_boards"]`，分组 label 公式：

```python
label = f"{td}连板" if td == tb else f"{td}天{tb}板"
```

| total_days | total_boards | label |
|------------|--------------|-------|
| 3 | 3 | `"3连板"` |
| 5 | 4 | `"5天4板"` |
| 2 | 2 | `"2连板"` |

## Eastmoney zttj 字段来源

`push2ex` 返回的 `zttj` 对象（`{days: N, ct: M}`）是唯一正确来源。
旧字段 `lbc`（连板数）仅在非连续性涨停场景下作为 fallback。

## 测试 fixture 要求

`make_limit_up_item` 必须同时返回 `total_days` 和 `total_boards`：

```python
return {
    ...
    "board_count": board_count,
    "total_days": board_count,    # 兼容 SKILL 字段
    "total_boards": board_count,  # 兼容 SKILL 字段
    ...
}
```

若测试 assert key 为 `"2"` 但实际 label 是 `"2连板"`，是 fixture 缺少 `total_days/total_boards` 字段导致 `td` 默认为 1，不是 SKILL 错。