import unittest
import os
import json
import base64
from pathlib import Path

from core.config import config
from services.image_service import image_service, ImageService
from services.referral_service import ReferralService
from services.web_panel import render_dashboard_html, get_system_health


SAMPLE_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
    <circle cx="50" cy="50" r="40" stroke="green" stroke-width="4" fill="yellow" />
</svg>'''


class TestV033Release(unittest.TestCase):
    def setUp(self):
        self.dash_html = render_dashboard_html()

    def test_pure_engine_version(self):
        """Rule 1.1 / v0.3.3: ENGINE_VERSION must be purely 'v0.3.3'."""
        self.assertEqual(str(config.ENGINE_VERSION), "v0.3.3")
        health = get_system_health()
        self.assertIn("v0.3.3", str(health.get("engine_version", "")))
        self.assertNotIn("(", str(config.ENGINE_VERSION))
        self.assertNotIn(")", str(config.ENGINE_VERSION))

    def test_svg_to_png_conversion(self):
        """Vector SVG Converter: PNG with transparency preservation."""
        svg_bytes = SAMPLE_SVG.encode("utf-8")
        png_bytes = image_service.convert_svg_to_png(svg_bytes)
        self.assertIsInstance(png_bytes, bytes)
        self.assertGreater(len(png_bytes), 100)
        # PNG signature check: 89 50 4E 47
        self.assertEqual(png_bytes[:4], b"\x89PNG")

    def test_svg_to_jpg_conversion(self):
        """Vector SVG Converter: JPG with solid background."""
        svg_bytes = SAMPLE_SVG.encode("utf-8")
        jpg_bytes = image_service.convert_svg_to_jpg(svg_bytes)
        self.assertIsInstance(jpg_bytes, bytes)
        self.assertGreater(len(jpg_bytes), 100)
        # JPEG signature check: FF D8
        self.assertEqual(jpg_bytes[:2], b"\xff\xd8")

    def test_mobile_off_canvas_drawer_markup(self):
        """Mobile Drawer: #mobileDrawer, #drawerOverlay and toggle function."""
        self.assertIn('id="mobileDrawer"', self.dash_html)
        self.assertIn('id="drawerOverlay"', self.dash_html)
        self.assertIn("toggleMobileDrawer", self.dash_html)

    def test_svg_converter_widget_in_studio(self):
        """Studio tab includes SVG Vector Converter widget and inputs."""
        self.assertIn('id="svgConvertForm"', self.dash_html)
        self.assertIn('id="svgFileInput"', self.dash_html)
        self.assertIn('id="svgOutputFormat"', self.dash_html)
        self.assertIn('id="btnSvgConvert"', self.dash_html)
        self.assertIn("handleSvgConvert", self.dash_html)

    def test_course_edit_by_id_and_js_serialization(self):
        """Course Edit: window.coursesData and openEditModalById."""
        self.assertIn("window.coursesData =", self.dash_html)
        self.assertIn("openEditModalById", self.dash_html)

    def test_zero_hardcoded_blue_classes_in_web_panel(self):
        """Theme consistency: Zero hardcoded bg-blue- or border-blue- classes."""
        panel_path = Path(__file__).resolve().parent.parent / "services" / "web_panel.py"
        with open(panel_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("bg-blue-", content)
        self.assertNotIn("border-blue-", content)

    def test_bale_and_telegram_referral_link_structure(self):
        """Referral links must use pure ref_{user_id} and dynamic bot usernames."""
        tg_link = ReferralService.get_referral_link("12345678", "telegram", "MyTgBot")
        self.assertEqual(tg_link, "https://t.me/MyTgBot?start=ref_12345678")

        bale_link = ReferralService.get_referral_link("98765432", "bale", "MyBaleBot")
        self.assertEqual(bale_link, "https://ble.ir/MyBaleBot?start=ref_98765432")

    def test_referral_code_parsing(self):
        """Parse referral code from various command patterns."""
        self.assertEqual(ReferralService.parse_referral_code("/start ref_112233"), "112233")
        self.assertEqual(ReferralService.parse_referral_code("ref_user99"), "user99")

    def test_config_settings_fields_present(self):
        """New configuration fields: APPLY_DEFAULT_ARTIST_TAG and CASHBACK_PERCENT."""
        self.assertTrue(hasattr(config, "APPLY_DEFAULT_ARTIST_TAG"))
        self.assertTrue(hasattr(config, "CASHBACK_PERCENT"))
        self.assertIn("cfg_APPLY_DEFAULT_ARTIST_TAG", self.dash_html)
        self.assertIn("cfg_CASHBACK_PERCENT", self.dash_html)


if __name__ == "__main__":
    unittest.main()
