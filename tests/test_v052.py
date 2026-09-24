"""
آزمون‌های جامع یکپارچگی مهندسی نگارش v0.5.2
UNFINIT Store Engine Release v0.5.2 Verification Test Suite
"""

import math
import unittest
import builtins
from pathlib import Path

from core.config import config
from services.web_panel import get_system_health, render_dashboard_html
from media.compressor import SmartVideoSplitter, SAFE_BALE_PART_LIMIT_MB
from platforms.bale_adapter import get_bale_customer_keyboard
from core.sign_service import SignService


class TestV052Release(unittest.TestCase):

    def test_01_engine_version_sync(self):
        """بررسی همگام‌سازی نگارش v0.5.2 / v0.5.3 در کانفیگ، وضعیت سلامت و ماژول‌ها"""
        self.assertIn(str(config.ENGINE_VERSION), ("v0.5.2", "v0.5.3"))
        health = get_system_health()
        self.assertTrue(any(v in str(health["engine_version"]) for v in ("v0.5.2", "v0.5.3")))

    def test_02_bale_customer_keyboard_layout(self):
        """بررسی چیدمان استاندارد RTL کیبورد مشتری بله و حذف فرکانس فراوانی از ریشه"""
        kb_data = get_bale_customer_keyboard()
        self.assertIn("keyboard", kb_data)
        rows = kb_data["keyboard"]
        self.assertEqual(len(rows), 2, "کیبورد مشتری باید دقیقاً ۲ ردیف باشد")

        # ردیف اول: [ 🔮 نشانه امروز من ] در راست (ایندکس ۰ در RTL) و [ 💎 محصولات و اشتراک پریمیوم ] در چپ (ایندکس ۱)
        row1 = rows[0]
        self.assertEqual(len(row1), 2)
        self.assertEqual(row1[0]["text"], "🔮 نشانه امروز من")
        self.assertEqual(row1[1]["text"], "💎 محصولات و اشتراک پریمیوم")

        # ردیف دوم: [ 👤 حساب کاربری ] و [ 🎁 فایل‌های هدیه ]
        row2 = rows[1]
        self.assertEqual(len(row2), 2)
        self.assertEqual(row2[0]["text"], "👤 حساب کاربری")
        self.assertIn("هدیه", row2[1]["text"])

        # عدم وجود فرکانس فراوانی در منوی ریشه
        for row in rows:
            for btn in row:
                self.assertNotIn("فرکانس فراوانی", btn["text"])

    def test_03_gift_cards_and_aspect_video(self):
        """بررسی بازطراحی کارت‌های هدیه ۱۶:۹ با no-referrer و loading=lazy در وب‌پنل"""
        html = render_dashboard_html()
        self.assertIn('referrerpolicy="no-referrer"', html)
        self.assertIn('loading="lazy"', html)
        self.assertIn('aspect-video', html)
        self.assertIn('unfinit_tab_renames', html)
        self.assertIn('restoreTabRenames', html)

    def test_04_manual_split_parts_and_safe_margin(self):
        """بررسی انعطاف‌پذیری حق انتخاب دستی کاربر برای ۲ یا ۳ پارت و سقف ایمن ۴۵MB"""
        # آزمون تعداد پارت‌ها
        parts_100mb = max(2, math.ceil(100.0 / SAFE_BALE_PART_LIMIT_MB))
        self.assertEqual(parts_100mb, 3, "ویدیوی ۱۰۰ مگابایتی برای سقف ۴۵MB حداقل به ۳ پارت نیاز دارد")

        tg_code = Path("platforms/telegram_adapter.py").read_text(encoding="utf-8")
        self.assertTrue("تقسیم هوشمند به ۲ پارت" in tg_code or "تقسیم به ۲ پارت" in tg_code)
        self.assertTrue("فشرده‌سازی تا سقف بله" in tg_code or "فشرده‌سازی معمولی" in tg_code)

    def test_05_category_navigation_back_button(self):
        """بررسی اصلاح دکمه ناوبری ۱۶ دسته‌بندی به [ 🔙 بازگشت به دسته‌بندی‌ها ]"""
        bale_code = Path("platforms/bale_adapter.py").read_text(encoding="utf-8")
        self.assertIn("🔙 بازگشت به دسته‌بندی‌ها", bale_code)

    def test_06_sign_smart_fallback(self):
        """بررسی فالبک هوشمند و پایدار نشانه امروز در بله و تلگرام"""
        bale_code = Path("platforms/bale_adapter.py").read_text(encoding="utf-8")
        tg_code = Path("platforms/telegram_adapter.py").read_text(encoding="utf-8")

        self.assertIn("📥 دانلود مستقیم از سایت", bale_code)
        self.assertIn("📥 دانلود مستقیم از سایت", tg_code)

    def test_07_premium_activation_notification(self):
        """بررسی ارسال نوتیفیکیشن تبریک فعال‌سازی پریمیوم در app.py و bale_adapter.py"""
        app_code = Path("app.py").read_text(encoding="utf-8")
        bale_code = Path("platforms/bale_adapter.py").read_text(encoding="utf-8")

        expected_msg_snip = "هم‌اکنون به ۱۶ دسته‌بندی و فرکانس فراوانی دسترسی دارید. ✨"
        self.assertIn(expected_msg_snip, app_code)
        self.assertIn(expected_msg_snip, bale_code)

    def test_08_documentation_and_changelog_v052(self):
        """بررسی مستندسازی کامل نسخه v0.5.2 در AGENTS.md, CHANGELOG.md و README.md"""
        agents_txt = Path("AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("v0.5.2", agents_txt)
        self.assertIn("| v0.5.2 | 1403/07/05 |", agents_txt)

        changelog_txt = Path("CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## [v0.5.2] - 1403/07/05", changelog_txt)

        readme_txt = Path("README.md").read_text(encoding="utf-8")
        self.assertTrue("UNFINIT (v0.5.2)" in readme_txt or "UNFINIT (v0.5.3)" in readme_txt)
        self.assertTrue("version-v0.5.2-blue.svg" in readme_txt or "version-v0.5.3-blue.svg" in readme_txt)


if __name__ == "__main__":
    unittest.main()
