import os
import json
import unittest
from pathlib import Path

from core.config import config
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html, get_all_themes
from platforms.soroush_worker import SoroushWorker
from platforms.bale_adapter import build_bale_frequency_nav_keyboard
from core.frequency_service import FrequencyService


class TestVersion039Features(unittest.TestCase):
    def setUp(self):
        self.themes_file = Path("data/themes.json")

    def test_01_themes_json_structure(self):
        """Verify data/themes.json is the Single Source of Truth with all required variables."""
        self.assertTrue(self.themes_file.exists(), "data/themes.json must exist")
        with open(self.themes_file, "r", encoding="utf-8") as f:
            themes = json.load(f)

        required_themes = [
            "default-dark", "catppuccin", "dracula", "tokyo-night",
            "vesper", "solarized-dark", "monokai", "one-dark-pro", "pure-dark"
        ]
        for t in required_themes:
            self.assertIn(t, themes, f"Theme {t} must be present in themes.json")

        required_vars = [
            "--bg-main", "--bg-card", "--bg-input", "--text-main",
            "--text-muted", "--border-color", "--accent-color", "--table-head-bg"
        ]
        for t_name, t_data in themes.items():
            self.assertIn("variables", t_data, f"Theme {t_name} must contain 'variables'")
            vars_dict = t_data["variables"]
            for r_var in required_vars:
                self.assertIn(r_var, vars_dict, f"Theme {t_name} missing standard variable {r_var}")
            # Ensure regression aliases exist
            self.assertIn("--card-bg", vars_dict)
            self.assertIn("--input-bg", vars_dict)

    def test_02_dashboard_html_themes_and_version(self):
        """Verify HTML renders data-theme, dynamic styles, and correct engine version."""
        dash_html = render_dashboard_html()
        self.assertIn('data-theme="', dash_html)
        self.assertIn('id="dynamicThemeStyles"', dash_html)
        self.assertIn("window.UNFINIT_THEMES =", dash_html)
        self.assertIn("applyAntigravityTheme", dash_html)
        self.assertIn(f"Vector Engine {config.ENGINE_VERSION}", dash_html)

        # Storefront dynamic version check
        store_html = render_storefront_html()
        self.assertIn(f">{config.ENGINE_VERSION}</span>", store_html)

    def test_03_engine_version_dynamism(self):
        """Verify ENGINE_VERSION is dynamically tracked in system health."""
        self.assertTrue(str(config.ENGINE_VERSION).startswith("v0."))
        health = get_system_health()
        self.assertIn(str(config.ENGINE_VERSION), health["engine_version"])

        # Verify core/config.py contains ENGINE_VERSION
        with open("core/config.py", "r", encoding="utf-8") as f:
            config_code = f.read()
        self.assertIn("ENGINE_VERSION", config_code)

    def test_04_soroush_gramjs_session_handling(self):
        """Verify SoroushWorker supports both raw dc2_auth_key and GramJS Web client JSON."""
        test_worker = SoroushWorker(session_name="soroush_test_v039")
        try:
            # 1. Test raw key
            raw_key = "a1b2c3d4e5f678901234567890abcdef"
            ok_raw = test_worker.save_manual_token(raw_key, phone="09120000001")
            self.assertTrue(ok_raw)
            self.assertTrue(test_worker.is_connected())
            st_raw = test_worker.get_status()
            self.assertEqual(st_raw["status"], "ONLINE")
            self.assertEqual(test_worker._session_data.get("token"), raw_key)

            # 2. Test GramJS JSON object
            gramjs_obj = {
                "dcId": 2,
                "dc2_auth_key": "fedcba09876543210987654321abcdef",
                "userId": "99887766"
            }
            gramjs_str = json.dumps(gramjs_obj)
            ok_json = test_worker.save_manual_token(gramjs_str, phone="09120000002")
            self.assertTrue(ok_json)
            self.assertTrue(test_worker.is_connected())
            st_json = test_worker.get_status()
            self.assertEqual(st_json["status"], "ONLINE")
            self.assertEqual(test_worker._session_data.get("token"), gramjs_obj["dc2_auth_key"])
            self.assertEqual(test_worker._session_data.get("user_id"), "99887766")
        finally:
            test_worker.disconnect()

    def test_05_faravani_frequency_and_bale_layout(self):
        """Verify FrequencyService and symmetric RTL Bale keyboard layout."""
        items = FrequencyService.get_all()
        self.assertGreaterEqual(len(items), 20)

        morning_items = FrequencyService.get_by_category("MORNING")
        night_items = FrequencyService.get_by_category("NIGHT")
        self.assertGreaterEqual(len(morning_items), 10)
        self.assertGreaterEqual(len(night_items), 10)

        # Bale RTL symmetric keyboard: [ بعدی ▶️ ] (idx 0), (counter) (idx 1), [ ◀️ قبلی ] (idx 2)
        kb = build_bale_frequency_nav_keyboard("MORNING", 0, len(morning_items))
        nav_row = kb["inline_keyboard"][0]
        self.assertIn("بعدی ▶️", nav_row[0]["text"])
        self.assertIn("از", nav_row[1]["text"])
        self.assertIn("◀️ قبلی", nav_row[2]["text"])


    def test_06_frequency_tab_and_drawer(self):
        """Verify standalone frequency tab, drawer trigger, and log drawer exist."""
        html = render_dashboard_html()
        self.assertIn('id="tab-frequencies"', html)
        self.assertIn('id="s-btn-tab-frequencies"', html)
        self.assertIn('id="btn-tab-frequencies"', html)
        self.assertIn('id="btnHeaderLogsDrawer"', html)
        self.assertIn('id="logsDrawer"', html)

    def test_07_frequency_import_export(self):
        """Verify FrequencyService import and export functions work accurately."""
        sample_items = [
            {"id": "test_1", "title": "تست ۱", "text": "متن تستی ۱", "category": "MORNING"},
            {"id": "test_2", "title": "تست ۲", "text": "متن تستی ۲", "category": "NIGHT"},
        ]
        original = FrequencyService.get_all()
        try:
            ok, count, msg = FrequencyService.import_items(sample_items, mode="replace")
            self.assertTrue(ok)
            self.assertEqual(count, 2)
            self.assertEqual(len(FrequencyService.get_all()), 2)
        finally:
            FrequencyService.import_items(original, mode="replace")
            self.assertEqual(len(FrequencyService.get_all()), len(original))


if __name__ == "__main__":
    unittest.main()
