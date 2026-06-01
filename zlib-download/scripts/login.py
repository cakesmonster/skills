#!/usr/bin/env python3
"""
Z-Library 登录 - 直接访问登录页，自动填写并提交
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
    print("请运行: pip install cloakbrowser")
    sys.exit(1)


def login_with_credentials(email: str, password: str, config_dir: Path):
    """使用账号密码自动登录"""
    storage_state = config_dir / "storage_state.json"

    print("=" * 70)
    print("🔐 Z-Library 自动登录")
    print("=" * 70)
    print(f"📧 账号: {email}")

    browser = launch_persistent_context(
        user_data_dir=str(config_dir / "browser_profile"),
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )

    page = browser.pages[0] if browser.pages else browser.new_page()
    page.set_default_timeout(60000)

    try:
        # 直接访问登录页
        print("📖 访问登录页...")
        page.goto("https://zh.zlib.li/login", wait_until='domcontentloaded', timeout=60000)

        print("⏳ 等待页面加载...")
        page.wait_for_timeout(5000)

        # 填写邮箱
        print("✏️  填写邮箱...")
        email_input = page.query_selector('input[name="email"]')
        if not email_input:
            # 备选：placeholder 为 Email 的输入框
            email_input = page.query_selector('input[placeholder="Email"]')
        if not email_input:
            raise Exception("未找到邮箱输入框")
        email_input.fill(email)
        page.wait_for_timeout(300)

        # 填写密码
        print("✏️  填写密码...")
        password_input = page.query_selector('input[name="password"]')
        if not password_input:
            password_input = page.query_selector('input[placeholder="密码"]')
        if not password_input:
            raise Exception("未找到密码输入框")
        password_input.fill(password)
        page.wait_for_timeout(300)

        # 提交：尝试点击 submit 按钮
        print("📤 提交登录...")
        submitted = False
        # 方式1: 找 button[type="submit"]
        try:
            btn = page.query_selector('button[type="submit"]')
            if btn:
                btn.click()
                submitted = True
                print("✅ 点击 button[type=submit]")
        except:
            pass

        # 方式2: 找任何包含"登录"/"Log in"的按钮
        if not submitted:
            for text in ['Log in', '登录', 'Sign in']:
                try:
                    btns = page.query_selector_all('button, input[type="submit"], input[type="button"]')
                    for b in btns:
                        t = b.inner_text() or ''
                        if text.lower() in t.lower():
                            b.click()
                            submitted = True
                            print(f"✅ 点击: {t}")
                            break
                except:
                    pass
                if submitted:
                    break

        # 方式3: 直接按 Enter
        if not submitted:
            password_input.press('Enter')
            print("✅ 按 Enter")

        print("⏳ 等待登录完成...")
        page.wait_for_timeout(8000)

        # 截图确认
        page.screenshot(path='/tmp/zlib-login-result.png')
        print(f"📸 结果截图: /tmp/zlib-login-result.png")
        print(f"   当前 URL: {page.url}")

        # 验证登录
        content = page.content()
        if any(x in content.lower() for x in ['logout', 'sign out', '退出', '个人中心', 'profile']):
            print("✅ 登录成功！")
        else:
            print(f"⚠️  登录状态不确定，请查看截图")
            # 检查是否还在登录页
            if 'login' in page.url.lower():
                print("❌ 似乎还在登录页")

        # 保存会话
        browser.storage_state(path=str(storage_state))
        storage_state.chmod(0o600)
        print(f"✅ 会话已保存: {storage_state}")

    except Exception as e:
        print(f"❌ 登录失败: {e}")
        import traceback
        traceback.print_exc()
        try:
            page.screenshot(path='/tmp/zlib-error.png')
            print(f"📸 错误截图: /tmp/zlib-error.png")
        except:
            pass
    finally:
        browser.close()


def main():
    if len(sys.argv) < 3:
        print("用法: python3 login.py <邮箱> <密码>")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]

    config_dir = Path.home() / ".zlibrary"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_dir.chmod(0o700)

    login_with_credentials(email, password, config_dir)


if __name__ == "__main__":
    main()
