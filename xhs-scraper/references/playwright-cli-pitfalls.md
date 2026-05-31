# playwright-cli 自动化陷阱与双轨策略

## 核心结论

**playwright-cli 是为交互式使用设计的，不适合 bash 脚本编排的自动化场景。**

## 已验证成功的场景：交互式

```bash
# 手动执行三步，完美工作
playwright-cli -s=xhs open --config=cli.config.json
playwright-cli -s=xhs state-load state.json
playwright-cli -s=xhs --raw eval "..."  # 一次提取 33 篇笔记 ID ✅
```

## 失败的场景：bash 脚本自动化

### 问题 1：daemon 生命周期

```
脚本: pw open → daemon 启动 (pid=416795)
脚本: pw goto  → 导航中...
外部: pkill -f cliDaemon → daemon 被杀
脚本: pw eval  → "browser 'xhs-417419' is not open" ❌
```

playwright-cli 使用外部 daemon 管理浏览器。如果在脚本运行期间 daemon 被任何方式终止（系统 OOM、手动 kill、其他进程冲突），所有后续命令都会失败。

### 问题 2：goto 超时不可控

配置文件中 `timeouts.navigation: 60000` 对 `goto` 命令不总是生效。实际超时可能是默认的 30000ms。对于加载慢的站点（如小红书），30s 可能不够。

解决方法是用 `run-code` 显式设置超时：
```bash
playwright-cli -s=xhs run-code \
  "async page => { page.setDefaultNavigationTimeout(90000); await page.goto('URL', { waitUntil: 'domcontentloaded' }); }"
```

但即使是 `run-code` 也可能因为网络波动超时。

### 问题 3：僵尸进程积累

每次测试不完整清理就会留下 chrome-headless-shell 进程。多次测试后系统可能有十几到二十几个僵尸进程，消耗内存和文件句柄，导致后续命令全部超时。

清理命令：
```bash
for pid in $(ps aux | grep -E "chrome-headless|cliDaemon" | grep -v grep | awk '{print $2}'); do kill -9 $pid 2>/dev/null; done
```

### 问题 4：set -e 与 playwright-cli 不兼容

playwright-cli 的某些命令（如 `goto`）在超时后可能返回非零退出码，但页面实际上已经加载。如果脚本使用 `set -e`，会过早退出。

## 双轨策略（最终方案）

| 场景 | 工具 | 原因 |
|------|------|------|
| 交互式按需抓取 | **playwright-cli** | 手动执行，每次一条命令，无状态依赖问题 |
| Cron 定时自动抓取 | **Python Playwright 脚本** | 一个进程管理完整生命周期，`finally` 保证清理 |

## 安装要点

### root 用户必须禁用 sandbox

```json
// cli.config.json
{
  "browser": {
    "browserName": "chromium",
    "launchOptions": {
      "args": ["--no-sandbox", "--disable-setuid-sandbox"]
    }
  }
}
```

### npm 安装问题

`@playwright/cli` 的 alpha 依赖在 npm 上不存在。需要：
1. `git clone https://github.com/microsoft/playwright-cli.git`
2. 修改 `package.json` 将 `playwright-core` 版本改为存在的 alpha（如 `1.60.0-alpha-2026-04-09`）
3. `npm install`
4. 手动创建 symlink 到 `/usr/local/bin/`

## Python 脚本的关键修复

`scrape_notes.py` 的笔记 ID 提取：
- ❌ 错误：`document.querySelectorAll('section a[href*="/explore/"]')` — 主页上不存在 `/explore/` 链接
- ✅ 正确：`document.querySelectorAll('a[href*="/user/profile/" + uid + "/"]')` — 主页笔记链接格式为 `/user/profile/{uid}/{note_id}?xsec_token=...`

### 问题 5：bash wrapper 函数与 subshell Session ID

在脚本中封装 `pw()` 函数时如果用 `$$` 作为 session 名，`while read` 管道或命令替换 `$()` 创建 subshell 时 `$$` 可能不一致，导致 `pw open` 和后续 `pw eval` 连接到不同的 session。

```bash
# 不可靠 — while read 在 subshell 中运行时 $$ 会变
pw() { playwright-cli -s="xhs-$$" "$@" ...; }

# 更可靠的方式：脚本顶层一次性固定
SESSION="xhs-$(date +%s)"
pw() { playwright-cli -s="$SESSION" "$@" ...; }
```

**教训**：session 名必须在脚本最外层确定，不能在函数内或管道中动态生成。
