#!/bin/bash
# GitHub Trending Daily Report — 日榜+周榜+月榜合并推送
# 用法: bash github-trending-daily.sh
set -euo pipefail

cd /usr/local/lib/hermes-agent
source venv/bin/activate

export PYTHONPATH="venv/lib/python3.11/site-packages${PYTHONPATH:+:$PYTHONPATH}"
python3 -c "
import gh_trending

for period in ['daily', 'weekly', 'monthly']:
    repos = gh_trending.scrape(period)
    print(gh_trending.fmt_markdown(period, repos))
    print()
"
