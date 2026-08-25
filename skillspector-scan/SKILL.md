---
name: skillspector-scan
description: 新装 skill 前的强制安全扫描流程。基于 NVIDIA SkillSpector（已克隆到 /root/cakemonster/skills/skillspector/），默认走 --no-llm 纯静态模式（保护隐私 + 离线 + 快），仅在风险分 ≥ 60 或用户明确要求时启用 LLM 阶段。触发场景：① 用户下载/安装新 skill 后；② 用户说"扫一下 X skill"；③ 周期性基线扫描。
---

# SkillSpector Scan — 新装 skill 前置安全检查

## 核心规则

1. **默认 `--no-llm`**。理由：① 静态阶段已覆盖 64 个模式 / 16 类；② LLM 阶段要发内容到第三方 API；③ 你的 `private-skills` 含医疗/个人数据，绝不外发。
2. **风险阈值 ≥ 60** 才升级到 LLM 阶段（不发给第三方）或上报 boss 决定。
3. **三个动作**根据风险分级处理：
   - `SAFE` / `LOW`（risk_score < 40）：静默通过
   - `MEDIUM`（40-69）：列出 issues 给用户
   - `HIGH` / `CRITICAL`（≥ 70）：**拒绝安装**，必须人工裁决

## 工具准备

SkillSpector 已下载到 `/root/cakemonster/skills/skillspector/`，Python 3.12 venv 已建。

```bash
# 验证可用（每次会话开始或怀疑环境坏了时跑）
source /root/cakemonster/skills/skillspector/.venv/bin/activate
skillspector --version  # 期望：SkillSpector v2.x.x
```

如果 venv 坏了，重建：
```bash
cd /root/cakemonster/skills/skillspector
uv venv --python /root/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/bin/python3.12 .venv
source .venv/bin/activate && uv pip install -e .
```

## 标准扫描流程

### 1. 单个 skill 扫描（标准用法）

```bash
source /root/cakemonster/skills/skillspector/.venv/bin/activate
skillspector scan <PATH_TO_SKILL> --no-llm --format json -o <REPORT.json>
```

**参数解释**：
- `<PATH_TO_SKILL>`：skill 目录、zip、URL、.md 文件均可
- `--no-llm`：纯静态，跳过 LLM（**默认必须**）
- `--format json -o`：机器可读，便于后续解析

### 2. 解析结果

JSON 结构（实测验证）：
```python
{
  "skill": {...},                # 被扫描 skill 元信息
  "risk_assessment": {           # 核心
    "risk_score": int | None,    # 0-100，可能为 None
    "severity": "LOW|MEDIUM|HIGH|CRITICAL",
    "recommendation": "SAFE|CAUTION|DANGER|BLOCK"  # 实测
  },
  "issues": [                    # 详细问题清单
    {
      "id": "LP3",               # 模式 ID
      "category": "MCP Least Privilege",
      "severity": "MEDIUM",
      "confidence": 0.0-1.0,
      "location": {"file": "...", "start_line": N},
      "explanation": "...",
      "remediation": "..."       # 修复建议
    }
  ],
  "components": {...},
  "metadata": {...}
}
```

### 3. 分级处理

```python
# 伪代码
score = report["risk_assessment"]["risk_score"] or 0
sev = report["risk_assessment"]["severity"]
issues = report["issues"]

if sev in ("CRITICAL", "HIGH") or score >= 70:
    # ❌ 拒绝安装，上报 boss
    return BLOCK + full report
elif sev == "MEDIUM" or score >= 40:
    # ⚠️ 列出 issues，让 boss 拍板
    return summary of issues
else:
    # ✅ 静默通过
    return PASS
```

### 4. 输出报告模板

**通过**：
> ✅ `<skill-name>` 扫描通过：LOW / SAFE（score=X），未发现需关注问题。

**中等风险**：
> ⚠️ `<skill-name>` 扫描 MEDIUM（score=X），N 个问题待你确认：
> 1. **[MEDIUM] MCP Least Privilege** — SKILL.md 缺 `permissions` 字段。修复：加 permissions 声明。
> 2. ...
> 要装吗？

**高危/拒绝**：
> 🚫 `<skill-name>` 扫描 **CRITICAL/HIGH**（score=X），**建议不安装**。问题：
> 1. **[CRITICAL] data-exfiltration** — 检出 `<file>:<line>` 通过 `<channel>` 外发数据 ...
> 必须人工裁决。

## 批量扫描（基线 / 巡检）

```bash
source /root/cakemonster/skills/skillspector/.venv/bin/activate
mkdir -p /root/.hermes/profiles/news-friday/scan-reports/<DATE>
for d in /root/cakemonster/skills/*/; do
  name=$(basename "$d")
  [ "$name" = "skillspector" ] && continue  # 跳过扫描器自己
  skillspector scan "$d" --no-llm --format json \
    -o "/root/.hermes/profiles/news-friday/scan-reports/<DATE>/${name}.json" 2>&1
done
```

**禁止扫的对象**：
- `skillspector/`（自己）
- `skillspector-scan/`（自己这个 skill）

## LLM 阶段（仅在以下情况启用）

**绝不**自动启用。仅当：
- 用户明确说"用 LLM 跑一下"
- 静态阶段高危，需要更深入语义分析时，**先问用户**同意

启用方式：
```bash
SKILLSPECTOR_PROVIDER=anthropic \
ANTHROPIC_API_KEY=<KEY> \
skillspector scan <PATH> --format json -o <REPORT.json>
# 不要加 --no-llm
```

**再次强调**：绝对不允许把 `private-skills/` 任何内容发给 LLM。

## 常见 issue 模式（已观察到）

- **LP3 (MCP Least Privilege, MEDIUM)**：SKILL.md 缺 `permissions` 声明。**普遍存在，几乎无害**，修复方法是加 permissions 字段。
- 其他模式需要逐个看 `explanation` 和 `remediation`。

## 失败处理

- **venv 激活失败** → 按"工具准备"重建
- **扫描超时** → 可能是大仓库，加 `--verbose` 看进度，或缩小目录范围
- **JSON 解析失败** → 用 `--format markdown` 看可读输出，或读 `metadata` 字段排查

## 集成进新 skill 安装流程

未来通过 `skillhub` / `npx skills add` 装新 skill 时，**安装完成立即扫描**。新 skill 流程模板：

```bash
# 1. 装
skillhub install <name>  # 或 git clone
# 2. 扫（必须）
source /root/cakemonster/skills/skillspector/.venv/bin/activate
skillspector scan <path> --no-llm --format json -o /tmp/scan-<name>.json
# 3. 分级处理（见上）
# 4. 通过 → 链接到 Hermes skills 目录
# 5. 不通过 → 删掉或上报
```

## 已知局限

- 静态扫描不分析代码运行时行为，部分恶意逻辑可能漏报
- 误报常见（特别是 LP3），以 `severity` + `confidence` 综合判断
- 不替代人工 review，特别是 `private-skills` 的新内容
