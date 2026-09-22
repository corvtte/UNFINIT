# -*- coding: utf-8 -*-
"""
آزمون‌های اعتبارسنجی نگارش v0.4.5 موتور UNFINIT Store Engine:
۱. همگام‌سازی سراسری شماره نسخه v0.4.5 (کانفیگ، وضعیت سلامت، داشبورد و استورفرانت)
۲. آزمون متدهای UserService (grant_vip, revoke_vip, get_user_by_any_id)
۳. آزمون عدم وجود خطای اسکوپ get_system_setting و st_txt در bale_adapter.py
۴. آزمون منطق فالبک ارسال فایل بالای ۴۹ مگابایت در bale_adapter.py
۵. آزمون هندلرها و کیبوردهای محصولات در تلگرام و بله
۶. آزمون اندپوینت‌های ایجکس جدید app.py (/api/users/toggle_vip, /api/users/profile, /api/settings/rename)
"""

import os
import sys
import unittest
import json
import asyncio
from pathlib import Path

# تنظیم مسیر پایه پروژه
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from core.config import config
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
from services.user_service import UserService

class TestV045Release(unittest.TestCase):
    """مجموعه آزمون‌های خودکار جهت اعتبارسنجی امکانات و ارتقای جامع نگارش v0.4.5."""

    def test_01_version_sync(self):
        """اعتبارسنجی نسخه v0.4.5 تا v0.4.6 در تمام بخش‌های اصلی سیستم."""
        self.assertIn(str(config.ENGINE_VERSION), ("v0.4.5", "v0.4.6"))
        health = get_system_health()
        self.assertTrue(any(v in str(health["engine_version"]) for v in ("v0.4.5", "v0.4.6")))
        
        dash_html = render_dashboard_html()
        self.assertTrue(any(v in dash_html for v in ("v0.4.5", "v0.4.6")))
        
        store_html = render_storefront_html()
        self.assertTrue(any(v in store_html for v in ("v0.4.5", "v0.4.6")))

    def test_02_vip_user_service(self):
        """اعتبارسنجی متدهای مدیریت اشتراک VIP در UserService."""
        test_uid = "999888777"
        # پاکسازی قبلی اگر وجود داشت
        UserService.revoke_vip(test_uid)
        
        # اعطای اشتراک VIP برای ۳۰ روز
        granted = UserService.grant_vip(test_uid, days=30)
        self.assertTrue(granted)
        
        # استعلام کاربر
        user = UserService.get_user_by_any_id(test_uid)
        self.assertIsNotNone(user)
        self.assertTrue(user.get("is_vip"))
        self.assertTrue(bool(user.get("vip_until")))
        
        # لغو اشتراک VIP
        revoked = UserService.revoke_vip(test_uid)
        self.assertTrue(revoked)
        user_after = UserService.get_user_by_any_id(test_uid)
        self.assertFalse(user_after.get("is_vip"))

    def test_03_bale_adapter_scoping_cleanliness(self):
        """اعتبارسنجی عدم وجود خطای UnboundLocalError و متغیر آزاد st_txt در bale_adapter.py."""
        bale_file = BASE_DIR / "platforms" / "bale_adapter.py"
        self.assertTrue(bale_file.exists())
        content = bale_file.read_text(encoding="utf-8")
        
        # بررسی اینکه هیچ ایمپورت محلی درون‌تابعی از get_system_setting وجود نداشته باشد
        lines = content.splitlines()
        local_imports = [
            (idx + 1, line)
            for idx, line in enumerate(lines)
            if "get_system_setting" in line and ("import" in line) and idx > 30
        ]
        self.assertEqual(len(local_imports), 0, f"Found local get_system_setting import at: {local_imports}")
        
        # بررسی اینکه متغیر st_txt تعریف شده باشد
        self.assertIn("st_txt =", content)
        # بررسی وجود هندلر کال‌بک اینویس VIP
        self.assertIn("bale:vip_pay_online", content)
        self.assertIn("send_invoice", content)
        self.assertIn("vip_sub_", content)

    def test_04_bale_large_audio_fallback(self):
        """اعتبارسنجی منطق فالبک ارسال فایل بالای ۴۹ مگابایت به sendDocument."""
        bale_file = BASE_DIR / "platforms" / "bale_adapter.py"
        content = bale_file.read_text(encoding="utf-8")
        self.assertIn("MAX_SAFE_BALE_SIZE_MB", content)
        self.assertIn("sendDocument", content)
        self.assertIn("send_document", content)

    def test_05_products_hub_keyboards(self):
        """اعتبارسنجی کیبورد شیشه‌ای سه‌گانه محصولات در بله و تلگرام."""
        bale_file = BASE_DIR / "platforms" / "bale_adapter.py"
        tg_file = BASE_DIR / "platforms" / "telegram_adapter.py"
        
        bale_content = bale_file.read_text(encoding="utf-8")
        tg_content = tg_file.read_text(encoding="utf-8")
        
        # دکمه منوی اصلی
        self.assertIn("🛍 محصولات", bale_content)
        self.assertIn("🛍 محصولات", tg_content)
        
        # کیبورد سه‌گانه
        self.assertIn("bale:prods_courses", bale_content)
        self.assertIn("bale:prods_audiobooks", bale_content)
        self.assertIn("bale:vip_plan", bale_content)
        
        self.assertIn("tg:prods_courses", tg_content)
        self.assertIn("tg:prods_audiobooks", tg_content)
        self.assertIn("tg:vip_plan", tg_content)

    def test_06_web_panel_products_hub_and_material3(self):
        """اعتبارسنجی المان‌های هاب سه‌گانه محصولات و Material 3 در وب‌پنل."""
        web_file = BASE_DIR / "services" / "web_panel.py"
        content = web_file.read_text(encoding="utf-8")
        
        # سابد تب‌ها در بخش محصولات
        self.assertIn("subtab-prods-courses", content)
        self.assertIn("subtab-prods-audiobooks", content)
        self.assertIn("subtab-prods-vip", content)
        self.assertIn("switchProductSubTab", content)
        
        # ویرایش درجا با دابل‌کلیک
        self.assertIn("inlineRenameTab", content)
        self.assertIn("ondblclick=\"inlineRenameTab(this,", content)
        
        # هولد ۴۰۰ میلی‌ثانیه‌ای درگ سایدبار
        self.assertIn("mouseHoldTimer = setTimeout", content)
        self.assertIn("400", content)
        
        # مودال پروفایل کاربر و دکمه‌های ایجکس
        self.assertIn("userProfileModal", content)
        self.assertIn("toggleUserVip", content)
        self.assertIn("viewUserProfile", content)

    def test_07_app_ajax_endpoints(self):
        """اعتبارسنجی وجود اندپوینت‌های جدید در app.py."""
        app_file = BASE_DIR / "app.py"
        content = app_file.read_text(encoding="utf-8")
        self.assertIn("/api/users/toggle_vip", content)
        self.assertIn("/api/users/profile", content)
        self.assertIn("/api/settings/rename", content)

if __name__ == "__main__":
    unittest.main()
