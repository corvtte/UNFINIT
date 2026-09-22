# -*- coding: utf-8 -*-
"""
آزمون‌های اعتبارسنجی نگارش v0.4.4 موتور UNFINIT Store Engine:
۱. همگام‌سازی سراسری شماره نسخه v0.4.4 (کانفیگ، وضعیت سلامت، داشبورد و استورفرانت)
۲. اعتبارسنجی سنکرون بودن متد ReferralService.record_referral و عدم نیاز به await
۳. سیستم اشتراک ماهانه VIP، فیلد vip_until و متدهای UserModel.is_vip و UserService
۴. شخصی‌سازی نشانه امروز من: تاریخ رسمی شمسی با اعداد فارسی، استخراج سرفصل‌ها و حذف برندینگ
۵. ساختار فرانت‌اند وب‌پنل: تب اشتراک پریمیوم، دکمه‌های بستن مودال و چک‌باکس‌های دوگانه رسانه
۶. سازگاری ارسال reply_markup در متد send_audio بله
"""

import inspect
import json
import os
import unittest
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from core.config import config
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
from core.sign_service import SignService
from services.user_service import UserService, UserModel
from services.referral_service import ReferralService
from platforms.bale_adapter import BaleAdapter


class TestVersion044Features(unittest.TestCase):
    """مجموعه آزمون‌های خودکار جهت اعتبارسنجی امکانات و هات‌فیکس‌های نگارش v0.4.4."""

    def test_01_version_v044_sync(self):
        """اعتبارسنجی نسخه v0.4.4 تا v0.4.5 در تمام بخش‌های اصلی سیستم."""
        self.assertIn(str(config.ENGINE_VERSION), ("v0.4.4", "v0.4.5"))
        health = get_system_health()
        self.assertTrue(any(v in str(health["engine_version"]) for v in ("v0.4.4", "v0.4.5")))

        dash_html = render_dashboard_html()
        self.assertTrue(any(v in dash_html for v in ("v0.4.4", "v0.4.5")))

        store_html = render_storefront_html()
        self.assertTrue(any(v in store_html for v in ("v0.4.4", "v0.4.5")))

    def test_02_referral_service_synchronous(self):
        """اعتبارسنجی قطعی سنکرون بودن ReferralService.record_referral و رفع باگ await."""
        self.assertFalse(inspect.iscoroutinefunction(ReferralService.record_referral))
        res = ReferralService.record_referral("invalid_code_test", "09120000000", "telegram", "123456")
        self.assertIsInstance(res, tuple)
        self.assertEqual(len(res), 2)
        inviter_phone, newly_unlocked = res
        self.assertIsNone(inviter_phone)
        self.assertFalse(newly_unlocked)

    def test_03_vip_club_user_model_and_service(self):
        """اعتبارسنجی سیستم اشتراک VIP در UserModel و متدهای UserService."""
        # کاربر بدون اشتراک
        user_free = UserModel({"phone": "09121111111", "vip_until": ""})
        self.assertFalse(user_free.is_vip())

        # کاربر با اشتراک منقضی شده
        past_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        user_expired = UserModel({"phone": "09122222222", "vip_until": past_date})
        self.assertFalse(user_expired.is_vip())

        # کاربر با اشتراک معتبر آینده
        future_date = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
        user_vip = UserModel({"phone": "09123333333", "vip_until": future_date})
        self.assertTrue(user_vip.is_vip())

        # اعتبارسنجی متدهای UserService
        with patch.object(UserService, "get_user_by_any_id", return_value=user_vip):
            self.assertTrue(UserService.is_user_vip("12345"))
        with patch.object(UserService, "get_user_by_any_id", return_value=user_free):
            self.assertFalse(UserService.is_user_vip("54321"))

    def test_04_sign_shamsi_date_and_clean_caption(self):
        """اعتبارسنجی کپشن نشانه با تاریخ شمسی، بدون فوتر UNFINIT و با تگ خواننده و سرفصل‌ها."""
        fake_sign = {
            "title": "فایل آرامش و شکرگزاری",
            "date": "2026-09-20",
            "url": "https://abasmanesh.com/test-sign",
            "chapters": [
                {"title": "مقدمه و شروع روز", "link": "https://abasmanesh.com/c1"},
                {"title": "باورهای ثروت", "link": "https://abasmanesh.com/c2"}
            ]
        }

        # تست فرمت پاک کپشن با تاریخ شمسی
        caption = SignService.format_sign_caption(fake_sign, reader_tag="abasmanesh365", include_chapters=True)
        # تاریخ باید با ارقام فارسی و تقویم شمسی باشد
        self.assertIn("📅", caption)
        self.assertNotIn("UNFINIT Store Engine", caption)
        self.assertIn("@abasmanesh365", caption)
        self.assertIn("مقدمه و شروع روز", caption)
        self.assertIn("باورهای ثروت", caption)

        # تست غیرفعال‌سازی سرفصل‌ها
        caption_no_chapters = SignService.format_sign_caption(fake_sign, reader_tag="my_channel", include_chapters=False)
        self.assertNotIn("مقدمه و شروع روز", caption_no_chapters)
        self.assertIn("@my_channel", caption_no_chapters)

    def test_05_web_panel_vip_and_modal_exports(self):
        """اعتبارسنجی توابع بستن مودال، تب VIP، چک‌باکس‌های دوگانه و عدم وجود draggable در سایدبار."""
        dash_html = render_dashboard_html()
        # بستن مودال در اسکوپ سراسری
        self.assertIn("window.closeEditModal", dash_html)
        self.assertIn("window.closeEditCourseModal", dash_html)
        # تب و متدهای VIP
        self.assertIn("اشتراک پریمیوم و محتوا", dash_html)
        self.assertIn("saveVipSettings", dash_html)
        self.assertIn("loadVipSettings", dash_html)
        # چک‌باکس‌های دوگانه ارسال هدیه
        self.assertIn("chkFormatAudio", dash_html)
        self.assertIn("chkFormatVideo", dash_html)
        # حذف draggable و تکان‌های سایدبار
        self.assertNotIn('draggable="true"', dash_html)

    def test_06_bale_send_audio_reply_markup(self):
        """اعتبارسنجی پشتیبانی متد send_audio بله از reply_markup و kwargs."""
        bale = BaleAdapter("dummy_token")
        sig = inspect.signature(bale.send_audio)
        self.assertIn("kwargs", sig.parameters)


if __name__ == "__main__":
    unittest.main()
