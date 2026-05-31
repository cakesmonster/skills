#!/usr/bin/env python3
"""
小红书 QR 码登录 — 通用脚本。
生成 QR 码 → 用户扫码 → 检测登录成功 → 处理二次设备验证 → 保存 Cookie。

用法:
    python3 login_qr.py [--qr-dir /tmp] [--cookie-file ~/.hermes/data/xhs/cookies.json]

输出:
    - QR 码图片（路径打印到 stdout）
    - Cookie 保存到指定文件
"""

import argparse
import json
import os
import sys
import time

import qrcode
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description="小红书 QR 码扫码登录")
    parser.add_argument("--qr-dir", default="/tmp", help="QR 图片输出目录（默认 /tmp）")
    parser.add_argument(
        "--cookie-file",
        default=os.path.expanduser("~/.hermes/data/xhs/cookies.json"),
        help="Cookie 保存路径",
    )
    parser.add_argument(
        "--qr-filename",
        default="xhs_qr_login.png",
        help="QR 图片文件名",
    )
    args = parser.parse_args()

    qr_path = os.path.join(args.qr_dir, args.qr_filename)
    cookie_file = os.path.expanduser(args.cookie_file)
    os.makedirs(os.path.dirname(cookie_file), exist_ok=True)

    print(f"📱 Cookie 将保存到: {cookie_file}")
    print(f"📸 QR 图片将保存到: {qr_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # ── Phase 1: 生成 QR 码 ──
        qr_data = {}

        def handle_response(response):
            if "qrcode/create" in response.url and response.status == 200:
                try:
                    inner = response.json().get("data", {})
                    qr_data["qr_id"] = inner.get("qr_id", "")
                    qr_data["code"] = inner.get("code", "")
                    qr_data["url"] = inner.get("url", "")
                    print(f"📡 拦截到 QR API: id={qr_data['qr_id']}")
                except Exception:
                    pass

        page.on("response", handle_response)

        print("\n🔗 打开登录页...")
        page.goto(
            "https://www.xiaohongshu.com/login",
            wait_until="networkidle",
            timeout=30000,
        )
        page.wait_for_timeout(5000)

        if not qr_data.get("url"):
            print("❌ 未能截获 QR code API 响应，请重试")
            browser.close()
            sys.exit(1)

        # 生成 QR 图片
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(qr_data["url"])
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_path)
        print(f"✅ QR 图片已生成: {qr_path} ({os.path.getsize(qr_path)} bytes)")
        print(f"   QR ID: {qr_data['qr_id']}")
        print(f"\n📲 请用小红书 App 扫描二维码登录（有效期 120 秒）")

        # ── Phase 2: 轮询检测登录 ──
        logged_in = False
        for i in range(24):  # 120 秒
            time.sleep(5)
            elapsed = (i + 1) * 5
            try:
                check = page.evaluate(
                    """() => {
                    const body = document.body?.innerText || '';
                    const url = window.location.href;
                    const hasLoginModal = body.includes('手机号登录') || body.includes('验证码登录');
                    const onLoginPage = url.includes('/login');
                    const hasSecurityVerify = body.includes('新设备验证') || body.includes('安全验证');
                    return {
                        modal: hasLoginModal,
                        onLogin: onLoginPage,
                        security: hasSecurityVerify,
                        urlShort: url.substring(0, 100)
                    };
                }"""
                )

                if check["security"]:
                    print(f"  [{elapsed}s] ⚠️ 检测到「新设备验证」页面")
                    # 等待验证页面的 QR 码出现
                    page.wait_for_timeout(3000)
                    # 尝试找到验证 QR 码
                    verify_qr = page.evaluate(
                        """() => {
                        const img = document.querySelector('img[src*="data:image"]');
                        const canvas = document.querySelector('canvas');
                        if (canvas) return canvas.toDataURL('image/png');
                        if (img) return img.src;
                        return '';
                    }"""
                    )
                    if verify_qr:
                        import base64

                        if verify_qr.startswith("data:image"):
                            header, b64 = verify_qr.split(",", 1)
                            verify_path = os.path.join(args.qr_dir, "xhs_security_qr.png")
                            with open(verify_path, "wb") as f:
                                f.write(base64.b64decode(b64))
                            print(f"  🔐 二次验证 QR 已保存: {verify_path}")
                            print(f"  📲 请用小红书 App 再次扫描此验证码")
                        else:
                            verify_path = os.path.join(args.qr_dir, "xhs_security_qr.png")
                            page.screenshot(path=verify_path)
                            print(f"  🔐 验证页面截图: {verify_path}")
                            print(f"  📲 请查看截图并用小红书 App 完成验证")
                    # 延长等待
                    print(f"  ⏳ 等待验证完成...")
                    for j in range(12):
                        time.sleep(5)
                        recheck = page.evaluate(
                            """() => {
                            const body = document.body?.innerText || '';
                            return {
                                stillSecurity: body.includes('新设备验证') || body.includes('安全验证'),
                                url: window.location.href.substring(0, 80)
                            };
                        }"""
                        )
                        if not recheck["stillSecurity"] and "login" not in recheck["url"]:
                            logged_in = True
                            print(f"  ✅ 验证通过，登录成功！")
                            break
                        if j % 3 == 0:
                            print(f"  [{j*5}s] 等待验证中...")
                    break

                if not check["modal"] and not check["onLogin"]:
                    logged_in = True
                    print(f"  [{elapsed}s] ✅ 登录成功！url={check['urlShort']}")
                    break
                else:
                    status = "modal" if check["modal"] else "login page"
                    print(f"  [{elapsed}s] 等待扫码... ({status})")

            except Exception as e:
                print(f"  [{elapsed}s] ⚠️ 检测异常: {e}")

        if logged_in:
            context.storage_state(path=cookie_file)
            print(f"\n✅ Cookie 已保存: {cookie_file} ({os.path.getsize(cookie_file)} bytes)")
            print(f"🎉 登录完成！后续抓取可直接复用此 Cookie。")
        else:
            print("\n⚠️ 超时，二维码可能已过期。请重新运行。")
            browser.close()
            sys.exit(1)

        browser.close()


if __name__ == "__main__":
    main()
