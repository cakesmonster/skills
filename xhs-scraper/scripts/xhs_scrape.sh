#!/bin/bash
# =============================================================
# 小红书博主笔记自动抓取器 v2.1 (playwright-cli)
# 修复: 去掉 set -e，抑制 verbose 输出，大超时
# =============================================================

USER_ID="${1:?Usage: $0 <user_id> [data_dir]}"
DATA_DIR="${2:-$HOME/.hermes/data/xhs/$USER_ID}"
STATE_FILE="$HOME/.hermes/data/xhs/state.json"
CONFIG_FILE="$HOME/.hermes/data/xhs/cli.config.json"
SESSION="xhs-$$"

mkdir -p "$DATA_DIR"
IDS_FILE="$DATA_DIR/note_ids.json"
META_FILE="$DATA_DIR/meta.json"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
die() { log "❌ $*"; pw close 2>/dev/null; exit 1; }
# wrapper: suppress playwright-cli verbose output, only keep result
pw() { playwright-cli -s="$SESSION" "$@" 2>/dev/null | grep -vE '^###|^```|^await |^- ' | grep -v '^$' || true; }

# ── 启动 ──
log "启动浏览器..."
pw open --config="$CONFIG_FILE"
sleep 1

# ── 加载登录态 ──
if [ -f "$STATE_FILE" ]; then
    log "加载登录态..."
    pw state-load "$STATE_FILE"
fi

# ── 访问主页 (用 run-code 设置 90s 超时) ──
log "访问主页..."
pw run-code "async page => { page.setDefaultNavigationTimeout(90000); await page.goto('https://www.xiaohongshu.com/user/profile/$USER_ID', { waitUntil: 'domcontentloaded' }); }"
sleep 4

# 检查登录墙
PAGE_TITLE=$(playwright-cli -s="$SESSION" --raw eval "document.title" 2>/dev/null || echo "")
log "页面标题: $PAGE_TITLE"

if echo "$PAGE_TITLE" | grep -qi "登录"; then
    die "登录态过期"
fi

# 获取昵称
NICKNAME=$(playwright-cli -s="$SESSION" --raw eval "document.querySelector('.username')?.textContent || ''" 2>/dev/null | tr -d '"' || echo "未知")
log "博主: $NICKNAME"

# ── 滚动加载 ──
log "滚动加载..."
for i in $(seq 1 6); do
    pw eval "window.scrollTo(0, document.body.scrollHeight)"
    sleep 2
done

# ── 提取笔记 ID ──
log "提取笔记 ID..."
RAW_IDS=$(playwright-cli -s="$SESSION" --raw eval "
(() => {
    const s = new Set();
    document.querySelectorAll('a').forEach(a => {
        if (a.href.includes('/$USER_ID/')) {
            const id = a.href.split('?')[0].split('/').pop();
            if (id.length === 24) s.add(id);
        }
    });
    return JSON.stringify([...s]);
})()
" 2>/dev/null || echo "[]")

NOTE_COUNT=$(echo "$RAW_IDS" | python3 -c "import sys,json; print(len(json.loads(sys.stdin.read())))" 2>/dev/null || echo "0")
log "页面找到 $NOTE_COUNT 篇笔记"

if [ "$NOTE_COUNT" -eq 0 ]; then
    die "未提取到笔记（可能页面结构变化）"
fi

# ── 对比已有 ──
if [ -f "$IDS_FILE" ]; then
    EXISTING=$(python3 -c "
import json
with open('$IDS_FILE') as f:
    print(' '.join(n['note_id'] for n in json.load(f)))
" 2>/dev/null || echo "")
fi

NEW_STR=$(echo "$RAW_IDS" | python3 -c "
import sys, json
all_ids = set(json.loads(sys.stdin.read()))
existing = set('${EXISTING}'.split())
new = sorted(all_ids - existing - {''}, reverse=True)
print(len(new))
print(json.dumps(new))
" 2>/dev/null)

NEW_COUNT=$(echo "$NEW_STR" | head -1)
NEW_IDS=$(echo "$NEW_STR" | tail -1)

log "新笔记: $NEW_COUNT 篇"

if [ "$NEW_COUNT" -eq 0 ]; then
    log "✅ 没有新笔记"
    pw state-save "$STATE_FILE"
    pw close
    exit 0
fi

# ── 抓取新笔记 ──
log "开始抓取 $NEW_COUNT 篇..."
echo "$NEW_IDS" | python3 -c "
import sys, json
ids = json.loads(sys.stdin.read())
for nid in ids:
    print(nid)
" | while read -r NOTE_ID; do
    log "  📝 $NOTE_ID"

    # 跳转详情
    URL="https://www.xiaohongshu.com/explore/$NOTE_ID"
    pw run-code "async page => { await page.goto('$URL', { waitUntil: 'domcontentloaded', timeout: 30000 }); }"
    sleep 3

    # 提取内容
    BODY=$(playwright-cli -s="$SESSION" --raw eval "
    (() => {
        const desc = document.querySelector('#detail-desc');
        const note = document.querySelector('.note-text');
        const date = document.querySelector('.date');
        const body = (desc?.textContent || note?.textContent || '').trim();
        return JSON.stringify({
            body: body,
            date: date?.textContent?.trim() || '',
            title: body.split('\n')[0].substring(0, 100) || '(empty)'
        });
    })()
    " 2>/dev/null || echo '{"body":"","date":"","title":"(失败)"}')

    # 保存
    python3 -c "
import json, time
c = json.loads('''$BODY''')
d = {
    'note_id': '$NOTE_ID',
    'title': c.get('title', ''),
    'desc': c.get('body', ''),
    'date': c.get('date', ''),
    'scraped_at': int(time.time())
}
with open('$DATA_DIR/${NOTE_ID}.json', 'w') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
" 2>/dev/null

    CHARS=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.loads(sys.stdin.read()).get('body','')))" 2>/dev/null || echo "0")
    log "    ✅ ${CHARS} 字"
    sleep 1
done

# ── 更新索引 ──
log "更新索引..."
python3 -c "
import json, time, os

try:
    with open('$IDS_FILE') as f:
        existing = json.load(f)
except:
    existing = []

seen = {e['note_id'] for e in existing}
import glob
for f in sorted(glob.glob('$DATA_DIR/*.json'), key=os.path.getmtime, reverse=True):
    if 'note_ids' in f or 'meta' in f: continue
    with open(f) as fh:
        d = json.load(fh)
    nid = d.get('note_id', '')
    if nid and nid not in seen:
        existing.insert(0, {
            'note_id': nid,
            'display_title': d.get('title', '')[:80],
            'type': 'normal',
            'scraped_at': d.get('scraped_at', 0)
        })
        seen.add(nid)

with open('$IDS_FILE', 'w') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)

with open('$META_FILE', 'w') as f:
    json.dump({
        'profile': {'user_id': '$USER_ID', 'nickname': '$NICKNAME'},
        'last_scrape': {
            'timestamp': int(time.time()),
            'datetime': time.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
            'latest_note_id': existing[0]['note_id'] if existing else '',
            'total_notes': len(existing)
        }
    }, f, ensure_ascii=False, indent=2)

print(f'✅ 索引更新: {len(existing)} 篇总计')
"

# ── 保存登录态 ──
pw state-save "$STATE_FILE"
log "登录态已刷新"

# ── 关闭 ──
pw close 2>/dev/null

log "✅ 完成！新增 $NEW_COUNT 篇笔记"
