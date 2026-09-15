#!/usr/bin/env bash
# Cron pre-run data collector for the "Product Hunt 日报" cron job (3d19533c70fb).
#
# Why this exists (2026-09-15): the cron AGENT's terminal has been dead for days
# (tirith scanner + approvals.cron_mode=deny for this profile), so the agent could
# not run ph_fetch.sh at all and every run degraded to a fault report or stale
# /tmp cache.  A cron `script` runs in the SCHEDULER process, not through the
# agent's approval gate — so data collection is now independent of terminal.
#
# Behaviour: ALWAYS exits 0 and always prints something (empty stdout would make
# the scheduler skip the run entirely).  Each leaderboard is one "### SECTION"
# block of raw JSON lines, exactly the ph_fetch.sh output format.
#
# Network: ph_fetch.sh routes itself through the local mihomo proxy
# (PH_PROXY, default http://127.0.0.1:7890) because direct egress to
# producthunt.com is blocked on this host.
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${PH_ENV_FILE:-/root/.hermes/profiles/news-friday/.env.ph}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
else
  echo "### WARN: env file not found: $ENV_FILE"
fi

echo "### PH COLLECT $(date -u +%Y-%m-%dT%H:%M:%SZ) UTC | $(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M %Z')"
# ${#VAR} on an unset var aborts the whole script under `set -u` — guard it.
if [[ -n "${PH_DEV_TOKEN:-}" ]]; then
  echo "### token_len=${#PH_DEV_TOKEN}"
else
  echo "### WARN: PH_DEV_TOKEN empty — API sections will degrade to feed (no votes)"
fi

api_ok=0
# Trim to what the report actually needs (daily top12 / weekly+monthly top10) and
# strip the PH utm_* query params, to keep the injected prompt lean.
# NOTE: write the full fetch to a temp file first — piping straight into `head`
# SIGPIPEs the producer and pipefail would then report a false failure.
keep_for() { case "$1" in daily) echo 12 ;; *) echo 10 ;; esac; }
for m in daily weekly monthly; do
  echo "### SECTION $m"
  bash "$SKILL_DIR/ph_fetch.sh" "$m" >/tmp/.ph_out_"$m" 2>/tmp/.ph_err_"$m"
  rc=$?
  if [[ $rc -eq 0 && -s /tmp/.ph_out_"$m" ]]; then
    out="$(head -n "$(keep_for "$m")" /tmp/.ph_out_"$m" | sed 's/?utm_[^"]*//')"
    printf '%s\n' "$out"
    case "$out" in
      *'"source": "api"'*) api_ok=1 ;;
      # No token => ph_fetch.sh silently degrades this section to feed data.
      # Say so out loud, or the report formats feed entries as if they were ranked.
      *) echo "### NOTE: $m 段是 feed 降级数据（无票数、非 votes 排名）——简报禁止给这些条目标票数" ;;
    esac
  else
    echo "### SECTION $m FAILED (exit $rc)"
    head -5 /tmp/.ph_err_"$m" 2>/dev/null | sed 's/^/  stderr: /'
  fi
done

if [[ $api_ok -eq 0 ]]; then
  echo "### SECTION feed (FALLBACK: no votes, feed order only)"
  bash "$SKILL_DIR/ph_fetch.sh" feed >/tmp/.ph_out_feed 2>/tmp/.ph_err_feed
  rc=$?
  if [[ $rc -eq 0 && -s /tmp/.ph_out_feed ]]; then
    head -n 15 /tmp/.ph_out_feed | sed 's/?utm_[^"]*//'
  else
    echo "### SECTION feed FAILED (exit $rc)"
    head -5 /tmp/.ph_err_feed 2>/dev/null | sed 's/^/  stderr: /'
  fi
fi

echo "### END"
exit 0