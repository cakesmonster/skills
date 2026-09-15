#!/usr/bin/env bash
# Ad-hoc verification for the product-hunt fetch fix (2026-09-15).
# Checks the changed behaviour of:
#   skills/product-hunt/scripts/ph_fetch.sh       (proxy path + API/feed output)
#   skills/product-hunt/scripts/ph_cron_collect.sh (cron pre-run contract)
#   ~/.hermes/profiles/news-friday/scripts/ph_cron_collect.sh (wrapper)
# Not a test suite — a focused smoke+contract check. Run: bash <thisfile>
set -uo pipefail

SKILL=/root/cakemonster/skills/product-hunt/scripts
WRAP=/root/.hermes/profiles/news-friday/scripts/ph_cron_collect.sh
ENV_FILE=/root/.hermes/profiles/news-friday/.env.ph
PASS=0; FAIL=0
ok()   { echo "  PASS: $1"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
check(){ if eval "$2"; then ok "$1"; else bad "$1  [$2]"; fi; }

echo "== 1. ph_fetch.sh API path (proxy required on this host) =="
for m in daily weekly monthly; do
  err=$(mktemp); out=$(bash "$SKILL/ph_fetch.sh" "$m" 2>"$err")
  rc=$?
  check "$m: exit 0"                   "[ $rc -eq 0 ]"
  check "$m: proxy probe succeeded"    "grep -q 'proxy OK' '$err'"
  check "$m: 20 JSON lines"            "[ \$(printf '%s\n' \"\$out\" | wc -l) -eq 20 ]"
  check "$m: source=api + votes>0"     "printf '%s\n' \"\$out\" | python3 -c 'import sys,json; L=[json.loads(l) for l in sys.stdin if l.strip()]; sys.exit(0 if L and all(x[\"source\"]==\"api\" and (x[\"votes\"] or 0)>0 for x in L) else 1)'"
  rm -f "$err"
done

echo "== 2. ph_fetch.sh feed fallback =="
out=$(bash "$SKILL/ph_fetch.sh" feed 2>/dev/null); rc=$?
check "feed: exit 0"            "[ $rc -eq 0 ]"
check "feed: source=feed lines" "printf '%s\n' \"\$out\" | grep -q '\"source\": \"feed\"'"

echo "== 3. collector contract (runs with a sanitized env, like the scheduler) =="
clog=$(mktemp)
env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root LANG=C.UTF-8 \
  bash "$WRAP" >"$clog" 2>/dev/null; rc=$?
check "collector: exit 0"                 "[ $rc -eq 0 ]"
check "collector: stdout non-empty (empty => scheduler skips the run)" "[ -s '$clog' ]"
check "collector: token_len=43"           "grep -q '### token_len=43' '$clog'"
for m in daily weekly monthly; do
  check "collector: ### SECTION $m present" "grep -q '^### SECTION $m\$' '$clog'"
done
check "collector: no FAILED section"      "! grep -q 'FAILED' '$clog'"
check "collector: sections terminated (### END)" "grep -q '^### END' '$clog'"
check "collector: daily capped at 12 lines" "[ \$(sed -n '/^### SECTION daily/,/^### SECTION weekly/p' '$clog' | grep -c '\"rank\"') -eq 12 ]"
check "collector: weekly capped at 10"      "[ \$(sed -n '/^### SECTION weekly/,/^### SECTION monthly/p' '$clog' | grep -c '\"rank\"') -eq 10 ]"
check "collector: utm params stripped"      "! grep -q 'utm_' '$clog'"
check "collector: valid JSONL under each section" \
  "python3 - '$clog' <<'PY'
import json,sys
bad=0
for line in open(sys.argv[1]):
    line=line.strip()
    if line.startswith('{'):
        try: json.loads(line)
        except Exception: bad=1
sys.exit(bad)
PY"
echo "  (payload: $(wc -c <"$clog") bytes, $(grep -c '"rank"' "$clog") products)"
rm -f "$clog"

echo "== 4. degraded path: bogus token => honest FAILED + feed fallback, still exit 0 =="
bogus=$(mktemp); echo 'PH_DEV_TOKEN=this-token-is-definitely-invalid' >"$bogus"
dlog=$(mktemp)
# env -i mirrors the scheduler: _sanitize_subprocess_env strips credentials, so the
# collector must not rely on anything inherited from this shell (real leak found here).
env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root LANG=C.UTF-8 \
  PH_ENV_FILE="$bogus" bash "$WRAP" >"$dlog" 2>/dev/null; rc=$?
check "degraded: exit 0 (never crashes the tick)"  "[ $rc -eq 0 ]"
check "degraded: daily marked FAILED, not silently empty" "grep -q '^### SECTION daily FAILED' '$dlog'"
check "degraded: feed fallback attempted"          "grep -q '### SECTION feed (FALLBACK' '$dlog'"
check "degraded: no fabricated votes in feed block" \
  "[ \$(sed -n '/### SECTION feed/,\$p' '$dlog' | grep -c '\"votes\": [0-9]') -eq 0 ]"
rm -f "$bogus" "$dlog"

echo "== 5. missing env file: warn, feed-degraded sections labelled, still exit 0 =="
mlog=$(mktemp)
env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root LANG=C.UTF-8 \
  PH_ENV_FILE=/tmp/does-not-exist-ph bash "$WRAP" >"$mlog" 2>/dev/null; rc=$?
check "no-env: exit 0"        "[ $rc -eq 0 ]"
check "no-env: WARN emitted"  "grep -q 'WARN: env file not found' '$mlog'"
check "no-env: feed-degraded sections labelled" "grep -q '段是 feed 降级数据' '$mlog'"
check "no-env: no fabricated votes in labelled sections" \
  "[ \$(sed -n '/^### SECTION daily/,/^### SECTION weekly/p' '$mlog' | grep -c '\"votes\": [0-9]') -eq 0 ]"
rm -f "$mlog"

echo
echo "== RESULT: $PASS passed, $FAIL failed =="
[ "$FAIL" -eq 0 ]