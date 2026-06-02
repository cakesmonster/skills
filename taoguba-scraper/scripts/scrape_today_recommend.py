#!/usr/bin/env python3
"""淘股吧今日推荐抓取脚本

用法:
    python3 scrape_today_recommend.py                    # 抓取并输出JSON
    python3 scrape_today_recommend.py --pages 3          # 抓取3页
    python3 scrape_today_recommend.py --no-content       # 只取列表，不抓正文
    python3 scrape_today_recommend.py --output out.json  # 输出到文件
"""

import subprocess
import json
import re
import sys
import time
import argparse
from datetime import datetime

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
BASE_URL = "https://www.tgb.cn"
API_PATH = "/newIndex/getNowRecommend"
COOKIE_JAR = "/tmp/tgb_cookies.txt"
DATA_DIR = "/root/.hermes/data/taoguba"

HEADERS = [
    "-H", f"User-Agent: {USER_AGENT}",
    "-H", "Referer: https://www.tgb.cn/",
    "-H", "X-Requested-With: XMLHttpRequest",
]


def curl(url, cookie_jar=COOKIE_JAR, extra_args=None):
    cmd = ["curl", "-s", "-b", cookie_jar, "-c", cookie_jar] + HEADERS
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def get_cookies():
    """首次访问首页获取cookie"""
    out, err, rc = curl(BASE_URL)
    if rc != 0 or len(out) < 100:
        print(f"[ERROR] 首页访问失败 rc={rc}", file=sys.stderr)
        return False
    return True


def fetch_today_recommend(pages=2):
    """抓取今日推荐列表"""
    all_posts = []
    for page in range(1, pages + 1):
        url = f"{BASE_URL}{API_PATH}?pageNo={page}"
        out, err, rc = curl(url)
        if rc != 0 or not out:
            print(f"[ERROR] 第{page}页失败 rc={rc}", file=sys.stderr)
            continue
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            print(f"[ERROR] 第{page}页JSON解析失败", file=sys.stderr)
            continue
        if not data.get("status"):
            print(f"[WARN] 第{page}页 status=false", file=sys.stderr)
            continue
        posts = data.get("dto", {}).get("list", [])
        all_posts.extend(posts)
        time.sleep(0.5)

    # 去重
    seen = set()
    unique = []
    for p in all_posts:
        tid = p.get("newTopicID")
        if tid and tid not in seen:
            seen.add(tid)
            unique.append(p)
    return unique


def extract_content(html, max_len=3000):
    """从HTML中提取帖子正文"""
    start = html.find('class="article-text')
    if start < 0:
        start = html.find('id="first"')
    tag_end = html.find('>', start) if start >= 0 else -1
    if tag_end < 0:
        return "[无法定位正文]"

    end = html.find('class="article-reward', tag_end)
    if end < 0:
        end = html.find('class="article-topic"', tag_end)
    if end < 0:
        end = html.find('<div class="article', tag_end + 10)
    if end < 0:
        end = len(html)

    raw = html[tag_end + 1:end]
    raw = re.sub(r'<br\s*/?>', '\n', raw)
    raw = re.sub(r'<a[^>]*>([^<]*)</a>', r'\1', raw)
    raw = re.sub(r'<img[^>]*>', '[图]', raw)
    raw = re.sub(r'<[^>]+>', '', raw)
    raw = raw.strip()

    if len(raw) > max_len:
        raw = raw[:max_len] + "\n... [截断]"
    return raw


def fetch_post_content(new_topic_id):
    """抓取单篇帖子内容"""
    url = f"{BASE_URL}/a/{new_topic_id}"
    out, err, rc = curl(url)
    if rc != 0 or not out:
        return f"[抓取失败: rc={rc}]"
    return extract_content(out)


def main():
    parser = argparse.ArgumentParser(description="淘股吧今日推荐抓取")
    parser.add_argument("--pages", type=int, default=2, help="抓取页数（每页15条）")
    parser.add_argument("--no-content", action="store_true", help="只取列表，不抓正文")
    parser.add_argument("--output", type=str, help="输出文件路径")
    parser.add_argument("--max-len", type=int, default=3000, help="正文截断长度")
    args = parser.parse_args()

    print("[INFO] 获取cookie...", file=sys.stderr)
    if not get_cookies():
        sys.exit(1)

    print(f"[INFO] 抓取今日推荐（{args.pages}页）...", file=sys.stderr)
    posts = fetch_today_recommend(args.pages)
    print(f"[INFO] 去重后 {len(posts)} 篇", file=sys.stderr)

    results = []
    for i, p in enumerate(posts):
        tid = p.get("newTopicID")
        subject = p.get("subject", "")[:100]
        username = p.get("userName", "?")
        views = p.get("totalViewNum", 0)
        replies = p.get("totalReplyNum", 0)
        subinfo = p.get("subinfo", "") or ""
        dt = p.get("dateTime")
        if dt:
            dt_str = datetime.fromtimestamp(dt / 1000).strftime("%Y-%m-%d %H:%M")
        else:
            dt_str = "?"

        item = {
            "idx": i + 1,
            "subject": subject,
            "username": username,
            "views": views,
            "replies": replies,
            "datetime": dt_str,
            "subinfo": subinfo[:200],
            "url": f"{BASE_URL}/a/{tid}",
            "newTopicID": tid,
        }

        if not args.no_content:
            content = fetch_post_content(tid)
            item["content"] = content[:args.max_len]
            clen = len(content)
        else:
            clen = 0

        bar = f"[{i+1}/{len(posts)}]"
        print(f"{bar} {subject[:50]:50s} | {username:16s} | {views:>6}阅 | {clen}字",
              file=sys.stderr)
        results.append(item)
        time.sleep(0.3)

    output = json.dumps(results, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[INFO] 已写入 {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
