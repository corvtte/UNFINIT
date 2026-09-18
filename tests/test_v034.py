import unittest
import os
import json
import base64
import asyncio
from pathlib import Path

from core.config import config, VersionStr
from core.database import init_db
from services.image_service import image_service, ImageService
from services.store_service import StoreService, ProductItem
from services.referral_service import ReferralService
from services.web_panel import render_dashboard_html, get_system_health


SAMPLE_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
    <style>
        .icon-fill { fill: #333333; }
        .icon-stroke { stroke: #111111; stroke-width: 2; fill: none; }
    </style>
    <rect width="200" height="200" fill="#EEEEEE" />
    <circle cx="100" cy="100" r="50" class="icon-fill" fill="#444444" stroke="#222222" />
    <path d="M 50 50 L 150 150" class="icon-stroke" />
</svg>'''


class TestUNFINITV034Release(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config.ENGINE_VERSION = VersionStr("v0.3.6")
        asyncio.run(init_db())

    @classmethod
    def tearDownClass(cls):
        async def _cleanup():
            await StoreService.delete_product("test_course_v034")
        asyncio.run(_cleanup())

    def setUp(self):
        config.ENGINE_VERSION = VersionStr("v0.3.6")
        self.dash_html = render_dashboard_html()

    def test_01_pure_engine_version(self):
        """Rule 1.1 / v0.3.4: Pure ENGINE_VERSION string without parenthetical history."""
        self.assertIn(str(config.ENGINE_VERSION), ("v0.3.4", "v0.3.5", "v0.3.6"))
        self.assertIn(config.ENGINE_VERSION.clean, ("v0.3.4", "v0.3.5", "v0.3.6"))
        self.assertNotIn("(", str(config.ENGINE_VERSION))
        self.assertNotIn(")", str(config.ENGINE_VERSION))
        health = get_system_health()
        self.assertTrue(any(v in str(health.get("engine_version", "")) for v in ("v0.3.4", "v0.3.5", "v0.3.6")))

    def test_02_svg_recolor_suite(self):
        """SVG Studio Suite: XML recoloring with ElementTree, style block, and regex fallback."""
        # Recolor to pure white
        white_svg = image_service.recolor_svg(SAMPLE_SVG, "#FFFFFF")
        self.assertIsInstance(white_svg, str)
        self.assertIn("#FFFFFF", white_svg)
        # Verify none fill was preserved
        self.assertIn("none", white_svg.lower())

        # Recolor to pure black
        black_svg = image_service.recolor_svg(SAMPLE_SVG, "#000000")
        self.assertIsInstance(black_svg, str)
        self.assertIn("#000000", black_svg)

        # Recolor to brand blue
        blue_svg = image_service.recolor_svg(SAMPLE_SVG, "#3B82F6")
        self.assertIsInstance(blue_svg, str)
        self.assertIn("#3B82F6", blue_svg)

    def test_03_text_to_svg_typography(self):
        """SVG Studio Suite: Text-to-SVG vector generator."""
        text = "UNFINIT AI Studio"
        svg_text = image_service.text_to_svg(text, font_size=40, fill="#FFFFFF")
        self.assertIsInstance(svg_text, str)
        self.assertIn("<svg", svg_text)
        self.assertIn(text, svg_text)
        self.assertIn("#FFFFFF", svg_text)
        self.assertIn('font-size="40"', svg_text)

    def test_04_svg_to_image_conversion(self):
        """SVG Studio Suite: High-resolution conversion to PNG (transparent) and JPG."""
        svg_bytes = SAMPLE_SVG.encode("utf-8")
        
        # PNG conversion
        png_bytes = image_service.convert_svg_to_image(svg_bytes, fmt="PNG")
        self.assertIsInstance(png_bytes, bytes)
        self.assertGreater(len(png_bytes), 100)
        self.assertEqual(png_bytes[:4], b"\x89PNG")

        # JPG conversion
        jpg_bytes = image_service.convert_svg_to_image(svg_bytes, fmt="JPG")
        self.assertIsInstance(jpg_bytes, bytes)
        self.assertGreater(len(jpg_bytes), 100)
        self.assertEqual(jpg_bytes[:2], b"\xff\xd8")

    def test_05_course_episode_bundler(self):
        """Course Episode Bundler: add and retrieve course episodes in database."""
        async def _run_episode_test():
            test_pid = "test_course_v034"
            await StoreService.delete_product(test_pid)
            try:
                item = ProductItem(
                    product_id=test_pid,
                    name="دوره آزمایشی نسخه ۰.۳.۴",
                    price=50000,
                    description="تست سرفصل‌های داینامیک",
                    download_link="https://example.com/main.zip",
                    episodes=[]
                )
                await StoreService.create_product(item)
                
                # Add Episode 1
                res1 = await StoreService.add_course_episode(
                    product_id=test_pid,
                    title="قسمت اول - آشنایی با موتور برداری",
                    url="https://example.com/ep1.mp3",
                    filename="Ep01.mp3"
                )
                self.assertTrue(res1.get("ok"))
                self.assertEqual(res1.get("episode", {}).get("part"), 1)

                # Add Episode 2
                res2 = await StoreService.add_course_episode(
                    product_id=test_pid,
                    title="قسمت دوم - معماری سرفصل‌ها",
                    url="https://example.com/ep2.mp3",
                    filename="Ep02.mp3"
                )
                self.assertTrue(res2.get("ok"))
                self.assertEqual(res2.get("episode", {}).get("part"), 2)

                # Retrieve episodes
                eps = await StoreService.get_course_episodes(test_pid)
                self.assertEqual(len(eps), 2)
                self.assertEqual(eps[0]["title"], "قسمت اول - آشنایی با موتور برداری")
                self.assertEqual(eps[1]["title"], "قسمت دوم - معماری سرفصل‌ها")
            finally:
                await StoreService.delete_product(test_pid)

        asyncio.run(_run_episode_test())

    def test_06_web_panel_courses_cache_and_modals(self):
        """Web Panel: window.COURSES_CACHE and openEditCourseModal integration."""
        self.assertIn("window.COURSES_CACHE =", self.dash_html)
        self.assertIn("window.openEditCourseModal =", self.dash_html)
        self.assertIn("openEditCourseModal(", self.dash_html)
        self.assertIn("feedCourseSelect", self.dash_html)
        self.assertIn("addFeedToCourseEpisodes", self.dash_html)
        self.assertIn("window.addFeedToCourseEpisodes =", self.dash_html)

    def test_07_web_panel_svg_studio_ui(self):
        """Web Panel: SVG Studio Suite UI widgets and live preview."""
        self.assertIn("استودیوی وکتور SVG", self.dash_html)
        self.assertTrue(any(v in self.dash_html for v in ("Vector Engine v0.3.4", "Vector Engine v0.3.5", "Vector Engine v0.3.6")))
        self.assertIn('id="svgConvertForm"', self.dash_html)
        self.assertIn('id="svgRecolorPicker"', self.dash_html)
        self.assertIn('id="svgHexInput"', self.dash_html)
        self.assertIn('id="svgLivePreview"', self.dash_html)
        self.assertIn('id="svgDimensionsBadge"', self.dash_html)
        self.assertIn('id="svgTextInput"', self.dash_html)
        self.assertIn("handleSvgRecolor", self.dash_html)
        self.assertIn("downloadCurrentSvg", self.dash_html)
        self.assertIn("handleGenerateTextSvg", self.dash_html)

    def test_08_vector_keyboards_integration(self):
        """Bot Adapters: 6-button SVG vector menus in Bale and Telegram adapters."""
        with open("platforms/bale_adapter.py", "r", encoding="utf-8") as f:
            bale_code = f.read()
        self.assertIn("b_svg_recol:white:", bale_code)
        self.assertIn("b_svg_recol:black:", bale_code)
        self.assertIn("b_svg_hex:", bale_code)
        self.assertIn("b_svg_conv:png:", bale_code)
        self.assertIn("b_svg_conv:jpg:", bale_code)
        self.assertIn("b_svg_conv:svg:", bale_code)
        self.assertIn("b_c_episodes:", bale_code)
        self.assertIn("await_svg_hex", bale_code)

        with open("platforms/telegram_adapter.py", "r", encoding="utf-8") as f:
            tg_code = f.read()
        self.assertIn("tg_svg_recol:white:", tg_code)
        self.assertIn("tg_svg_recol:black:", tg_code)
        self.assertIn("tg_svg_hex:", tg_code)
        self.assertIn("tg_svg:png:", tg_code)
        self.assertIn("tg_svg:jpg:", tg_code)
        self.assertIn("tg_svg:svg:", tg_code)
        self.assertIn("tg_c_episodes:", tg_code)
        self.assertIn("await_svg_hex", tg_code)


if __name__ == "__main__":
    unittest.main()
