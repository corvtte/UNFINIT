"""
آزمون‌های یکپارچگی مهندسی نگارش v0.4.9
UNFINIT Store Engine Comprehensive Test Suite
"""

import unittest
import asyncio
import re
from pathlib import Path

from core.config import config
from services.feed_scraper import (
    ABASMANESH_PREMIUM_CATEGORIES,
    _extract_articles_from_html,
    get_latest_free_downloads
)
from services.web_panel import get_system_health, render_dashboard_html


class TestV049Release(unittest.TestCase):

    def test_01_engine_version_sync(self):
        """بررسی همگام‌سازی نگارش v0.4.9 در پیکربندی و وضعیت سلامت"""
        self.assertEqual(str(config.ENGINE_VERSION), "v0.4.9")
        health = get_system_health()
        self.assertIn("v0.4.9", str(health["engine_version"]))

    def test_02_bale_aiohttp_scope_fix(self):
        """اطمینان از برطرف شدن خطای shadow import محلی aiohttp در بله"""
        bale_path = Path("platforms/bale_adapter.py")
        self.assertTrue(bale_path.exists())
        with open(bale_path, "r", encoding="utf-8") as f:
            content = f.read()

        # بررسی عدم وجود import aiohttp در بدنه توابع پولینگ و هندلرها
        lines = content.splitlines()
        for idx, line in enumerate(lines[50:], start=51):
            if "import aiohttp" in line and not line.strip().startswith("#"):
                self.fail(f"Local inline 'import aiohttp' found at line {idx}: {line}")

    def test_03_premium_16_categories_integrity(self):
        """بررسی ساختار ۱۶ دسته‌بندی رسمی عباس‌منش"""
        self.assertEqual(len(ABASMANESH_PREMIUM_CATEGORIES), 16)
        ids = [c["id"] for c in ABASMANESH_PREMIUM_CATEGORIES]
        self.assertEqual(ids, list(range(1, 17)))
        for c in ABASMANESH_PREMIUM_CATEGORIES:
            self.assertTrue(c["title"])
            self.assertTrue(c["url"].startswith("https://abasmanesh.com/fa/"))

    def test_04_feed_scraper_card_parser(self):
        """تست پارسر کارت‌های مقالات عباس‌منش با HTML نمونه"""
        sample_html = """
        <div class="article-grid">
            <div class="card card--media">
                <a class="card__media-link" href="https://abasmanesh.com/fa/sample-post/">
                    <img src="/storage/sample.webp" alt="عنوان نمونه مقاله">
                </a>
                <div class="card__body">
                    <a class="chip" href="#">درک عمیق‌تر قوانین خداوند</a>
                    <a href="https://abasmanesh.com/fa/sample-post/">عنوان نمونه مقاله</a>
                </div>
            </div>
        </div>
        """
        extracted = _extract_articles_from_html(sample_html, limit=10)
        self.assertEqual(len(extracted), 1)
        url, title, cover, tag = extracted[0]
        self.assertEqual(url, "https://abasmanesh.com/fa/sample-post/")
        self.assertEqual(title, "عنوان نمونه مقاله")
        self.assertIn("storage/sample.webp", cover)
        self.assertEqual(tag, "درک عمیق‌تر قوانین خداوند")

    def test_05_web_panel_products_subtabs_and_drag_drop(self):
        """بررسی وجود Drag & Drop و ۱۶ دسته در وب‌پنل"""
        html = render_dashboard_html()
        self.assertIn("productSubtabsContainer", html)
        self.assertIn('data-subtab="courses"', html)
        self.assertIn('data-subtab="audiobooks"', html)
        self.assertIn('data-subtab="vip"', html)
        self.assertIn("initProductSubtabsDragAndDrop", html)
        self.assertIn("unfinit_products_subtabs_order", html)
        self.assertIn("۱۶ دسته‌بندی رسمی عباس‌منش", html)

    def test_06_agents_and_changelog_rules(self):
        """بررسی بند ۵.۸ در AGENTS.md و وجود CHANGELOG.md"""
        agents_p = Path("AGENTS.md")
        changelog_p = Path("CHANGELOG.md")
        self.assertTrue(agents_p.exists())
        self.assertTrue(changelog_p.exists())

        agents_txt = agents_p.read_text(encoding="utf-8")
        self.assertIn("v0.4.9", agents_txt)
        self.assertIn("قانون طلایی بازتاب متناظر بک‌اند در وب‌پنل", agents_txt)

        changelog_txt = changelog_p.read_text(encoding="utf-8")
        self.assertIn("## [v0.4.9]", changelog_txt)


if __name__ == "__main__":
    unittest.main()
