# 日晷设计系统

基于 Pulse Intel 共享设计系统，浅色 modern-minimal 方向。

## 颜色体系

所有颜色使用 oklch 色彩空间。

### 中性色（背景/前景/边框）

| 变量 | 值 | 用途 |
|------|-----|------|
| `--bg` | `oklch(99% 0.002 240)` | 页面背景 |
| `--bg-soft` | `oklch(97.5% 0.004 245)` | 次级背景 |
| `--surface` | `oklch(100% 0 0)` | 卡片/表层 |
| `--surface-2` | `oklch(98.5% 0.004 245)` | 表层变体 |
| `--surface-3` | `oklch(96.5% 0.006 248)` | 深层变体 |
| `--fg` | `oklch(18% 0.012 250)` | 正文 |
| `--fg-soft` | `oklch(28% 0.014 250)` | 次级文字 |
| `--muted` | `oklch(54% 0.012 250)` | 弱化文字 |
| `--muted-2` | `oklch(68% 0.010 250)` | 极弱文字 |
| `--border` | `oklch(92% 0.005 250)` | 默认边框 |
| `--border-strong` | `oklch(86% 0.006 250)` | 强调边框 |

### 产品色

| 变量 | 值 | 用途 |
|------|-----|------|
| `--accent` | `oklch(58% 0.18 255)` | 主强调色（蓝） |
| `--accent-soft` | `oklch(96% 0.025 255)` | 主色浅底 |
| `--accent-strong` | `oklch(48% 0.20 258)` | 主色加深 |
| `--cyan` | `oklch(64% 0.14 220)` | 青色 |
| `--violet` | `oklch(58% 0.17 290)` | 紫色 |
| `--warning` | `oklch(68% 0.15 75)` | 警戒色 |
| `--warn` | `oklch(72% 0.15 75)` | 警告色 |
| `--success` | `oklch(62% 0.14 150)` | 成功绿 |
| `--info` | `oklch(64% 0.14 220)` | 信息色 |

### 市场专用色（红涨绿跌）

| 变量 | 值 | 用途 | 适用范围 |
|------|-----|------|----------|
| `--positive` | `oklch(58% 0.20 25)` | 红=涨 | 仅小角标/涨跌幅 |
| `--positive-soft` | `oklch(97% 0.03 25)` | 浅红底 | 涨停行/tag |
| `--negative` | `oklch(62% 0.14 150)` | 绿=跌 | 仅小角标/涨跌幅 |
| `--negative-soft` | `oklch(96% 0.04 150)` | 浅绿底 | tag |

## 圆角体系

| 变量 | 值 | 用途 |
|------|-----|------|
| `--r-xs` | 4px | 图标/标签 |
| `--r-sm` | 6px | 小按钮/chip |
| `--r-md` | 10px | 输入框/KPI |
| `--r-lg` | 14px | 卡片/弹窗 |
| `--r-xl` | 18px | 大面板 |
| `--r-pill` | 999px | 药丸/标签 |

## 阴影

| 变量 | 用途 |
|------|------|
| `--sh-1` | 卡片基础阴影 |
| `--sh-2` | hover 浮起 |
| `--sh-pop` | 弹窗/悬停卡 |

## 字体

| 变量 | 栈 |
|------|-----|
| `--font-display` | `-apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", "PingFang SC", system-ui, sans-serif` |
| `--font-body` | `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "PingFang SC", system-ui, sans-serif` |
| `--font-mono` | `"JetBrains Mono", "SF Mono", ui-monospace, "Cascadia Mono", Menlo, monospace` |

不依赖 Google Fonts。

## 颜色分配规则（铁律）

**红涨绿跌仅用于交易小角标**，不可污染大卡片、横条、回测指标。

| 场景 | 色 | CSS 选择器 |
|------|-----|------------|
| trend 箭头涨 | `--positive` (红) | `.trend.up` |
| trend 箭头跌 | `--negative` (绿) | `.trend.down` |
| 价格涨 | `--positive` (红) | `.price-up` |
| 价格跌 | `--negative` (绿) | `.price-down` |
| tape 涨跌 | 红/绿 | `.pct.up` / `.pct.down` |
| 涨停标签 | 红底红字 | `.tag.group` |
| 涨停行 | 浅红底 | `.limit-up-row` |
| KPI 大数字 | 中性 `--fg` | `.kpi-value` |
| 情绪横条 | accent 渐变 | `.rt-fill.up/down` |
| 进度条 | accent/warn 渐变 | `.progress-fill` |
| 回测 return | `--accent-strong` (蓝) | `.metric.metric-ret` |
| 回测 drawdown | `--warn` (amber) | `.metric.metric-drawdown` |
| 回测 sharpe | `--violet` (紫) | `.metric.metric-sharpe` |
| 交易状态 pulse | `--success` (绿) | `.pulse` |
| 信号值 | `--violet` (紫) | `.value-signal` |
