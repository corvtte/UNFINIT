# -*- coding: utf-8 -*-
"""
آزمون‌های اعتبارسنجی نگارش v0.4.2 موتور UNFINIT Store Engine:
۱. همگام‌سازی سراسری شماره نسخه v0.4.2 (کانفیگ، وضعیت سلامت، داشبورد و استورفرانت)
۲. عملکرد ماژول لید مگنت «نشانه امروز من» (SignService) و قطعی بودن ۲۴ ساعته آن
۳. پارس پویا و استخراج متادیتای حساب سروش‌پلاس (account1) بدون هاردکد
۴. پایبندی به قانون اکشن‌های بدون رفرش (Zero Page-Reload Principle) در وب‌پنل
5. عدم وجود خطای اسکوپ StoreService در هندلر متد do_POST در app.py
۶. وجود دکمه تعاملی «🔮 نشانه امروز من» در کیبوردهای تلگرام و بله
۷. رعایت قانون مستندسازی و داک‌استرینگ‌های فارسی در ماژول‌های جدید طبق بند ۵.۵ منشور AGENTS.md
"""

import json
import os
import unittest
import asyncio
from pathlib import Path

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from core.config import config
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
from core.sign_service import SignService
from platforms.soroush_worker import SoroushWorker
from platforms.telegram_adapter import get_customer_keyboard
from platforms.bale_adapter import get_bale_customer_keyboard


