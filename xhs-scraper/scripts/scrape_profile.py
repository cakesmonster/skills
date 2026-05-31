#!/usr/bin/env python3
"""
小红书博主主页笔记抓取器 — 通用版。
给定任意博主主页链接或 user_id，抓取其所有可见笔记。

用法:
    # 抓取全部可见笔记
    python3 scrape_profile.py --uid <user_id>
    python3 scrape_profile.py --url https://www.xiaohongshu.com/user/profile/<user_id>

    # 增量模式（跳过已有数据）
    python3 scrape_profile.py --uid <user_id> --data-dir ~/.hermes/data/xhs/博主名/

    # 仅列出新笔记 ID（不抓详情）
    python3 scrape_profile.py --uid <user_id> --list-only

    # 限制抓取数量
    python3 scrape_profile.py --uid <user_id> --max-notes 10
"""

import argparse
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright


def extract_user_id(url_or_id: str) -> str:
    """从 URL 或纯 ID 中提取小红书 user_id (24 位 hex)。"""
    # 直接是 24 位 hex
    if re.match(r"^[a-f0-9]{24}$", url_or_id):
        return url_or_id
    # 从 URL 提取
    m = re.search(r"/user/profile/([a-f0-9]{24})", url_or_id)
    if m:
        return m.group(1)
    raise ValueError(f"无法从 '{url_or_id}' 中提取 user_id，请提供 24 位 hex 或完整主页链接")


def load_existing_ids(data_dir: str) -> set:
    """加载已有笔记 ID 集合（用于增量模式）。"""
    ids_path = os.path.join(data_dir, "note_ids.json")
    if not os.path.exists(ids_path):
        return set()
    with open(ids_path) as f:
        return {item.get("note_id", "") for item in json.load(f)}


