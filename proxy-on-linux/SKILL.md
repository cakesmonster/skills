# proxy-on-linux

Linux 服务器通过订阅链接配置代理（sing-box + Reality），支持自动故障关闭看门狗。

## 背景

- 订阅格式：`vless://uuid@server:port?mode=multi&security=reality&pbk=...&sid=...&sni=...`（base64 编码）
- sing-box 支持从订阅里的 `pbk`（公钥）自动生成客户端私钥，无需额外配置 privateKey
- Xray 需要显式 privateKey，无法直接使用不含私钥的通用订阅
- **推荐使用 sing-box 而非 Xray**

## 快速使用

```bash
# 访问被墙网站（单次）
curl -x http://127.0.0.1:7890 https://被墙域名

# 长期使用，写到环境变量
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
```

## 服务控制

```bash
# 查看状态
systemctl status sing-box

# 关闭代理
systemctl stop sing-box

# 开启代理
systemctl start sing-box

# 重启代理（改完配置后）
systemctl restart sing-box

# 看门狗状态
systemctl status proxy-watchdog

# 关闭看门狗（仅停止自动检测，代理不动）
systemctl stop proxy-watchdog
```

## 架构

```
sing-box (systemd service)
├── inbound: http 127.0.0.1:7890（仅本机）
└── outbound: vless reality → 代理服务器

proxy-watchdog (systemd service)
├── 每30秒通过代理访问 google.com
├── 连续失败3次 → systemctl stop sing-box → 自动退出
└── 恢复成功 → 计数器清零，继续监控
```

## 配置步骤

### 1. 获取 sing-box 二进制

从 Mac 下载后上传（服务器 GitHub 下载速度极慢，通常只有几 KB/s）：

```bash
# 服务器准备接收
nc -l -p 5555 > /tmp/sing-box.tar.gz

# Mac 上传（文件路径替换为实际下载的 tar.gz）
nc 服务器IP 5555 < ~/Downloads/sing-box-1.13.12-linux-amd64.tar.gz
```

或者在服务器上用代理下载：

```bash
curl -o /tmp/sing-box.tar.gz -L --max-time 300 \
  'https://ghproxy.net/https://github.com/SagerNet/sing-box/releases/download/v1.13.12/sing-box-1.13.12-linux-amd64.tar.gz'
```

解压：

```bash
tar -xzf sing-box-*.tar.gz -C /tmp/
ls /tmp/sing-box-1.13.12-linux-amd64/
# 二进制路径: /tmp/sing-box-1.13.12-linux-amd64/sing-box
```

### 2. 解析订阅链接

```python
import base64, re, json

sub_url = "你的订阅链接"  # base64 编码的 vless URI 列表
raw = base64.b64decode(sub_url).decode()

nodes = []
for line in raw.strip().split('\n'):
    if 'vless://' not in line:
        continue
    m = re.match(r'vless://([^@]+)@([^:]+):(\d+)\?(.*)#(.+)', line)
    if not m:
        continue
    uuid, server, port = m.group(1), m.group(2), int(m.group(3))
    params = dict(p.split('=', 1) for p in m.group(4).split('&') if '=' in p)

    nodes.append({
        'tag': m.group(5),          # URL 编码的中文节点名
        'server': server,
        'port': port,
        'uuid': uuid,
        'pbk': params.get('pbk', ''),
        'sid': params.get('sid', ''),
        'sni': params.get('sni', ''),
    })

print(json.dumps(nodes, indent=2, ensure_ascii=False))
```

取第一个节点（或者测试延迟最低的），记下 `tag`、`server`、`port`、`uuid`、`pbk`、`sid`、`sni`。

### 3. 生成 sing-box 配置

