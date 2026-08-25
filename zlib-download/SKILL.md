---
name: zlib-download
description: 从 Z-Library 下载书籍（优先 EPUB），使用 CloakBrowser + Xvfb 绕过 Cloudflare 检测，账号密码自动登录。下载目录：~/Downloads/zlib/
---

# Z-Library 书籍下载 Skill

## 激活条件

用户提供 Z-Library 链接或书名，要求下载书籍时使用。

## 环境要求

- CloakBrowser 已安装（二进制在 `/root/.cloakbrowser/`）
- sing-box 代理运行在 `127.0.0.1:7890`
- Xvfb 已安装（`yum install -y xorg-x11-server-Xvfb`）
- **sing-box 路径坑**：`/tmp` 是 936M tmpfs，重启会清空。`/etc/systemd/system/sing-box.service` 默认 ExecStart 指向 `/tmp/sing-box-1.13.12-linux-amd64/sing-box`，**重启后会 203/EXEC 失败**。修复：把 service 改指向 `/usr/local/bin/sing-box`（系统装的版本），`sudo systemctl daemon-reload && sudo systemctl restart sing-box`。
- 账号已登录（会话保存于 `~/.zlibrary/storage_state.json`）

## 使用流程

### Step 1: 首次登录（仅需一次）

提供账号密码，全自动登录并保存会话：

```bash
xvfb-run -a python3 -u ~/cakemonster/skills/zlib-download/scripts/login.py <邮箱> <密码>
```

登录成功后会话持久化，后续下载无需重新登录。

### Step 2: 搜索书籍（如只有书名）

```bash
xvfb-run -a python3 -u ~/cakemonster/skills/zlib-download/scripts/search.py <书名>
```

输出书籍链接列表，选择对应链接进行下载。

### Step 3: 下载书籍

```bash
xvfb-run -a python3 -u ~/cakemonster/skills/zlib-download/scripts/download.py <Z-Library书籍链接>
```

书籍保存到 `~/Downloads/zlib/`。

## 核心脚本

| 脚本 | 用途 |
|------|------|
| `login.py <邮箱> <密码>` | 账号密码全自动登录（仅首次需要） |
| `search.py <书名>` | 搜索书籍，返回链接列表 |
| `download.py <URL>` | 下载书籍（优先 EPUB） |

## 技术细节

- **Cloudflare 绕过**：CloakBrowser（58 个 C++ 级别指纹补丁）配合 Xvfb 虚拟显示
- **代理**：通过 sing-box（`http://127.0.0.1:7890`）连接 Z-Library
- **下载格式**：优先 EPUB（用户偏好），无 EPUB 时降级 PDF
- **下载链接提取**：从书籍页面直接提取 `a.addDownloadedBook` 链接
- **下载方式**：使用 Playwright `expect_download()` 捕获触发式下载
- **文件名**：从页面标题自动清理构造

## 关键发现（踩坑记录）

1. **Z-Library 登录页**：`https://zh.zlib.li/login`，表单 `#loginForm`，输入框 `input[name="email"]` / `input[name="password"]`，提交按钮 `button[type="submit"]`
2. **搜索**：需先用 JS 调用 `openSearchLine()` 展开搜索栏，再 submit 表单，搜索结果页 URL 含 `token` 参数需保护
3. **下载链接**：书籍页面的 `a.addDownloadedBook` 元素含 `/dl/<id>` 格式链接，需补充域名；EPUB 线上阅读链接 ≠ 下载链接
4. **Xvfb 必须**：CloakBrowser 必须有虚拟显示环境，`xvfb-run -a` 分配虚拟显示器
5. **download.py 中 `page.goto()` 不能用于触发下载**，必须用 `page.evaluate()` 改变 window.location 或 `expect_download()` 上下文管理器

## 依赖

- `cloakbrowser`
- `ebooklib`
- `beautifulsoup4`
- `xvfb`（系统包）

## 注意事项

仅用于：
- ✅ 拥有合法访问权限的资源
- ✅ 公共领域或开源许可的文档
- ❌ 版权 infringing 用途

## 当前可用性（2026-07-15）

- sing-box 节点 `pro-hk-01` 已死（`dus148.sdwan.realm-sync.com` 连不上，重启无用 — 订阅失效）
- 但 **`z-lib.li` 国内直连可达**（Cloudflare 104.21.x.x），CloakBrowser 绕得过 anti-bot
- ⚠️ **新限制**：z-lib.li 现在强制登录才能搜书；原 `storage_state.json` 的 cookie 是给 `zh.zlib.li` 的，**z-lib.li 不认**。未登录直接 `s?q=xxx` 会返回 "Please log in to your account to see the results"
- Anna's Archive / LibGen 国内 IP SSL 阻（CF 反代 parklogic），走不通
- Anna's Archive 也要求登录才能下载
- 国内电子书源（豆瓣/京东/当当）搜索页 JS 占位，纯 HTTP 抓不到结果

**结论**：在 boss 提供新 VPN 节点或 Z-Library 账号之前，下载外文电子书基本无解；下载国内出版社电子书（尤其新书）只能走微信读书/京东读书 VIP 在线阅读，没有 PDF。

