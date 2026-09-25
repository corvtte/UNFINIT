"""
مجموعه آزمون‌های خودکار نگارش v0.5.7 موتور UNFINIT (UNFINIT Store Engine)
این تست‌ها صحت ۱۷ دسته‌بندی استخراج‌شده زنده، صفحه‌بندی ?page=، استخراج کاورهای لود تنبل،
نوار پیشرفت FFmpeg، کیبورد ۵ دکمه‌ای MAIN_KEYBOARD_LAYOUT و ابزارهای مدیریت دوره را بررسی می‌کنند.
"""

import unittest
import sys
from pathlib import Path

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
from services.abasmanesh_crawler import (
    OFFICIAL_17_CATEGORIES,
    extract_thumbnail_url,
    build_page_url,
    AbasmaneshCrawler
)
from services.feed_scraper import feed_scraper, ABASMANESH_PREMIUM_CATEGORIES, get_all_categories
from media.compressor import SmartVideoCompressor
from platforms.telegram_adapter import get_customer_keyboard
from platforms.bale_adapter import get_bale_customer_keyboard
from services.store_service import StoreService

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


class TestEngineVersion057(unittest.TestCase):
    """آزمون‌های اعتبارسنجی نگارش موتور v0.5.7"""

    def test_engine_version(self):
        self.assertEqual(str(config.ENGINE_VERSION), "v0.5.7")
        self.assertEqual(config.ENGINE_VERSION.clean, "v0.5.7")
        self.assertTrue("v0.5.7" in config.ENGINE_VERSION)


class Test17Categories(unittest.TestCase):
    """آزمون‌های ۱۷ دسته‌بندی رسمی و واقعی سایت عباس‌منش"""

    def test_categories_count(self):
        self.assertEqual(len(OFFICIAL_17_CATEGORIES), 17)
        self.assertEqual(len(ABASMANESH_PREMIUM_CATEGORIES), 17)

    def test_key_slugs_present(self):
        slugs = [c["slug"] for c in OFFICIAL_17_CATEGORIES]
        expected_slugs = [
            "free-download",
            "interview-with-master-abasmanesh",
            "live-sessions",
            "living-in-paradise",
            "cross-country-road-trip",
            "the-series-of-focus-on-positive-points",
            "indisputable-law-of-the-universe",
            "recognition-of-essential-from-nonessential",
            "practical-monotheism",
            "faith-takes-action",
            "the-power-of-mind-control",
            "wealth-creating-beliefs",
            "be-your-own-life-developer",
            "investing-in-yourself",
            "inner-piece",
            "peace-in-light-of-awareness",
            "evolutionary-steps-to-receive-guidance"
        ]
        for s in expected_slugs:
            self.assertIn(s, slugs, f"اسلاگ {s} باید در ۱۷ دسته موجود باشد.")

    def test_categories_have_emojis_and_urls(self):
        for c in OFFICIAL_17_CATEGORIES:
            self.assertTrue(bool(c.get("emoji")), f"دسته {c.get('slug')} فاقد ایموجی است.")
            self.assertTrue(c.get("url", "").startswith("https://abasmanesh.com/fa/category/"), f"آدرس نامعتبر: {c.get('url')}")
            self.assertTrue(bool(c.get("title")), f"دسته {c.get('slug')} فاقد عنوان است.")

    def test_crawler_lookup(self):
        cat = AbasmaneshCrawler.get_category_by_id_or_slug("indisputable-law-of-the-universe")
        self.assertIsNotNone(cat)
        self.assertEqual(cat["title"], "قوانین بدون تغییر خداوند")


class TestPaginationAndThumbnails(unittest.TestCase):
    """آزمون‌های صفحه‌بندی با الگوی ?page= و مهار لود تنبل تصاویر"""

    def test_build_page_url(self):
        base = "https://abasmanesh.com/fa/category/free-download/"
        self.assertEqual(build_page_url(base, 1), base)
        self.assertEqual(build_page_url(base, 2), "https://abasmanesh.com/fa/category/free-download/?page=2")
        self.assertEqual(build_page_url("https://abasmanesh.com/fa/articles/", 3), "https://abasmanesh.com/fa/articles/?page=3")

    def test_extract_thumbnail_lazy_loading(self):
        if not BeautifulSoup:
            return

        # تست ۱: صفت data-src
        html1 = '<div class="card"><img data-src="https://cdn.example.com/cover1.jpg" src="data:image/svg+xml;base64,PHN2Zy8+"></div>'
        soup1 = BeautifulSoup(html1, "html.parser")
        self.assertEqual(extract_thumbnail_url(soup1), "https://cdn.example.com/cover1.jpg")

        # تست ۲: صفت srcset
        html2 = '<div class="card"><img src="data:image/gif" srcset="https://cdn.example.com/small.jpg 300w, https://cdn.example.com/large.jpg 800w"></div>'
        soup2 = BeautifulSoup(html2, "html.parser")
        self.assertEqual(extract_thumbnail_url(soup2), "https://cdn.example.com/large.jpg")

        # تست ۳: استایل background-image
        html3 = '<div class="card" style="background-image: url(\'https://cdn.example.com/bg.jpg\')"></div>'
        soup3 = BeautifulSoup(html3, "html.parser")
        self.assertEqual(extract_thumbnail_url(soup3), "https://cdn.example.com/bg.jpg")

        # تست ۴: مسیر نسبی
        html4 = '<div class="card"><img data-lazy-src="/uploads/pic.webp"></div>'
        soup4 = BeautifulSoup(html4, "html.parser")
        self.assertEqual(extract_thumbnail_url(soup4), "https://abasmanesh.com/uploads/pic.webp")


class TestKeyboardLayout(unittest.TestCase):
    """آزمون ساختار ۵ دکمه‌ای MAIN_KEYBOARD_LAYOUT"""

    def test_telegram_customer_keyboard(self):
        kb = get_customer_keyboard()
        self.assertIsNotNone(kb)
        # ۳ ردیف استاندارد
        self.assertEqual(len(kb.keyboard), 3)
        self.assertEqual(len(kb.keyboard[0]), 1)  # محصولات آموزشی
        self.assertEqual(len(kb.keyboard[1]), 2)  # نشانه امروز من، اشتراک پریمیوم
        self.assertEqual(len(kb.keyboard[2]), 2)  # دانلودها، حساب کاربری

    def test_bale_customer_keyboard(self):
        kb = get_bale_customer_keyboard()
        self.assertIn("keyboard", kb)
        self.assertEqual(len(kb["keyboard"]), 3)


class TestMediaAndStoreMethods(unittest.TestCase):
    """آزمون نوار پیشرفت FFmpeg و متدهای جدید دوره"""

    def test_ffmpeg_progress_method_exists(self):
        self.assertTrue(hasattr(SmartVideoCompressor, "_execute_ffmpeg_progress"))
        self.assertTrue(callable(SmartVideoCompressor.compress_if_needed))
        self.assertTrue(callable(SmartVideoCompressor.compress_video))

    def test_store_service_methods_exist(self):
        self.assertTrue(hasattr(StoreService, "delete_course_episode"))
        self.assertTrue(hasattr(StoreService, "create_course_from_category"))
        self.assertTrue(callable(StoreService.delete_course_episode))
        self.assertTrue(callable(StoreService.create_course_from_category))


if __name__ == "__main__":
    unittest.main()
