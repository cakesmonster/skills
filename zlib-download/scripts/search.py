#!/usr/bin/env python3
"""
Z-Library 书籍搜索 - 用 CloakBrowser 搜索书籍并返回链接
"""

import sys
import os
from pathlib import Path

os.environ['http_proxy'] = 'http://127.0.0.1:7890'
os.environ['https_proxy'] = 'http://127.0.0.1:7890'
os.environ['CLOAKBROWSER_BINARY_PATH'] = '/root/.cloakbrowser/chromium-146.0.7680.177.5/chrome'

try:
    from cloakbrowser import launch_persistent_context
except ImportError:
    print("❌ CloakBrowser 未安装")
    sys.exit(1)


def search(query: str) -> list[tuple[str, str]]:
    """搜索书籍，返回 [(url, title), ...]"""
    config_dir = Path.home() / ".zlibrary"
    storage_state = config_dir / "storage_state.json"

    if not storage_state.exists():
        print("❌ 未登录（找不到会话文件）")
        print("请先运行: python3 login.py <邮箱> <密码>")
        return []

    browser = launch_persistent_context(
        user_data_dir=str(config_dir / "browser_profile"),
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )

    page = browser.pages[0]
    page.set_default_timeout(60000)

    results = []

    try:
        print(f"🔍 搜索: {query}")

        # 先访问首页
        page.goto("https://zh.zlib.li/", wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(5000)

        # 展开搜索栏
        page.evaluate("openSearchLine()")
        page.wait_for_timeout(1500)

        # 输入搜索词并提交
        page.evaluate(f"""
            const input = document.querySelector('#searchFieldx');
            if (input) {{
                input.value = {repr(query)};
                const form = input.closest('form');
                if (form) form.submit();
            }}
        """)
        page.wait_for_timeout(6000)

        print(f"📄 结果页: {page.url}")

        # 提取书籍链接
        links = page.query_selector_all('a[href*="/book/"]')
        seen = set()
        for link in links:
            href = link.get_attribute('href') or ''
            # 清理掉 query string 中的 dsource 等参数
            clean_href = href.split('?')[0]
            if clean_href not in seen:
                seen.add(clean_href)
                try:
                    title = link.inner_text()[:80].strip()
                except:
                    title = ''
                if title:
                    results.append((f"https://zh.zlib.li{clean_href}", title))

    except Exception as e:
        print(f"❌ 搜索失败: {e}")
    finally:
        browser.close()

    return results


def main():
    if len(sys.argv) < 2:
        print("Z-Library 书籍搜索")
        print("用法: python3 search.py <书名>")
        sys.exit(1)

    query = sys.argv[1]
    results = search(query)

    print(f"\n找到 {len(results)} 个结果:")
    for i, (url, title) in enumerate(results, 1):
        print(f"\n{i}. {title}")
        print(f"   {url}")

    if results:
        print(f"\n下载命令:")
        print(f"  python3 download.py \"{results[0][0]}\"")


if __name__ == "__main__":
    main()
