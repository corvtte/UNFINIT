"""
Unit tests for UNFINIT Store Engine v0.5.3 enhancements
"""
import unittest
import asyncio
from pathlib import Path
from media.compressor import SmartVideoCompressor, SmartVideoSplitter
from services.feed_scraper import feed_scraper, fetch_live_categories, get_all_categories
from core.sign_service import SignService
from core.config import config
import platforms.bale_adapter as bale_module


class TestVersion053(unittest.TestCase):

    def test_engine_version(self):
        """بررسی ارتقاء صحیح شماره نگارش به v0.5.3 یا بالاتر"""
        self.assertIn(str(config.ENGINE_VERSION), ("v0.5.3", "v0.5.4"))

    def test_compressor_alias_and_signature(self):
        """بررسی وجود نام مستعار compress_video و عدم پرتاب AttributeError"""
        self.assertTrue(hasattr(SmartVideoCompressor, "compress_video"))
        self.assertTrue(hasattr(SmartVideoCompressor, "compress_if_needed"))
        self.assertEqual(SmartVideoCompressor.compress_video, SmartVideoCompressor.compress_if_needed)

    def test_bale_escape_import(self):
        """بررسی وجود تابع escape در ماژول بله"""
        self.assertTrue(hasattr(bale_module, "escape"))
        self.assertTrue(callable(bale_module.escape))
        # تست صحت کارکرد escape
        escaped = bale_module.escape("<script>alert('xss')</script>")
        self.assertNotIn("<script>", escaped)

    def test_sign_caption_includes_lesson_text(self):
        """بررسی درج خودکار گزیده پیام و آموزش درس در کپشن نشانه امروز"""
        sign_data = {
            "title": "قانون فرکانس و احساس خوب",
            "tag": "قوانین جهان هستی",
            "lesson_text": "تمام اتفاقات زندگی ما به وسیله کانون توجه و احساسات درونی ما رقم می‌خورد.",
            "page_url": "https://abasmanesh.com/fa/sample-lesson/"
        }
        caption = SignService.format_sign_caption(sign_data)
        self.assertIn("گزیده پیام و آموزش درس", caption)
        self.assertIn("تمام اتفاقات زندگی ما به وسیله کانون توجه", caption)

    def test_feed_scraper_categories(self):
        """بررسی دریافت دسته‌بندی‌ها از feed_scraper"""
        cats = feed_scraper.get_all_categories()
        self.assertIsInstance(cats, list)
        self.assertGreaterEqual(len(cats), 16)
        first_cat = cats[0]
        self.assertIn("slug", first_cat)
        self.assertIn("title", first_cat)
        self.assertIn("url", first_cat)

    def test_async_fetch_live_categories(self):
        """بررسی متد غیرهمگام fetch_live_categories"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            cats = loop.run_until_complete(feed_scraper.fetch_live_categories())
            self.assertIsInstance(cats, list)
            self.assertGreaterEqual(len(cats), 10)
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
