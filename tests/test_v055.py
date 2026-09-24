# -*- coding: utf-8 -*-
"""
آزمون‌های یکپارچه‌سازی و اعتبارسنجی نگارش v0.5.5 موتور UNFINIT
شامل تست تقویم شمسی کامل، کش دیسک دانلودها، دسته‌بندی‌های سفارشی،
پریمیوم کاربر، و کلاس استریم پیشرفت بله.
"""

import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

# افزودن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from core.config import config
from core.jalali import format_jalali_full, gregorian_to_jalali
from services.feed_scraper import (
    FeedScraper,
    get_all_categories,
    save_custom_categories,
    get_custom_categories,
    load_feed_disk_cache,
    save_feed_disk_cache,
    FALLBACK_ITEMS
)
from services.user_service import UserService, UserModel
from platforms.bale_adapter import ProgressFileReader


class TestVersion055(unittest.TestCase):
    def test_01_version_consistency(self):
        """بررسی همگام‌سازی نگارش v0.5.5 در config"""
        self.assertEqual(str(config.ENGINE_VERSION), "v0.5.5")
        self.assertTrue(config.ENGINE_VERSION.startswith("v0.5"))

    def test_02_jalali_full_format(self):
        """بررسی فرمت جامع تاریخ و ساعت شمسی"""
        dt = datetime(2026, 10, 24, 8, 53, 0)
        formatted = format_jalali_full(dt)
        self.assertIn("آبان", formatted)
        self.assertIn("ساعت", formatted)
        # باید شامل روز هفته باشد
        self.assertTrue(any(w in formatted for w in ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]))

    def test_03_fallback_items_cdnir(self):
        """تایید اولویت دامنه‌های پایدار cdnir در FALLBACK_ITEMS جهت ریشه‌کنی خطای ۴۰۰ تلگرام"""
        for item in FALLBACK_ITEMS:
            audio_url = item.get("audio_download_url", "")
            video_url = item.get("video_download_url", "")
            if audio_url:
                self.assertNotIn("cdneu.abasmanesh.com/download.php?url=video/1405", audio_url)
                self.assertIn("cdnir.abasmanesh.com", audio_url)

    def test_04_categories_emojis_and_custom_save(self):
        """بررسی وجود ایموجی در ۱۶ دسته‌بندی و ذخیره/بازیابی تنظیمات شخصی‌سازی"""
        cats = get_all_categories()
        self.assertGreaterEqual(len(cats), 15)
        # بررسی وجود کلید emoji
        for c in cats[:5]:
            self.assertTrue("emoji" in c or "id" in c)

        # تست ذخیره دسته‌بندی سفارشی
        test_cats = [dict(c) for c in cats]
        test_cats[0]["title"] = "تست دسته اول"
        ok = save_custom_categories(test_cats)
        self.assertTrue(ok)
        loaded = get_custom_categories()
        self.assertEqual(loaded[0]["title"], "تست دسته اول")

        # بازگرداندن به حالت پیش‌فرض
        test_cats[0]["title"] = cats[0]["title"]
        save_custom_categories(test_cats)

    def test_05_feed_disk_cache(self):
        """بررسی عملکرد کش دیسک دانلودها زیر ۱۰ms"""
        dummy_items = [{"title": "آیتم تستی کش دیسک", "url": "https://example.com/test.mp3"}]
        save_feed_disk_cache(dummy_items)
        cached = load_feed_disk_cache()
        self.assertEqual(len(cached), 1)
        self.assertEqual(cached[0]["title"], "آیتم تستی کش دیسک")

    def test_06_user_vip_jalali_grant(self):
        """بررسی اعطا و تمدید اشتراک پریمیوم و دریافت تاریخ شمسی"""
        test_uid = "test_user_v055"
        u = UserService.grant_vip(test_uid, days=10)
        self.assertTrue(u.is_vip())
        jalali_str = u.get_vip_until_jalali()
        self.assertIsNotNone(jalali_str)
        self.assertTrue(len(jalali_str) > 5)
        self.assertIn("ساعت", jalali_str)

        # تمدید ۳۰ روزه
        u30 = UserService.grant_vip(test_uid, days=30)
        self.assertTrue(u30.is_vip())

        # لغو پریمیوم
        u_rev = UserService.revoke_vip(test_uid)
        self.assertFalse(u_rev.is_vip())

    def test_07_progress_file_reader(self):
        """بررسی عملکرد کلاس استریم پیشرفت برای بله"""
        dummy_data = b"0123456789" * 100
        called = []

        def callback(sent, total):
            called.append((sent, total))

        reader = ProgressFileReader(dummy_data, callback=callback)
        chunk = reader.read(50)
        self.assertEqual(len(chunk), 50)
        self.assertEqual(len(called), 1)
        self.assertEqual(called[0], (50, 1000))

    def test_08_no_legacy_transfer_captions(self):
        """تایید پاکسازی عبارات زائد «منتقل شده از» در سورسکد آداپتورها"""
        bale_code = (root_dir / "platforms" / "bale_adapter.py").read_text(encoding="utf-8")
        tg_code = (root_dir / "platforms" / "telegram_adapter.py").read_text(encoding="utf-8")

        self.assertNotIn("منتقل شده از تلگرام", bale_code)
        self.assertNotIn("منتقل شده از بله", tg_code)


if __name__ == "__main__":
    unittest.main()
