---
name: xhs-scraper
version: 1.0.0
description: "小红书通用抓取器：QR 码登录 → Cookie 持久化 → 任意博主主页/单篇笔记抓取。适用场景：用户给你一个小红书链接，你需要抓取内容。"
triggers:
  - 小红书
  - xhs
  - 扫码登录
  - 博主主页
  - 笔记
  - 抓取帖子
  - 小红书链接
  - xiaohongshu
---

# 小红书通用抓取器 (XHS Scraper) v2.0

> 基于 **Microsoft Playwright CLI** 的标准化浏览器自动化。不再依赖手写 Python 脚本。

## 前置依赖

```bash
# playwright-cli（已安装在 /usr/local/bin/playwright-cli）
npm install -g @playwright/cli@latest   # 当前版本: 0.1.13
playwright-cli install-browser chromium

# Python（仅用于 JSON 处理）
python3 -c "import json"  # 系统自带
```

## 数据流（v2.0）

```
playwright-cli -s=xhs open --config=cli.config.json
    ↓
playwright-cli -s=xhs state-load state.json    ← 复用登录态
    ↓
playwright-cli -s=xhs goto 博主主页
playwright-cli -s=xhs eval "..."   → 提取笔记 ID
    ↓
playwright-cli -s=xhs goto 笔记详情页
playwright-cli -s=xhs eval "..."   → 提取正文
    ↓
JSON 保存到 --data-dir
```

## 脚本清单

| 脚本 | 用途 |
|------|------|
| `scripts/xhs_scrape.sh <uid> [data_dir]` | **一键抓取**（打开浏览器→加载登录态→抓取→保存→关闭） |
| `scripts/login_qr.py` | QR 码扫码登录（备用，仍可用） |

## 使用流程

### 第一步：登录（一次性，以后复用 state.json）

**方式 A：用 playwright-cli（推荐）**
```bash
playwright-cli -s=xhs-login open --config=~/.hermes/data/xhs/cli.config.json https://www.xiaohongshu.com/login
playwright-cli -s=xhs-login screenshot --filename=/tmp/xhs_qr.png
# → 把 QR 发给用户扫码
# → 等用户扫码后验证:
playwright-cli -s=xhs-login eval "document.title"
# → 保存状态:
playwright-cli -s=xhs-login state-save ~/.hermes/data/xhs/state.json
playwright-cli -s=xhs-login close
```

**方式 B：用 login_qr.py（自动生成 QR + 轮询）**
```bash
python3 ~/.hermes/skills/trading/xhs-scraper/scripts/login_qr.py
# → 扫码 → 自动检测 → 保存 state.json
```

### 第二步：抓取（一键）

```bash
./xhs_scrape.sh <24位user_id> ~/.hermes/data/xhs/博主名/
```

## 与 Python 版对比

| | Python 版 (v1) | playwright-cli 版 (v2) |
|---|---|---|
| 代码量 | ~300 行 Python/script | 1 行 CLI 命令 |
| Cookie 管理 | 手动 cookies.json | `state-save` / `state-load` |
| 元素定位 | JS 选择器硬编码 | 标准化 `eval` + snapshot |
| 可维护性 | 需维护 Python 依赖 | 无额外依赖 |
| 标准化 | 自创 | Microsoft 官方 CLI |
| Skills | 无 | 自带 SKILL.md + references |

## 数据格式

每篇笔记保存为 JSON：

```json
{
  "note_id": "6a0723eb00000000080241d3",
  "title": "笔记标题或正文首行",
  "desc": "完整正文内容",
  "date": "2026-05-15",
  "author": "博主昵称",
  "type": "normal",
  "scraped_at": 1778863892
}
```

数据目录结构：
```
~/.hermes/data/xhs/
  cookies.json          ← 登录 Cookie
  博主名/               ← 每个博主独立目录
    note_ids.json       ← 已抓笔记索引
    meta.json           ← 抓取元数据
    {note_id}.json      ← 单篇笔记内容
```

## 关联 Skill

- **`playwright-cli`**：浏览器自动化 CLI（`open → state-load → eval` 模式）
- **`stock-price-query`**：A股/港股/美股实时行情查询（通过 SkillHub CLI 安装）

## 参考文档

- **[playwright-cli 自动化陷阱与双轨策略](references/playwright-cli-pitfalls.md)** — daemon 生命周期、超时处理、僵尸进程清理、bash 脚本编排注意事项

## 其他安装渠道

腾讯 SkillHub 提供了一键安装 CLI：
```bash
curl -fsSL https://skillhub.cn/install/skillhub.md | bash -s -- --cli-only
skillhub search <关键字>
skillhub install <技能名>
```
技能会安装到当前 workspace。部分技能（如 `stock-price-query`）来自 ClawHub 社区。若 SkillHub 上找不到，回退到本 Skill 的手动安装方式。
