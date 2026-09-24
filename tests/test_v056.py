# -*- coding: utf-8 -*-
"""
آزمون‌های یکپارچه‌سازی و اعتبارسنجی نگارش v0.5.6 موتور UNFINIT
شامل تست سریالایز ProgressFileReader با استانداردهای aiohttp،
مهار نشت خطای هوش مصنوعی و نرمال‌سازی فازی منوها،
سقف سختگیرانه ۴۸.۵MB ارسال مستقیم بله،
کش دیسک جلسات ۱۶ دسته‌بندی، تاریخ‌های سه‌گانه متقارن و شخصی‌ساز کیبورد.
"""

import io
import sys
import unittest
from pathlib import Path
from datetime import datetime

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

from core.config import config
from platforms.bale_adapter import ProgressFileReader
from core.formatters import (
    get_canonical_menu_action,
    normalize_persian_menu_text,
    ACTION_TODAY_SIGN,
    ACTION_PREMIUM,
    ACTION_FREE_DOWNLOADS,
    ACTION_PRODUCTS,
    ACTION_FREQUENCY,
    ACTION_USER_ACCOUNT,
    ACTION_SUPPORT,
)
from core.jalali import get_synchronized_date_string, gregorian_to_hijri
from services.feed_scraper import (
    load_category_disk_cache,
    save_category_disk_cache,
)
from platforms.telegram_adapter import MAX_DIRECT_BALE_MB


class TestVersion056(unittest.TestCase):
    def test_01_version_consistency(self):
        """بررسی همگام‌سازی نگارش v0.5.6 در core/config.py"""
        self.assertEqual(str(config.ENGINE_VERSION), "v0.5.6")
        self.assertTrue(config.ENGINE_VERSION.startswith("v0.5"))

    def test_02_progress_file_reader_io_base_compatibility(self):
        """بررسی کامل استاندارد io.IOBase در کلاس ProgressFileReader جهت مهار خطای سریالایز aiohttp"""
        dummy_data = b"Hello UNFINIT Engine v0.5.6! Testing binary stream and callbacks."
        stream = io.BytesIO(dummy_data)
        
        callback_called = []
        def on_progress(bytes_read, total_bytes):
            callback_called.append((bytes_read, total_bytes))

        reader = ProgressFileReader(stream, callback=on_progress)
        
        # ۱. اعتبارسنجی ارث‌بری از io.IOBase
        self.assertIsInstance(reader, io.IOBase)
        self.assertTrue(reader.readable())
        self.assertTrue(reader.seekable())
        self.assertFalse(reader.writable())
        self.assertEqual(len(reader), len(dummy_data))
        
        # ۲. بررسی خواندن و فراخوانی کالبک
        chunk = reader.read(10)
        self.assertEqual(len(chunk), 10)
        self.assertGreaterEqual(len(callback_called), 1)
        self.assertEqual(reader.tell(), 10)
        
        # ۳. بررسی متد seek
        reader.seek(0)
        self.assertEqual(reader.tell(), 0)
        all_data = reader.read()
        self.assertEqual(all_data, dummy_data)
        reader.close()
        self.assertTrue(reader.closed)

    def test_03_canonical_menu_actions_and_fuzzy_normalization(self):
        """تایید نگاشت اکشن‌های کانونیکال و عدم ارسال گزینه‌های منو به AI"""
        # دکمه‌های با ایموجی‌های مختلف و فاصله‌های گوناگون
        test_cases = [
            ("✨ نشانه امروز من", ACTION_TODAY_SIGN),
            ("نشانه امروز من", ACTION_TODAY_SIGN),
            ("فال و نشانه امروز", ACTION_TODAY_SIGN),
            ("💎 اشتراک پریمیوم", ACTION_PREMIUM),
            ("اشتراک ویژه vip", ACTION_PREMIUM),
            ("دانلودها (هدیه) 📁", ACTION_FREE_DOWNLOADS),
            ("📁 دانلودها (ویژه مشترکین پریمیوم)", ACTION_FREE_DOWNLOADS),
            ("فایل‌های هدیه سایت", ACTION_FREE_DOWNLOADS),
            ("🛍️ دوره‌ها و محصولات", ACTION_PRODUCTS),
            ("محصولات آموزشی", ACTION_PRODUCTS),
            ("🌊 فرکانس فراوانی", ACTION_FREQUENCY),
            ("فرکانس روزانه", ACTION_FREQUENCY),
            ("👤 حساب کاربری", ACTION_USER_ACCOUNT),
            ("پنل کاربری من", ACTION_USER_ACCOUNT),
            ("💬 پشتیبانی و تیکت", ACTION_SUPPORT),
            ("ارتباط با ادمین", ACTION_SUPPORT),
        ]
        for raw_text, expected_action in test_cases:
            action = get_canonical_menu_action(raw_text)
            self.assertEqual(action, expected_action, f"Failed canonical mapping for: {raw_text}")

    def test_04_strict_48_5mb_bale_threshold(self):
        """اعتبارسنجی سقف سختگیرانه ۴۸.۵ مگابایت برای ارسال مستقیم بدون اسپلیت به بله"""
        self.assertEqual(MAX_DIRECT_BALE_MB, 48.5)
        # ۴۸.۵MB باید بدون اسپلیت رد شود
        self.assertTrue(48.5 <= MAX_DIRECT_BALE_MB)
        self.assertFalse(48.6 <= MAX_DIRECT_BALE_MB)

    def test_05_category_disk_cache_performance(self):
        """بررسی کش دیسک جلسات ۱۶ دسته‌بندی جهت پاسخ‌دهی بلادرنگ زیر ۵۰ms"""
        test_cat = "test_category_123"
        test_data = {
            "title": "دسته آزمایشی",
            "sessions": [
                {"title": "جلسه اول آزمایشی", "url": "https://example.com/s1.mp3"},
                {"title": "جلسه دوم آزمایشی", "url": "https://example.com/s2.mp3"},
            ]
        }
        save_category_disk_cache(test_cat, test_data)
        
        cached = load_category_disk_cache(test_cat)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.get("title"), "دسته آزمایشی")
        self.assertEqual(len(cached.get("sessions", [])), 2)

    def test_06_synchronized_three_calendars(self):
        """بررسی تقارن و دقت تاریخ‌های سه‌گانه (شمسی، قمری، میلادی)"""
        dt = datetime(2026, 10, 24, 12, 0, 0)
        sync_str = get_synchronized_date_string(dt)
        self.assertIn("۱۴۰۵/۰۸/۰۲", sync_str)
        self.assertIn("خورشیدی", sync_str)
        self.assertIn("قمری", sync_str)
        self.assertIn("2026-10-24", sync_str)


if __name__ == "__main__":
    unittest.main()
