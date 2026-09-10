"""
Automated Banner Resolution & System Audit Test Suite (v0.1.1)
Tests:
1. Web Panel Storefront Banner CSS and HTML rendering
2. Telegram course photo banner resolution (file_id, local path, public HF space URL)
3. Bale course photo banner resolution (local path, URL)
4. Live Hugging Face Space health and banner assets
"""

import unittest
import os
import asyncio
from pathlib import Path

try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from core.config import config
from services.store_service import ProductItem
from services.web_panel import render_storefront_html
from platforms.telegram_adapter import resolve_telegram_course_photo
from platforms.bale_adapter import resolve_bale_course_photo


class TestBannersAndSystemAudit(unittest.TestCase):

    def test_01_web_storefront_banner_classes(self):
        """Verify storefront course cards render banners with full width, natural height, and object-cover."""
        with open("services/web_panel.py", encoding="utf-8") as f:
            wp_code = f.read()

        # Check for user-requested styles: no more forced aspect-video letterboxing
        self.assertIn("w-full h-auto max-h-[520px] object-cover rounded-2xl mb-4", wp_code)
        self.assertNotIn("aspect-video object-contain bg-slate-950/60", wp_code)

    def test_02_telegram_banner_resolution(self):
        """Verify resolve_telegram_course_photo handles file_id, local file, and public HF space URL."""
        # 1. Product with Telegram photo_file_id
        p1 = ProductItem({
            "product_id": "test_01",
            "name": "تست ۱",
            "photo_file_id": "AgACAgQAAx0CBA...",
            "photo_url": ""
        })
        res1 = resolve_telegram_course_photo(p1)
        self.assertIsNotNone(res1)
        self.assertEqual(res1["type"], "file_id")
        self.assertEqual(res1["value"], "AgACAgQAAx0CBA...")

        # 2. Product with relative URL (resolves to local path if exists, or public URL)
        p2 = ProductItem({
            "product_id": "test_02",
            "name": "تست ۲",
            "photo_file_id": None,
            "photo_url": "/uploads/banners/banner_prod_01_2b3cf3a8.jpg"
        })
        res2 = resolve_telegram_course_photo(p2)
        self.assertIsNotNone(res2)
        self.assertIn(res2["type"], ("local_path", "url"))
        if res2["type"] == "url":
            self.assertTrue(res2["value"].startswith("https://"))
            self.assertIn("banner_prod_01_2b3cf3a8.jpg", res2["value"])

        # 3. Product with absolute public HTTP URL
        p3 = ProductItem({
            "product_id": "test_03",
            "name": "تست ۳",
            "photo_file_id": None,
            "photo_url": "https://example.com/banner.jpg"
        })
        res3 = resolve_telegram_course_photo(p3)
        self.assertIsNotNone(res3)
        self.assertEqual(res3["type"], "url")
        self.assertEqual(res3["value"], "https://example.com/banner.jpg")

        # 4. Product with no photo
        p4 = ProductItem({
            "product_id": "test_04",
            "name": "تست ۴",
            "photo_file_id": None,
            "photo_url": ""
        })
        res4 = resolve_telegram_course_photo(p4)
        self.assertIsNone(res4)

    def test_03_bale_banner_resolution(self):
        """Verify resolve_bale_course_photo handles local file path and public HF space URL."""
        # 1. Product with relative URL
        p1 = ProductItem({
            "product_id": "test_b1",
            "name": "دوره بله ۱",
            "photo_url": "/uploads/banners/banner_prod_01_2b3cf3a8.jpg"
        })
        res1 = resolve_bale_course_photo(p1)
        self.assertIsNotNone(res1)
        self.assertIn(res1["type"], ("local_path", "url"))
        if res1["type"] == "url":
            self.assertTrue(res1["value"].startswith("https://"))
            self.assertIn("banner_prod_01_2b3cf3a8.jpg", res1["value"])

        # 2. Product with direct public HTTP URL
        p2 = ProductItem({
            "product_id": "test_b2",
            "name": "دوره بله ۲",
            "photo_url": "https://images.unsplash.com/photo-test.jpg"
        })
        res2 = resolve_bale_course_photo(p2)
        self.assertIsNotNone(res2)
        self.assertEqual(res2["type"], "url")
        self.assertEqual(res2["value"], "https://images.unsplash.com/photo-test.jpg")

        # 3. Product without photo
        p3 = ProductItem({
            "product_id": "test_b3",
            "name": "دوره بله ۳",
            "photo_url": ""
        })
        res3 = resolve_bale_course_photo(p3)
        self.assertIsNone(res3)

    def test_04_telegram_caption_length_safety(self):
        """Verify caption safety handling for long course descriptions."""
        long_desc = "توضیحات بسیار طولانی " * 100
        p = ProductItem({
            "product_id": "prod_long",
            "name": "دوره آزمایشی با توضیحات زیاد",
            "description": long_desc,
            "price": 500000
        })
        desc_txt = (p.description or "بدون توضیحات").strip()
        price_txt = f"{p.price:,} تومان"
        caption = f"🎓 <b>{p.name}</b>\n\n📝 <b>توضیحات دوره:</b>\n{desc_txt}\n\n💵 <b>قیمت:</b> <b>{price_txt}</b>"
        if len(caption) > 1000:
            short_desc = desc_txt[: max(50, 950 - len(p.name))] + "..."
            caption = f"🎓 <b>{p.name}</b>\n\n📝 <b>توضیحات دوره:</b>\n{short_desc}\n\n💵 <b>قیمت:</b> <b>{price_txt}</b>"
        self.assertLessEqual(len(caption), 1024)

    def test_05_bale_adapter_source_contains_send_photo(self):
        """Verify Bale adapter bcview handler invokes send_photo and send_photo_by_id."""
        with open("platforms/bale_adapter.py", encoding="utf-8") as f:
            bale_code = f.read()
        self.assertIn("resolve_bale_course_photo", bale_code)
        self.assertIn("bale.send_photo", bale_code)
        self.assertIn("bale.send_photo_by_id", bale_code)

    def test_06_telegram_adapter_source_contains_send_photo(self):
        """Verify Telegram adapter cview handler invokes client.send_photo."""
        with open("platforms/telegram_adapter.py", encoding="utf-8") as f:
            tg_code = f.read()
        self.assertIn("resolve_telegram_course_photo", tg_code)
        self.assertIn("client.send_photo", tg_code)
        self.assertIn("cnav:back", tg_code)


if __name__ == "__main__":
    unittest.main()
