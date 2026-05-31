#!/usr/bin/env python3
"""
小红书单篇笔记抓取器。
给定笔记链接或 note_id，抓取单篇笔记的完整内容。

用法:
    python3 scrape_note.py --note-id 6a0723eb00000000080241d3
    python3 scrape_note.py --url https://www.xiaohongshu.com/explore/6a0723eb00000000080241d3
    python3 scrape_note.py --url 'https://www.xiaohongshu.com/user/profile/UID/NOTE_ID?xsec_token=...'

输出:
    - JSON 到 stdout（默认）或 --output FILE
"""

import argparse
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright


def extract_note_id(url_or_id: str) -> str:
    """从 URL 或纯 ID 中提取 note_id（24 位 hex）。"""
    if re.match(r"^[a-f0-9]{24}$", url_or_id):
        return url_or_id
    # /explore/{note_id} 或 /user/profile/{uid}/{note_id}
    m = re.search(r"/(?:explore|user/profile/[a-f0-9]{24})/([a-f0-9]{24})", url_or_id)
    if m:
        return m.group(1)
    raise ValueError(f"无法从 '{url_or_id}' 中提取 note_id")


def parse_args():
    parser = argparse.ArgumentParser(description="小红书单篇笔记抓取器")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--note-id", help="笔记 ID（24 位 hex）")
    src.add_argument("--url", help="笔记完整 URL")
    parser.add_argument(
        "--cookie-file",
        default=os.path.expanduser("~/.hermes/data/xhs/cookies.json"),
        help="Cookie 文件路径",
    )
    parser.add_argument("--output", "-o", help="保存到文件（默认 stdout 输出 JSON）")
    return parser.parse_args()


def main():
    args = parse_args()
    note_id = extract_note_id(args.note_id or args.url)
    cookie_file = os.path.expanduser(args.cookie_file)

    if not os.path.exists(cookie_file):
        print(f"❌ Cookie 文件不存在: {cookie_file}", file=sys.stderr)
        print("   请先运行 login_qr.py 完成登录", file=sys.stderr)
        sys.exit(1)

    # 尝试从 URL 中提取 xsec_token
    xsec_token = ""
    if args.url and "xsec_token=" in args.url:
        m = re.search(r"xsec_token=([^&]+)", args.url)
        if m:
            xsec_token = m.group(1)

    # 构建详情页 URL
    if xsec_token:
        detail_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_user"
    else:
        detail_url = f"https://www.xiaohongshu.com/explore/{note_id}"

    print(f"🔍 抓取笔记: {detail_url}", file=sys.stderr)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            storage_state=cookie_file,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(3000)

            # 检查登录墙
            body = page.evaluate(
                "() => document.body?.innerText?.substring(0, 200) || ''"
            )
            if "登录即可查看" in body:
                print("❌ 需要登录，Cookie 可能已过期", file=sys.stderr)
                browser.close()
                sys.exit(1)

            # 提取内容
            content = page.evaluate(
                """() => {
                const desc = document.querySelector('#detail-desc');
                const noteText = document.querySelector('.note-text');
                const dateEl = document.querySelector('.date');
                const titleEl = document.querySelector('.title');
                const authorEl = document.querySelector('.username, [class*="nickname"]');
                const body = (desc?.textContent || noteText?.textContent || '').trim();
                return {
                    body: body,
                    date: dateEl?.textContent?.trim() || '',
                    title: titleEl?.textContent?.trim() || '',
                    author: authorEl?.textContent?.trim() || ''
                };
            }"""
            )

            body_text = content["body"]
            title = content["title"] or (
                body_text.split("\n")[0][:100] if body_text else "(empty)"
            )

            note_data = {
                "note_id": note_id,
                "title": title,
                "desc": body_text,
                "date": content.get("date", ""),
                "author": content.get("author", ""),
                "type": "normal",
                "scraped_at": int(time.time()),
            }

            # 输出
            json_str = json.dumps(note_data, ensure_ascii=False, indent=2)
            if args.output:
                with open(args.output, "w") as f:
                    f.write(json_str)
                print(f"✅ 已保存: {args.output} ({len(body_text)} 字)", file=sys.stderr)
            else:
                print(json_str)

        except Exception as e:
            print(f"❌ 抓取失败: {e}", file=sys.stderr)
            sys.exit(1)

        browser.close()


if __name__ == "__main__":
    main()
