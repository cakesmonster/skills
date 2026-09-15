#!/usr/bin/env bash
# product-hunt daily/weekly/monthly leaderboard fetcher
# Usage:
#   ./ph_fetch.sh daily              # last 24h top posts by votes
#   ./ph_fetch.sh weekly             # last 7 days
#   ./ph_fetch.sh monthly            # last 30 days
#   ./ph_fetch.sh feed               # no-key fallback: Atom feed (no votes/ranking)
#   PH_RANKING=ai ./ph_fetch.sh weekly   # filter by topic slug
#
# Env: PH_DEV_TOKEN (preferred; dashboard "Developer Token" - used directly as Bearer)
#      PH_API_KEY + PH_API_SECRET (fallback: client_credentials exchange, cached in /tmp)
#      PH_PROXY (default http://127.0.0.1:7890 — REQUIRED on this host, see below)
# Output: JSON lines to stdout: rank,name,tagline,votes,comments,url,created,topics,source
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-daily}"
GRAPHQL="https://api.producthunt.com/v2/api/graphql"
TOKEN_URL="https://api.producthunt.com/v2/oauth/token"
TOKEN_CACHE="/tmp/.ph_token"
DEV_TOKEN="${PH_DEV_TOKEN:-}"
API_KEY="${PH_API_KEY:-}"
API_SECRET="${PH_API_SECRET:-}"
TOPIC="${PH_RANKING:-}"

# ---------------------------------------------------------------------------
# Network path (2026-09-15 finding, see SKILL.md)
# Direct egress to producthunt.com / api.producthunt.com is DEAD from this host:
# DNS resolves the Cloudflare edge to AAAA only, the box has no IPv6 route
# (only ::1 + fe80), and the IPv4 443 handshake hangs -> every curl times out
# at --max-time with http_code 000. The local mihomo proxy reaches both fine
# (feed 200 in 0.2s, GraphQL 200 in 0.4s). So: probe the proxy once, use it if
# alive, otherwise fall back to a direct attempt (in case egress is restored).
PH_PROXY="${PH_PROXY:-http://127.0.0.1:7890}"
CURL_PROXY=""   # becomes "-x http://127.0.0.1:7890" (unquoted expansion = 2 args)
if [[ -n "$PH_PROXY" ]]; then
  if curl -s -o /dev/null --max-time 8 -x "$PH_PROXY" "$GRAPHQL"; then
    CURL_PROXY="-x $PH_PROXY"
    echo "INFO: proxy OK ($PH_PROXY)" >&2
  else
    echo "WARN: proxy $PH_PROXY unreachable, trying direct" >&2
  fi
fi
# shellcheck disable=SC2086
curl_ph() { curl -s $CURL_PROXY "$@"; }

fetch_feed() {
  curl_ph -L --max-time 30 \
    -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36" \
    "https://www.producthunt.com/feed" > /tmp/.ph_feed.xml
  if ! grep -q "<entry" /tmp/.ph_feed.xml 2>/dev/null; then
    echo "ERROR: feed fetch returned no <entry> (size $(wc -c < /tmp/.ph_feed.xml) bytes)" >&2
    exit 3
  fi
  python3 "$SCRIPT_DIR/parse_feed.py" /tmp/.ph_feed.xml
}

if [[ "$MODE" == "feed" ]]; then fetch_feed; exit 0; fi

if [[ -z "$DEV_TOKEN" && ( -z "$API_KEY" || -z "$API_SECRET" ) ]]; then
  echo "ERROR: PH_DEV_TOKEN (or PH_API_KEY/PH_API_SECRET) not set. Falling back to feed (no votes)." >&2
  fetch_feed
  exit $?
fi

get_token() {
  if [[ -n "$DEV_TOKEN" ]]; then echo "$DEV_TOKEN"; return; fi
  if [[ -s "$TOKEN_CACHE" ]]; then cat "$TOKEN_CACHE"; return; fi
  local tok
  tok=$(curl_ph --max-time 20 -X POST "$TOKEN_URL" \
    -d grant_type=client_credentials \
    -d client_id="$API_KEY" \
    -d client_secret="$API_SECRET" \
    | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
  if [[ -z "$tok" ]]; then echo "ERROR: token exchange failed" >&2; exit 1; fi
  echo "$tok" > "$TOKEN_CACHE"
  echo "$tok"
}

case "$MODE" in
  daily)   export PH_AFTER=$(date -u -d '-1 day' +%Y-%m-%dT00:00:00Z) ;;
  weekly)  export PH_AFTER=$(date -u -d '-7 day' +%Y-%m-%dT00:00:00Z) ;;
  monthly) export PH_AFTER=$(date -u -d '-30 day' +%Y-%m-%dT00:00:00Z) ;;
  *) echo "ERROR: mode must be daily|weekly|monthly|feed" >&2; exit 2 ;;
esac
export PH_NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
export PH_TOPIC="$TOPIC"
QUERY=$(python3 "$SCRIPT_DIR/mk_query.py")

do_fetch() {
  curl_ph --max-time 25 -X POST "$GRAPHQL" \
    -H "Authorization: Bearer ${1}" \
    -H "Content-Type: application/json" \
    --data "$QUERY"
}

RESP=$(do_fetch "$(get_token)")
if [[ -z "$RESP" ]]; then echo "ERROR: empty API response (network?)" >&2; exit 4; fi
if echo "$RESP" | grep -q '"errors"'; then
  if [[ -z "$DEV_TOKEN" ]]; then rm -f "$TOKEN_CACHE"; RESP=$(do_fetch "$(get_token)"); fi
fi

echo "$RESP" | python3 "$SCRIPT_DIR/parse_posts.py"