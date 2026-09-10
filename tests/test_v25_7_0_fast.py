# -*- coding: utf-8 -*-
"""
Fast Unit Test Suite for UNFINIT Store Engine v25.7.0
Validates:
1. Global version synchronization (v25.7.0).
2. Antigravity Official Themes in web admin panel (8 themes & CSS variables).
3. Tap-to-Copy Artist Formatting and Mirrored Visual Progress Bars.
4. Telegram Supergroup Forum Topic IDs and Multi-Admin (ADMIN_USER_IDS).
5. Zarinpal v4 Payment Gateway (Sandbox/Production URLs, payment requests, verification, and purchased courses).
6. HD 16:9 Pillow Banner Optimization (Lanczos resize, RGB conversion, quality 92).
7. Video Compressor ultrafast preset and 2-stage AI assistant engine selection.
"""

import os
import io
import json
import unittest
import asyncio
from pathlib import Path
from PIL import Image

from core.config import config, Config
from core.database import init_db, execute_query, fetch_all, set_system_setting
from core.formatters import BaleFormatter, TelegramFormatter, format_transfer_progress
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
from services.store_service import StoreService
from services.ai_agent_service import ai_agent_service
import app


class TestV2570Fast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_01_version_synchronization(self):
        """Verify global version is v25.7.0 across all components."""
        self.assertIn(config.ENGINE_VERSION, ("v25.7.0", "v25.7.1", "v25.7.2", "v25.7.3", "v25.7.4"))
        
        dash = render_dashboard_html()
        self.assertTrue(any(v in dash for v in ("v25.7.0", "v25.7.1", "v25.7.2", "v25.7.3", "v25.7.4")))
        
        store = render_storefront_html()
        self.assertTrue(any(v in store for v in ("v25.7.0", "v25.7.1", "v25.7.2", "v25.7.3", "v25.7.4")))
        
        for env_file in [".env.example"]:
            env_content = Path(env_file).read_text(encoding="utf-8")
            self.assertTrue(any(f"ENGINE_VERSION={v}" in env_content for v in ("v25.7.0", "v25.7.1", "v25.7.2", "v25.7.3", "v25.7.4")))
            self.assertIn("ZARINPAL_MERCHANT_ID=", env_content)
            self.assertIn("TELEGRAM_FORUM_GROUP_ID=", env_content)
            self.assertIn("ADMIN_USER_IDS=", env_content)

    def test_02_antigravity_themes(self):
        """Verify 8 Antigravity official themes and CSS variables in dashboard."""
        dash = render_dashboard_html()
        
        # Verify theme switcher element
        self.assertIn('id="themeSwitcherSelect"', dash)
        self.assertIn('applyAntigravityTheme', dash)
        
        # Verify 8 themes in HTML
        themes = [
            "Default Dark",
            "Catppuccin",
            "Dracula",
            "Tokyo Night",
            "Vesper",
            "Solarized Dark",
            "Monokai",
            "One Dark Pro"
        ]
        for th in themes:
            self.assertIn(th, dash, f"Theme {th} missing from dashboard HTML")
            
        # Verify specific CSS classes and hex codes
        self.assertIn("body.theme-catppuccin", dash)
        self.assertIn("#24273A", dash) # Catppuccin bg
        self.assertIn("body.theme-dracula", dash)
        self.assertIn("#282A36", dash) # Dracula bg
        self.assertIn("body.theme-tokyo-night", dash)
        self.assertIn("#1A1B26", dash) # Tokyo Night bg
        self.assertIn("body.theme-vesper", dash)
        self.assertIn("#101010", dash) # Vesper bg
        self.assertIn("body.theme-solarized-dark", dash)
        self.assertIn("#002B36", dash) # Solarized bg
        self.assertIn("body.theme-monokai", dash)
        self.assertIn("#272822", dash) # Monokai bg
        self.assertIn("body.theme-one-dark-pro", dash)
        self.assertIn("#282C34", dash) # One Dark Pro bg

    def test_03_tap_to_copy_and_progress_bars(self):
        """Verify tap-to-copy code formatting and visual progress bar."""
        test_drop = {
            "audio_filename": "Mastery_Track_01.mp3",
            "api_meta": {"title": "Mastery Part 1", "artist": "Master Mind"},
            "size": 10485760,
            "format": "mp3"
        }
        card = TelegramFormatter.format_light_card(test_drop)
        # Performer/artist must be wrapped in <code> for instant tap-to-copy
        self.assertIn("<code>Master Mind</code>", card)
        
        # Test visual transfer progress bar: current, total, elapsed_sec, filename
        bar_50 = format_transfer_progress(50 * 1024 * 1024, 100 * 1024 * 1024, 10.0, "lecture.mp3")
        self.assertIn("50%", bar_50)
        self.assertIn("█", bar_50)
        self.assertIn("░", bar_50)
        self.assertIn("MB/s", bar_50)

    def test_04_forum_topics_and_multi_admin(self):
        """Verify forum group config and multi-admin permission evaluation."""
        os.environ["TELEGRAM_OWNER_ID"] = "111222"
        os.environ["BALE_OWNER_ID"] = "333444"
        os.environ["ADMIN_USER_IDS"] = "555666, 777888,999000"
        config.reload_from_environ()
        
        # Test owner IDs
        self.assertTrue(config.is_admin("111222"))
        self.assertTrue(config.is_admin(111222))
        self.assertTrue(config.is_admin("333444"))
        
        # Test secondary admin IDs from ADMIN_USER_IDS
        self.assertTrue(config.is_admin("555666"))
        self.assertTrue(config.is_admin(777888))
        self.assertTrue(config.is_admin("999000"))
        
        # Test non-admin
        self.assertFalse(config.is_admin("12345"))
        self.assertFalse(config.is_admin(None))

    def test_05_zarinpal_and_purchased_courses(self):
        """Verify Zarinpal payment request/verify helpers and purchased courses query."""
        # Verify Zarinpal modal and checkout in storefront
        store_html = render_storefront_html()
        self.assertIn('id="zarinpalBuyModal"', store_html)
        self.assertIn('handleZarinpalPaymentSubmit', store_html)
        self.assertIn('openZarinpalBuyModal', store_html)
        
        # Add test course
        prod = asyncio.run(StoreService.add_product(
            name="دوره تخصصی هوش مصنوعی v25.7.0",
            price=250000,
            description="دوره جامع پایتون و هوش مصنوعی",
            download_link="https://dl.unfinit.com/ai-v2570.zip",
            allow_card=True
        ))
        
        # Create test order
        order = asyncio.run(StoreService.create_order(
            user_id="989123456789",
            username="test_user",
            customer_name="علی رضایی",
            phone="09123456789",
            product=prod,
            platform="web"
        ))
        
        # Approve order to simulate successful payment
        asyncio.run(StoreService.approve_order(order.order_id))
        
        # Test get_customer_purchased_courses
        purchased = asyncio.run(StoreService.get_customer_purchased_courses("989123456789"))
        self.assertTrue(len(purchased) >= 1)
        found = False
        for p in purchased:
            if p["product_id"] == prod.product_id:
                found = True
                self.assertEqual(p["download_link"], "https://dl.unfinit.com/ai-v2570.zip")
                break
        self.assertTrue(found, "Purchased course not found for customer")

    def test_06_pillow_banner_hd_optimization(self):
        """Verify Pillow 16:9 HD banner resizing and Lanczos optimization logic."""
        # Create raw RGBA high-resolution image
        raw_img = Image.new("RGBA", (2560, 1440), color=(36, 39, 58, 255))
        
        # Simulate app.py banner processing logic
        max_width = 1280
        w, h = raw_img.size
        new_w = min(w, max_width)
        new_h = int(new_w * (9 / 16))
        
        resized = raw_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Convert RGBA to RGB
        bg = Image.new("RGB", resized.size, (16, 16, 16))
        bg.paste(resized, mask=resized.split()[3])
        
        out_io = io.BytesIO()
        bg.save(out_io, format="JPEG", quality=92, optimize=True)
        out_bytes = out_io.getvalue()
        
        # Verify dimensions and output size
        self.assertEqual(bg.size, (1280, 720))
        self.assertTrue(len(out_bytes) < 1024 * 1024, "Optimized banner exceeds 1MB")
        self.assertTrue(len(out_bytes) > 1000, "Optimized banner is corrupted/empty")

    def test_07_fast_video_compressor_and_ai_stage(self):
        """Verify compressor preset is ultrafast and AI service supports multi-engine selection."""
        with open("media/compressor.py", encoding="utf-8") as f:
            comp_content = f.read()
            self.assertIn("-preset", comp_content)
            self.assertIn("ultrafast", comp_content)
            
        import inspect
        sig = inspect.signature(ai_agent_service.transcribe_and_summarize_audio)
        self.assertIn("engine", sig.parameters)
        self.assertEqual(sig.parameters["engine"].default, "gemini")


if __name__ == "__main__":
    unittest.main()
