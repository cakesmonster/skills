#!/usr/bin/env python3
"""
Z-Library 书籍下载 - 使用 CloakBrowser 绕过 Cloudflare
优先 EPUB 格式，自动保存到 ~/Downloads/zlib/
"""

import sys
import os
import re
import time
from pathlib import Path

os.environ['http_proxy'] = 'http://127.0.0.1:7890'
os.environ['https_proxy'] = 'http://127.0.0.1:7890'
os.environ['CLOAKBROWSER_BINARY_PATH'] = '/root/.cloakbrowser/chromium-146.0.7680.177.5/chrome'

try:
    from cloakbrowser import launch_persistent_context
except ImportError:
    print("❌ CloakBrowser 未安装")
    sys.exit(1)


class ZLibraryDownloader:
    def __init__(self):
        self.downloads_dir = Path.home() / "Downloads" / "zlib"
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir = Path.home() / ".zlibrary"
        self.storage_state = self.config_dir / "storage_state.json"

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名非法字符"""
        name = re.sub(r'[<>:"/\\|?*\t]', '_', name)
        name = re.sub(r'_{3,}', '_', name)
        return name.strip('._ ')

    def _extract_book_title(self, page) -> str:
        """从页面提取书名"""
        try:
            title = page.title()
            # 格式: "书名 | 作者 | download on Z-Library"
            main_title = title.split('|')[0].strip()
            main_title = main_title.split(' - ')[0].strip()
            return self._sanitize_filename(main_title)
        except:
            return ""

    def download(self, url: str, prefer_format='epub') -> Path | None:
        print("=" * 70)
        print(f"🌐 Z-Library 书籍下载（CloakBrowser + Cloudflare 绕过）")
        print(f"📖 目标: {url}")
        print(f"📦 优先格式: {prefer_format.upper()}")
        print("=" * 70)

        if not self.storage_state.exists():
            print("❌ 未找到会话状态")
            print("💡 请先运行: python3 ~/cakemonster/skills/zlib-download/scripts/login.py <邮箱> <密码>")
            return None

        print("✅ 使用已保存的会话")

        browser = launch_persistent_context(
            user_data_dir=str(self.config_dir / "browser_profile"),
            headless=False,
            accept_downloads=True,
            args=['--disable-blink-features=AutomationControlled']
        )

        page = browser.pages[0] if browser.pages else browser.new_page()
        page.set_default_timeout(60000)

        try:
            print("📖 访问书籍页面...")
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            print("⏳ 等待 Cloudflare 验证和页面加载...")
            page.wait_for_timeout(8000)

            title = self._extract_book_title(page)
            print(f"📚 书名: {title}")

            # 提取下载链接
            dl_link = page.query_selector('a.addDownloadedBook')
            if not dl_link:
                print("❌ 未找到下载链接")
                page.screenshot(path='/tmp/zlib-debug.png')
                browser.close()
                return None

            href = dl_link.get_attribute('href') or ''
            link_text = dl_link.inner_text() or ''

            # 判断格式
            detected_format = 'epub'
            if 'pdf' in link_text.lower():
                detected_format = 'pdf'
            elif prefer_format == 'pdf':
                detected_format = 'pdf'

            print(f"✅ 下载链接: {link_text} -> {href[:60]}")

            # 构建下载 URL
            dl_url = href if href.startswith('http') else f"https://zh.zlib.li{href}"

            # 构造目标文件名
            ext = '.epub' if detected_format == 'epub' else '.pdf'
            safe_title = self._sanitize_filename(title) if title else 'book'
            target_filename = f"{safe_title}{ext}"
            final_path = self.downloads_dir / target_filename

            print(f"⬇️  开始下载: {target_filename}")

            # 使用 expect_download 捕获下载
            with page.expect_download(timeout=60000) as dl_info:
                page.evaluate(f"window.location.href = '{dl_url}'")
                page.wait_for_timeout(5000)

            dl = dl_info.value
            dl.save_as(str(final_path))

            if final_path.exists():
                size_mb = final_path.stat().st_size / 1024 / 1024
                print(f"✅ 下载成功!")
                print(f"   文件: {final_path.name}")
                print(f"   大小: {size_mb:.2f} MB")
                browser.close()
                return final_path

            print("❌ 下载文件未找到")
            browser.close()
            return None

        except Exception as e:
            print(f"❌ 下载失败: {e}")
            import traceback
            traceback.print_exc()
            try:
                page.screenshot(path='/tmp/zlib-error.png')
            except:
                pass
            browser.close()
            return None


def main():
    if len(sys.argv) < 2:
        print("Z-Library 书籍下载（优先 EPUB）")
        print("用法: python3 download.py <Z-Library URL> [格式]")
        sys.exit(1)

    url = sys.argv[1]
    prefer_format = sys.argv[2] if len(sys.argv) > 2 else 'epub'

    downloader = ZLibraryDownloader()
    result = downloader.download(url, prefer_format)

    if result:
        print("")
        print("=" * 70)
        print(f"✅ 下载完成: {result.name}")
        print(f"📁 路径: {result}")
        print("=" * 70)
    else:
        print("❌ 下载失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
