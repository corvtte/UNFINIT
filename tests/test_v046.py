# -*- coding: utf-8 -*-
"""
آزمون‌های جامع اعتبارسنجی نگارش v0.4.6 موتور UNFINIT Store Engine:
۱. همگام‌سازی سراسری نسخه v0.4.6 در تمام مؤلفه‌های کلیدی.
۲. مهار خطاهای BrokenPipeError و ConnectionResetError در app.py.
۳. عدم وجود خطای سینتکس جاوااسکریپت و اعتبارسنجی Event Delegation جدول کاربران.
۴. حذف قطعی و کامل واژه VIP و یکدست‌سازی به «اشتراک پریمیوم» در تمام پلتفرم‌ها و اینویس بله.
۵. حضور ۵ پروژه تحول گام‌به‌گام سایت عباس‌منش در زیرشاخه ۳ محصولات و پیام‌های پلتفرم‌ها.
۶. حذف کارت تکراری سقف ایمن بله از بالای داشبورد و ایجاد گرید ۳ ستونی کارت‌های متریک.
۷. مکانیزم صف امن محلی در soroush_worker.py هنگام تایم‌اوت یا خطای شبکه.
"""

import os
import sys
import unittest
import json
import asyncio
import re
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from core.config import config
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
from services.user_service import UserService

class TestV046Release(unittest.TestCase):
    """مجموعه آزمون‌های خودکار جهت تایید و اعتبارسنجی نگارش v0.4.6."""

    def test_01_version_sync(self):
        """اعتبارسنجی شماره نسخه v0.4.6 در کانفیگ، وضعیت سلامت و خروجی‌های وب."""
        self.assertEqual(str(config.ENGINE_VERSION), "v0.4.6")
        health = get_system_health()
        self.assertIn("v0.4.6", str(health["engine_version"]))
        
        dash_html = render_dashboard_html()
        self.assertIn("v0.4.6", dash_html)
        
        store_html = render_storefront_html()
        self.assertIn("v0.4.6", store_html)

    def test_02_broken_pipe_suppression(self):
        """اعتبارسنجی مهار BrokenPipeError و ConnectionResetError در app.py."""
        app_file = BASE_DIR / "app.py"
        self.assertTrue(app_file.exists())
        content = app_file.read_text(encoding="utf-8")
        self.assertIn("BrokenPipeError", content)
        self.assertIn("ConnectionResetError", content)

    def test_03_web_panel_js_syntax_and_delegation(self):
        """اعتبارسنجی نبود هیچ خطای سینتکس جاوااسکریپت و وجود Event Delegation در جدول کاربران."""
        dash_html = render_dashboard_html()
        scripts = re.findall(r'<script>(.*?)</script>', dash_html, re.DOTALL)
        self.assertTrue(len(scripts) > 0, "No scripts found in dashboard HTML")
        
        full_js = '\n'.join(scripts)
        # بررسی عدم وجود اسکیپ شکسته کوتیشن در جاوااسکریپت
        self.assertNotIn("'' + userIdClean + ''", full_js)
        # بررسی وجود Event Delegation
        self.assertIn("data-user-action", full_js)
        self.assertIn("data-user-id", full_js)
        self.assertIn("revoke_vip", full_js)
        self.assertIn("grant_vip", full_js)
        
        # اجرای اعتبارسنجی کامپایل جاوااسکریپت با node -c
        temp_js = BASE_DIR / "temp_test_v046.js"
        try:
            temp_js.write_text(full_js, encoding="utf-8")
            res = subprocess.run(["node", "-c", str(temp_js)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Node.js syntax error:\n{res.stderr}")
        finally:
            if temp_js.exists():
                temp_js.unlink()

    def test_04_vip_purged_from_platforms_and_invoices(self):
        """اعتبارسنجی حذف اصطلاح VIP از اینویس بله، هاب محصولات و پیام‌ها."""
        bale_file = BASE_DIR / "platforms" / "bale_adapter.py"
        bale_code = bale_file.read_text(encoding="utf-8")
        
        # فاکتور بله باید منحصراً با عنوان 'اشتراک پریمیوم ۳۰ روزه' صادر شود
        self.assertIn('title="اشتراک پریمیوم ۳۰ روزه"', bale_code)
        self.assertNotIn('title="اشتراک ویژه ۳۰ روزه VIP"', bale_code)
        
        # در دکمه‌های محصولات بله و تلگرام باید 'اشتراک پریمیوم' باشد
        self.assertIn('"💎 اشتراک پریمیوم"', bale_code)
        self.assertNotIn('"💎 اشتراک ویژه (VIP)"', bale_code)

        tg_file = BASE_DIR / "platforms" / "telegram_adapter.py"
        tg_code = tg_file.read_text(encoding="utf-8")
        self.assertIn('"💎 اشتراک پریمیوم"', tg_code)
        self.assertNotIn('"💎 اشتراک ویژه (VIP)"', tg_code)

    def test_05_five_transformation_projects_present(self):
        """اعتبارسنجی حضور ۵ پروژه تحول گام‌به‌گام سایت عباس‌منش در وب‌پنل و پیام‌های پلتفرم‌ها."""
        dash_html = render_dashboard_html()
        projects = [
            "درک عمیق‌تر قوانین خدا",
            "پروژه تغییر را در آغوش بگیر",
            "پروژه مهاجرت به مدار بالاتر",
            "پروژه خانه‌تکانی ذهن",
            "روزشمار تحول زندگی من"
        ]
        for p in projects:
            self.assertIn(p, dash_html, f"Project '{p}' missing from dashboard HTML")

        bale_code = (BASE_DIR / "platforms" / "bale_adapter.py").read_text(encoding="utf-8")
        for p in projects:
            self.assertIn(p, bale_code, f"Project '{p}' missing from bale_adapter.py")

        tg_code = (BASE_DIR / "platforms" / "telegram_adapter.py").read_text(encoding="utf-8")
        for p in projects:
            self.assertIn(p, tg_code, f"Project '{p}' missing from telegram_adapter.py")

    def test_06_dashboard_metrics_clean_3_cols(self):
        """اعتبارسنجی حذف کارت تکراری سقف ایمن بله از بالای داشبورد و آرایش ۳ ستونی."""
        dash_html = render_dashboard_html()
        self.assertIn("grid-cols-1 sm:grid-cols-3 gap-4", dash_html)
        self.assertNotIn("<!-- Metric 4: Bale Safe Limit -->", dash_html)

    def test_07_soroush_local_queue_on_timeout(self):
        """اعتبارسنجی ذخیره در صف امن محلی کلاینت سروش‌پلاس در زمان خطا/تایم‌اوت."""
        soroush_file = BASE_DIR / "platforms" / "soroush_worker.py"
        soroush_code = soroush_file.read_text(encoding="utf-8")
        self.assertIn("فایل با موفقیت در صف امن محلی ثبت شد", soroush_code)
        self.assertIn("queue_dir", soroush_code)

if __name__ == "__main__":
    unittest.main()
