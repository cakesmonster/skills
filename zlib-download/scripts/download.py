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
            # CF challenge 可能要 60-90s（首页 5s，book 页要重过），轮询直到 title 稳定
            for _ in range(35):
                page.wait_for_timeout(3000)
                cur_title = page.title() or ''
                if 'Just a moment' not in cur_title and cur_title.strip():
                    break
            # 给页面稳定时间（防跨域跳转中查询）
            page.wait_for_timeout(3000)

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

            # 判断格式（支持 epub / pdf / mobi）
            text_lower = link_text.lower()
            if 'pdf' in text_lower:
                detected_format = 'pdf'
            elif 'mobi' in text_lower or 'azw' in text_lower or 'kindle' in text_lower:
                detected_format = 'mobi'
            elif prefer_format == 'pdf':
                detected_format = 'pdf'
            else:
                detected_format = 'epub'

            print(f"✅ 下载链接: {link_text} -> {href[:60]}")

            # 构建下载 URL — 如果浏览器当前在镜像站（z-library.ms），用镜像的 host
            from urllib.parse import urlparse as _urlparse
            current_host = _urlparse(page.url).hostname if page.url else ''
            dl_path = href if href.startswith('/') else href
            if dl_path.startswith('/'):
                dl_url = f"https://{current_host}{dl_path}" if current_host else f"https://zh.zlib.li{dl_path}"
            else:
                dl_url = dl_path

            # 构造目标文件名
            ext_map = {'epub': '.epub', 'pdf': '.pdf', 'mobi': '.mobi'}
            ext = ext_map.get(detected_format, '.epub')
            safe_title = self._sanitize_filename(title) if title else 'book'
            target_filename = f"{safe_title}{ext}"
            final_path = self.downloads_dir / target_filename

            print(f"⬇️  开始下载: {target_filename}")

            # 用 anchor click 触发下载（Playwright 拦截 click → download 事件）
            with page.expect_download(timeout=60000) as dl_info:
                dl_link.click()
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