class TestVersion042Features(unittest.TestCase):
    def setUp(self):
        self.sign_cache_dir = Path("data/sign_cache")

    def test_01_version_v042_sync(self):
        """اعتبارسنجی نسخه v0.4.2 و v0.4.3 در تمام بخش‌های اصلی سیستم."""
        self.assertIn(str(config.ENGINE_VERSION), ("v0.4.2", "v0.4.3"))
        health = get_system_health()
        self.assertTrue(any(v in health["engine_version"] for v in ("v0.4.2", "v0.4.3")))

        dash_html = render_dashboard_html()
        self.assertTrue(any(v in dash_html for v in ("v0.4.2", "v0.4.3")))

        store_html = render_storefront_html()
        self.assertTrue(any(v in store_html for v in ("v0.4.2", "v0.4.3")))

    def test_02_sign_service_lead_magnet(self):
        """اعتبارسنجی ماژول لید مگنت نشانه امروز من و قطعی بودن انتخاب ۲۴ ساعته."""
        user_id = 987654321
        sign1 = asyncio.run(SignService.get_user_today_sign(user_id))
        self.assertIsNotNone(sign1)
        self.assertIn("title", sign1)
        self.assertIn("audio_url", sign1)

        # استعلام دوباره برای همان کاربر در همان روز باید دقیقاً همان فایل را برگرداند
        sign2 = asyncio.run(SignService.get_user_today_sign(user_id))
        self.assertEqual(sign1["title"], sign2["title"])
        self.assertEqual(sign1["audio_url"], sign2["audio_url"])

        # استعلام تست تصادفی
        rand_sign = asyncio.run(SignService.get_random_sign_for_test())
        self.assertIsNotNone(rand_sign)
        self.assertIn("title", rand_sign)

        # قالب‌بندی پیام
        caption = SignService.format_sign_caption(sign1)
        self.assertIn("نشانه امروز من", caption)
        self.assertIn(sign1["title"], caption)

    def test_03_soroush_worker_dynamic_account_parsing(self):
        """اعتبارسنجی پارس پویای ساختار account1 وب سروش‌پلاس بدون هاردکد."""
        worker = SoroushWorker(session_name="test_soroush_v042")
        sample_account = {
            "dcId": 2,
            "dc2_auth_key": "0123456789abcdef0123456789abcdef0123456789abcdef",
            "userId": "989129998877",
            "phone": "09129998877",
            "firstName": "سجاد تست"
        }
        raw_json = json.dumps(sample_account)
        ok = worker.save_manual_token(raw_json)
        self.assertTrue(ok)
        self.assertTrue(worker.is_connected())

        masked = worker.get_masked_phone()
        self.assertIn("سجاد تست", masked)
        self.assertIn("0912***8877", masked)

        status = worker.get_status()
        self.assertEqual(status["platform"], "soroush")
        self.assertTrue(status["connected"])
        self.assertEqual(status["first_name"], "سجاد تست")

        # پاکسازی
        worker.disconnect()
        self.assertFalse(worker.is_connected())

    def test_04_zero_page_reload_in_web_panel(self):
        """اعتبارسنجی قانون اکشن‌های بدون رفرش (Zero Page-Reload) در جاوااسکریپت پنل."""
        with open("services/web_panel.py", "r", encoding="utf-8") as f:
            content = f.read()

        # بررسی متد قطع نشست
        self.assertIn("async function disconnectSession(platform)", content)
        # تابع disconnectSession نباید دارای window.location.reload باشد
        idx_dc = content.find("async function disconnectSession(platform)")
        idx_end_dc = content.find("window.disconnectSession = disconnectSession;", idx_dc)
        dc_body = content[idx_dc:idx_end_dc]
        self.assertNotIn("window.location.reload()", dc_body)
        self.assertNotIn("location.reload()", dc_body)

        # بررسی متد ذخیره دوره
        idx_save = content.find("async function handleSaveEdit(e)")
        idx_end_save = content.find("async function saveCourseTermsText()", idx_save)
        save_body = content[idx_save:idx_end_save]
        self.assertNotIn("location.reload()", save_body)

        # بررسی وجود توابع تعاملی مدیریت جلسات پکیج
        self.assertIn("function renderPackageLessons()", content)
        self.assertIn("function addPackageLessonRow()", content)
        self.assertIn("function movePackageLesson(", content)
        self.assertIn("function removePackageLesson(", content)

        # بررسی وجود دکمه تست ادمین نشانه امروز من
        self.assertIn("id=\"btnTestTodaySign\"", content)
        self.assertIn("testTodaySign()", content)

    def test_05_store_service_scope_in_app(self):
        """اعتبارسنجی عدم وجود خطای اسکوپ و ایمپورت محلی StoreService در app.py."""
        with open("app.py", "r", encoding="utf-8") as f:
            lines = f.readlines()

        # نباید ایمپورت محلی StoreService درون بدنه do_POST وجود داشته باشد
        in_do_post = False
        local_import_found = False
        for idx, line in enumerate(lines, 1):
            if "def do_POST(self):" in line:
                in_do_post = True
            elif in_do_post and line.startswith("    def "):
                in_do_post = False
            
            if in_do_post and "from services.store_service import StoreService" in line:
                local_import_found = True
                break

        self.assertFalse(local_import_found, "نباید ایمپورت محلی StoreService در do_POST وجود داشته باشد.")

    def test_06_customer_keyboards_have_today_sign(self):
        """اعتبارسنجی وجود دکمه 'نشانه امروز من' در کیبوردهای مشتری تلگرام و بله."""
        tg_kb = get_customer_keyboard()
        tg_buttons_text = []
        rows = getattr(tg_kb, "keyboard", tg_kb)
        for row in rows:
            for btn in row:
                if isinstance(btn, dict):
                    tg_buttons_text.append(btn.get("text", ""))
                elif hasattr(btn, "text"):
                    tg_buttons_text.append(btn.text)
                else:
                    tg_buttons_text.append(str(btn))
        self.assertTrue(any("نشانه امروز من" in t for t in tg_buttons_text))

        bale_kb = get_bale_customer_keyboard()
        bale_buttons_text = []
        rows_bale = bale_kb.get("keyboard", []) if isinstance(bale_kb, dict) else getattr(bale_kb, "keyboard", bale_kb)
        for row in rows_bale:
            for btn in row:
                if isinstance(btn, dict):
                    bale_buttons_text.append(btn.get("text", ""))
                elif hasattr(btn, "text"):
                    bale_buttons_text.append(btn.text)
                else:
                    bale_buttons_text.append(str(btn))
        self.assertTrue(any("نشانه امروز من" in t for t in bale_buttons_text))

    def test_07_persian_docstrings_compliance(self):
        """اعتبارسنجی رعایت بند ۵.۵ در AGENTS.md برای مستندسازی فارسی در SignService."""
        self.assertIsNotNone(SignService.__doc__)
        self.assertIn("نشانه امروز من", SignService.__doc__)
        self.assertIsNotNone(SignService.get_user_today_sign.__doc__)
        self.assertIn("ورودی", SignService.get_user_today_sign.__doc__)


if __name__ == "__main__":
    unittest.main()
