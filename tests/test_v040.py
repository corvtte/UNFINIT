# -*- coding: utf-8 -*-
"""
Unit tests for UNFINIT Store Engine v0.4.0:
1. Absolute absence of phantom domain file.splus.ir in soroush worker and codebase
2. Global CSS theme overrides with !important in render_dashboard_html()
3. SoroushWorker userId extraction from GramJS session (account1 or direct userId) and masked phone display
4. Bale frequency carousel keyboard RTL order: [ بعدی ▶️ ] (idx 0), [ ◀️ قبلی ] (idx 2)
5. Engine version dynamic sync to v0.4.0 in config, health, dashboard and storefront
"""

import json
import os
import unittest
from pathlib import Path

from core.config import config
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
from platforms.soroush_worker import SoroushWorker
from platforms.bale_adapter import build_bale_frequency_nav_keyboard


class TestVersion040Features(unittest.TestCase):
    def setUp(self):
        self.themes_file = Path("data/themes.json")

    def test_01_no_phantom_file_splus_domain(self):
        """Ensure invalid domain file.splus.ir is completely removed from the project."""
        soroush_file = Path("platforms/soroush_worker.py")
        self.assertTrue(soroush_file.exists())
        with open(soroush_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("file.splus.ir", content, "file.splus.ir must not be in platforms/soroush_worker.py")

    def test_02_css_overrides_with_important(self):
        """Verify CSS overrides with !important exist in render_dashboard_html() to override Tailwind classes."""
        html = render_dashboard_html()
        self.assertIn('id="dynamicThemeStyles"', html)
        self.assertIn("!important", html)
        # Check critical CSS variable mappings
        self.assertIn("var(--bg-main", html)
        self.assertIn("var(--bg-card", html)
        self.assertIn("var(--bg-input", html)
        self.assertIn("var(--border-color", html)
        self.assertIn("var(--text-main", html)

    def test_03_soroush_userid_extraction_and_display(self):
        """Verify SoroushWorker extracts userId from GramJS session JSON and formats display properly."""
        worker = SoroushWorker(session_name="soroush_v040_test")
        gramjs_session = {
            "token": "test_auth_token_12345",
            "account1": {
                "userId": 987654321,
                "phone": "09121112233"
            }
        }
        res = worker.save_manual_token(gramjs_session)
        self.assertTrue(res)
        self.assertEqual(str(worker._session_data.get("user_id")), "987654321")
        self.assertEqual(worker._session_data.get("phone"), "09121112233")

        # Test masked phone / userId output
        masked = worker.get_masked_phone()
        self.assertIn("987654321", masked)

        # Test status
        status = worker.get_status()
        self.assertEqual(status["status"], "ONLINE")
        self.assertIn("987654321", str(status.get("masked_phone")))
        worker.disconnect()

    def test_04_bale_frequency_keyboard_rtl_symmetry(self):
        """Verify Bale carousel buttons Next is on left index 0 and Prev is on right index 2."""
        kb = build_bale_frequency_nav_keyboard(current_idx=2, total_count=10, category="MORNING")
        self.assertIsNotNone(kb)
        self.assertIn("inline_keyboard", kb)
        nav_row = kb["inline_keyboard"][0]
        self.assertEqual(len(nav_row), 3)

        # Index 0: Next
        self.assertIn("بعدی", nav_row[0]["text"])
        self.assertIn("▶️", nav_row[0]["text"])
        self.assertIn("freq_page:MORNING:3", nav_row[0]["callback_data"])

        # Index 1: Counter
        self.assertIn("3 از 10", nav_row[1]["text"])

        # Index 2: Prev
        self.assertIn("قبلی", nav_row[2]["text"])
        self.assertIn("◀️", nav_row[2]["text"])
        self.assertIn("freq_page:MORNING:1", nav_row[2]["callback_data"])

    def test_05_version_v040_sync(self):
        """Verify ENGINE_VERSION is at least v0.4.0 and synced across config, health, dashboard and storefront."""
        self.assertTrue(str(config.ENGINE_VERSION) >= "v0.4.0")
        health = get_system_health()
        self.assertIn(str(config.ENGINE_VERSION), health["engine_version"])

        dash_html = render_dashboard_html()
        self.assertIn(str(config.ENGINE_VERSION), dash_html)

        store_html = render_storefront_html()
        self.assertIn(str(config.ENGINE_VERSION), store_html)


if __name__ == "__main__":
    unittest.main()