```python
import json

# 用上一步解析出来的值替换下面这些占位符
SERVER = "服务器域名"
PORT = 端口数字
UUID = "订阅里的uuid"
PBK = "pbk公钥"
SID = "shortId"
SNI = "TLS SNI域名（通常 swcdn.apple.com）"

config = {
    "log": {"level": "warning"},
    "inbounds": [{
        "tag": "http",
        "type": "http",
        "listen": "127.0.0.1",
        "listen_port": 7890
    }],
    "outbounds": [
        {
            "tag": "proxy",
            "type": "vless",
            "server": SERVER,
            "server_port": PORT,
            "uuid": UUID,
            "flow": "xtls-rprx-vision",
            "network": "tcp",
            "tls": {
                "enabled": True,
                "server_name": SNI,
                "utls": {"enabled": True, "fingerprint": "chrome"},
                "reality": {
                    "enabled": True,
                    "public_key": PBK,
                    "short_id": SID
                }
            }
        },
        {"tag": "direct", "type": "direct"}
    ],
    "route": {"auto_detect_interface": True}
}

with open('/etc/sing-box/config.json', 'w') as f:
    json.dump(config, f, indent=2)
```

### 4. 安装 systemd 服务

```bash
cat > /tmp/sing-box.service << 'EOF'
[Unit]
Description=sing-box proxy
After=network.target

[Service]
ExecStart=/tmp/sing-box-1.13.12-linux-amd64/sing-box run -C /etc/sing-box
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cp /tmp/sing-box.service /etc/systemd/system/sing-box.service
systemctl daemon-reload
systemctl enable sing-box
systemctl start sing-box
```

### 5. 安装看门狗（可选，推荐）

```bash
cat > /usr/local/bin/proxy-watchdog.sh << 'WATCHDOG'
#!/bin/bash
PROXY="http://127.0.0.1:7890"
TEST_URL="https://www.google.com"
TIMEOUT=10
MAX_FAIL=3
CHECK_INTERVAL=30

fail_count=0
echo "$(date): 代理看门狗启动"

while true; do
    if curl -x "$PROXY" --max-time "$TIMEOUT" -s -o /dev/null -w "%{http_code}" "$TEST_URL" | grep -qE "^(200|301|302)"; then
        [ "$fail_count" -gt 0 ] && echo "$(date): 代理恢复" && fail_count=0
    else
        fail_count=$((fail_count + 1))
        echo "$(date): 代理连接失败 (${fail_count}/${MAX_FAIL})"
        [ "$fail_count" -ge "$MAX_FAIL" ] && echo "$(date): 关闭 sing-box" && systemctl stop sing-box && exit 0
    fi
    sleep $CHECK_INTERVAL
done
WATCHDOG
chmod +x /usr/local/bin/proxy-watchdog.sh

cat > /etc/systemd/system/proxy-watchdog.service << 'EOF'
[Unit]
Description=Proxy Watchdog
After=sing-box.service

[Service]
Type=simple
ExecStart=/bin/bash /usr/local/bin/proxy-watchdog.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable proxy-watchdog
systemctl start proxy-watchdog
```

### 6. 验证

```bash
curl -x http://127.0.0.1:7890 --max-time 10 https://httpbin.org/ip
# 返回代理出口 IP（非服务器原 IP）说明代理正常
```

## 已知坑

1. **Xray 无法直接用这个订阅**：Xray outbound reality 要求 `privateKey`，订阅只有服务端公钥 `pbk`。Clash/sing-box 可从 pbk 自动派生私钥，Xray 不行。**用 sing-box。**

2. **sing-box 字段名**：outbound 用 `server_port`（非 `port`），`server_name`（非 `servername`），`public_key`（非 `publicKey`），`short_id`（非 `shortId`）。

3. **reality 必须配 utls**：`utls.enabled` 和 `utls.fingerprint` 必须设置，否则报错 "uTLS is required by reality client"。

4. **不要加 `route.outbounds`**：sing-box 的 route 里没有 `outbounds` 字段，所有流量默认走第一个 outbound。

5. **订阅里 `sni` 和 `servername` 可能不同**：一般填 `swcdn.apple.com`，具体看订阅解析出来的 `sni` 字段。

6. **geoip/geosite 文件**：sing-box 不需要，Xray 需要。