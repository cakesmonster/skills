---
name: proxy-on-linux
description: Linux 服务器代理 — 机场订阅 → mihomo(Clash Meta) + watchdog 自愈。2026-09-15 起现行方案，sing-box 为已停用旧案。含构建顺序与订阅更新方法。
version: 2.0.0
---

# Linux 代理（mihomo / Clash Meta）

当前部署（本机实测 2026-09-30）：`curl -x http://127.0.0.1:7890 https://www.google.com` → HTTP 200。

## 现状架构

```
机场订阅(clash格式, 117节点 vless+reality)
  └→ /etc/mihomo/config.yaml          ← 订阅原样落地(含uuid/pbk, 敏感, 勿入git)
mihomo  v1.19.31  /usr/local/bin/mihomo   (systemd: mihomo.service, enabled)
  ├─ mixed-port: 127.0.0.1:7890        ← HTTP+SOCKS 共用, 程序都指这里
  └─ external-controller: 127.0.0.1:9090  ← REST API(换节点/查延迟)
proxy-watchdog  ~/cakemonster/proxy-watchdog/proxy-watchdog.sh (systemd, enabled)
  ├─ 每30s: curl google via :7890
  ├─ 连续3次失败 → systemctl restart mihomo
  └─ 30分钟内重启满3次 → 退避30分钟(防重启风暴)
geo 数据: /etc/mihomo/{geoip.dat, geosite.dat, geoip.metadb}
```

历史注：`sing-box.service` 仍装着但 **inactive（2026-09-15 被 mihomo 取代）**。
不要误启动它——和 mihomo 抢 7890。回退旧案见文末。

## 构建顺序（从零部署一台新服务器）

1. **下载 mihomo 二进制**（GitHub 直连慢，挂代理或 ghproxy）
   ```bash
   curl -L -o /tmp/m.zip https://ghproxy.net/https://github.com/MetaCubeX/mihomo/releases/download/v1.19.31/mihomo-linux-amd64-v1.19.31.zip
   unzip /tmp/m.zip -d /tmp/m && cp /tmp/m/mihomo /usr/local/bin/ && chmod +x /usr/local/bin/mihomo
   ```
2. **落地订阅** → `/etc/mihomo/config.yaml`（机场"复制 Clash 配置"直接整份落盘，reality 节点 mihomo 原生支持，无需推导私钥）+ 放入 geoip/geosite 文件
3. **systemd** `/etc/systemd/system/mihomo.service`：
   ```ini
   [Service]
   ExecStart=/usr/local/bin/mihomo -d /etc/mihomo
   Restart=always
   RestartSec=3
   LimitNOFILE=1048576
   ```
4. **watchdog**：脚本放 `~/cakemonster/proxy-watchdog/`，unit 的 `ExecStart=/bin/bash <该路径>/proxy-watchdog.sh`，`After=mihomo.service`
5. **验证**：
   ```bash
   curl -x http://127.0.0.1:7890 --max-time 10 https://httpbin.org/ip   # 出口IP≠服务器IP
   curl -s http://127.0.0.1:9090/version                                 # {"meta":true,...}
   ```

## 更新订阅

机场面板换配置 → 新的 clash 整份配置覆写 `/etc/mihomo/config.yaml` → `systemctl restart mihomo` → 跑上面验证。watchdog 不用动。

## 排障顺序

```bash
systemctl is-active mihomo proxy-watchdog        # 服务层
ss -tlnp | grep 7890                             # 监听层(确认是mihomo不是别的)
journalctl -u proxy-watchdog --since "-1h"       # 探测史: "失败(n/3)"/"已恢复"/"退避"
journalctl -u mihomo --since "-1h"               # mihomo自身日志
curl -s http://127.0.0.1:9090/proxies | head -c 300   # 节点组状态(REST)
```
- watchdog 报 1/3 后自动恢复 = 瞬时抖动，正常，不处理
- watchdog 进入"退避" = mihomo 反复起不来，多半订阅节点全挂 → 换订阅
- google 通但某站不通 = 分流规则问题，改 config.yaml rules 后 restart

## 已知坑

1. **Reality 订阅的客户端差异**：Xray 要显式 privateKey（通用订阅没有）→ 握手失败；Clash/mihomo/sing-box 从 pbk 自动推导 → 能用。**Linux 上别用 Xray 跑订阅。**
2. **watchdog 语义（2026-09-15 定稿）**：连续失败是"restart+退避"，不是早期版本的"stop 永久关闭"——旧脚本模板已过时，以 `~/cakemonster/proxy-watchdog/proxy-watchdog.sh` 为准。
3. **config.yaml 是敏感文件**：明文含 uuid/reality 公钥。留在 /etc/mihomo，永不进 git 仓库（skills 仓库只写方法不写订阅）。
4. **external-controller 保持 127.0.0.1**：这台机无认证暴露史（sundial 同类问题），9090 开对外=任何人控制你的代理。
5. 环境变量持久化非必需：程序都是显式 `-x http://127.0.0.1:7890`，改全局 http_proxy 会波及 pip/system 等所有出站。

## 旧案回退（sing-box，2026-09-15 前）

`/etc/sing-box/config.json` + sing-box v1.13.12，单节点 reality outbound。字段坑：`server_port`/`public_key`/`short_id` snake_case；`tls.utls={enabled:true,fingerprint:"chrome"}` 必配；route 无 outbounds 字段。仅当 mihomo 方案整体失效时用，且先 stop mihomo。

## 相关文件

- `~/cakemonster/proxy-watchdog/proxy-watchdog.sh` — watchdog 现行实现（git 管理）
- `/etc/mihomo/config.yaml` — 现行订阅配置（敏感）
- `git@github.com:cakesmonster/skills` — 本文档仓库