def parse_args():
    parser = argparse.ArgumentParser(description="小红书博主主页笔记抓取器")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--uid", help="博主 user_id（24 位 hex）")
    src.add_argument("--url", help="博主主页完整 URL")
    parser.add_argument(
        "--cookie-file",
        default=os.path.expanduser("~/.hermes/data/xhs/cookies.json"),
        help="Cookie 文件路径",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="数据保存目录（默认不保存；启用后自动增量模式）",
    )
    parser.add_argument(
        "--max-notes",
        type=int,
        default=50,
        help="最多抓取篇数（默认 50）",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="仅列出笔记 ID 和标题，不抓取详情",
    )
    parser.add_argument(
        "--scroll-times",
        type=int,
        default=5,
        help="滚动加载次数（默认 5）",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    user_id = extract_user_id(args.uid or args.url)
    profile_url = f"https://www.xiaohongshu.com/user/profile/{user_id}"
    cookie_file = os.path.expanduser(args.cookie_file)

    # 检查 Cookie
    if not os.path.exists(cookie_file):
        print(f"❌ Cookie 文件不存在: {cookie_file}")
        print("   请先运行 login_qr.py 完成登录")
        sys.exit(1)

    # 增量模式
    existing_ids = set()
    if args.data_dir:
        os.makedirs(args.data_dir, exist_ok=True)
        existing_ids = load_existing_ids(args.data_dir)
        print(f"📚 已有 {len(existing_ids)} 篇笔记")

    print(f"🎯 目标博主: {profile_url}")

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

        # 打开主页
        print(f"\n🌐 打开主页...")
        try:
            page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            print("⚠️ 主页加载超时，尝试继续...")
        page.wait_for_timeout(4000)

        # 检查登录墙
        body = page.evaluate("() => document.body?.innerText?.substring(0, 300) || ''")
        if "登录即可查看" in body:
            print("❌ 未登录或 Cookie 过期，请重新运行 login_qr.py")
            browser.close()
            sys.exit(1)

        # 获取博主昵称
        nickname = page.evaluate(
            """() => {
            const el = document.querySelector('.username, [class*="nickname"], [class*="user-name"]');
            return el?.textContent?.trim() || '';
        }"""
        )
        print(f"👤 博主: {nickname or '(未获取到昵称)'}")

        # 滚动加载
        print(f"📜 滚动加载笔记 (×{args.scroll_times})...")
        for i in range(args.scroll_times):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

        # ── 核心修复：从主页链接格式提取笔记 ID ──
        # 笔记链接格式: /user/profile/{user_id}/{note_id}?xsec_token=...
        notes = page.evaluate(
            """(uid) => {
            const links = document.querySelectorAll('a[href*="/user/profile/' + uid + '/"]');
            const seen = new Map();
            links.forEach(a => {
                const h = a.href || '';
                // 匹配 /user/profile/{uid}/{note_id}?xsec_token=TOKEN
                const re = new RegExp('/user/profile/' + uid + '/([a-f0-9]+)\\\\?xsec_token=([^&]+)');
                const m = h.match(re);
                if (m && !seen.has(m[1])) {
                    seen.set(m[1], decodeURIComponent(m[2].replace(/&amp;/g, '&')));
                }
            });
            return Array.from(seen.entries()).map(([id, token]) => ({
                note_id: id,
                xsec_token: token
            }));
        }""",
            user_id,
        )

        print(f"\n📊 页面找到 {len(notes)} 篇笔记")

        # 增量过滤
        new_notes = [n for n in notes if n["note_id"] not in existing_ids]
        print(f"🆕 其中新笔记: {len(new_notes)} 篇")

        # 截取
        to_scrape = new_notes[: args.max_notes] if not args.list_only else notes[: args.max_notes]
        print(f"🔍 将处理: {len(to_scrape)} 篇\n")

        if args.list_only:
            # 仅列出
            for i, n in enumerate(to_scrape):
                marker = "🆕" if n["note_id"] not in existing_ids else "  "
                print(f"  [{i+1}] {marker} {n['note_id']}")
            browser.close()
            print(f"\n✅ 共 {len(notes)} 篇（新 {len(new_notes)} 篇）")
            return

        # 抓取详情
        if not new_notes:
            print("✅ 没有新笔记，已是最新。")
            browser.close()
            return

        scraped = []
        for i, note in enumerate(new_notes[: args.max_notes]):
            nid = note["note_id"]
            token = note["xsec_token"]
            detail_url = (
                f"https://www.xiaohongshu.com/explore/{nid}"
                f"?xsec_token={token}&xsec_source=pc_user"
            )
            print(f"  [{i+1}/{min(len(new_notes), args.max_notes)}] {nid}", end="")

            try:
                page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)

                content = page.evaluate(
                    """() => {
                    const desc = document.querySelector('#detail-desc');
                    const noteText = document.querySelector('.note-text');
                    const dateEl = document.querySelector('.date');
                    const titleEl = document.querySelector('.title');
                    const body = (desc?.textContent || noteText?.textContent || '').trim();
                    const title = titleEl?.textContent?.trim() || '';
                    return {
                        body: body,
                        date: dateEl?.textContent?.trim() || '',
                        title: title
                    };
                }"""
                )

                body = content["body"]
                note_title = content["title"] or (body.split("\n")[0][:100] if body else "(empty)")

                note_data = {
                    "note_id": nid,
                    "title": note_title,
                    "desc": body,
                    "date": content.get("date", ""),
                    "type": "normal",
                    "scraped_at": int(time.time()),
                }

                if args.data_dir:
                    note_path = os.path.join(args.data_dir, f"{nid}.json")
                    with open(note_path, "w") as f:
                        json.dump(note_data, f, ensure_ascii=False, indent=2)

                scraped.append(
                    {
                        "note_id": nid,
                        "display_title": note_title[:80],
                        "type": "normal",
                        "published_at": None,
                        "scraped_at": int(time.time()),
                    }
                )
                print(f"  ✅ ({len(body)} 字) {note_title[:60]}")

                time.sleep(1)  # 反爬节流

            except Exception as e:
                print(f"  ❌ {e}")

        # 更新 note_ids.json
        if args.data_dir and scraped:
            ids_path = os.path.join(args.data_dir, "note_ids.json")
            if os.path.exists(ids_path):
                with open(ids_path) as f:
                    all_ids = json.load(f)
            else:
                all_ids = []
            all_ids = scraped + all_ids
            with open(ids_path, "w") as f:
                json.dump(all_ids, f, ensure_ascii=False, indent=2)

            # 更新 meta.json
            meta_path = os.path.join(args.data_dir, "meta.json")
            meta = {
                "profile": {
                    "user_id": user_id,
                    "nickname": nickname,
                    "profile_url": profile_url,
                },
                "last_scrape": {
                    "timestamp": int(time.time()),
                    "datetime": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                    "latest_note_id": scraped[0]["note_id"],
                    "total_notes": len(all_ids),
                },
                "data_dir": args.data_dir,
            }
            with open(meta_path, "w") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

        # 刷新 Cookie
        context.storage_state(path=cookie_file)

        print(f"\n✅ 完成: {len(scraped)} 新笔记")
        for s in scraped:
            print(f"   {s['note_id']} — {s['display_title'][:60]}")

        browser.close()


if __name__ == "__main__":
    main()
