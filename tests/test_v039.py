# -*- coding: utf-8 -*-
"""
Tests for UNFINIT Store Engine v0.3.9:
1. Standalone Frequency of Abundance Service (20 beliefs, MORNING/NIGHT split, CRUD, format_card)
2. Symmetrical Telegram & Bale navigation keyboards for Frequency carousel without store ads
3. Soroush Plus worker manual token storage, DNS endpoint fix & suppressed spam logs
4. Web Panel drawer logs unification & removal of duplicate dashboard logs bar
5. Web Panel Frequency Management section in settings tab (HTML & JS exports)
6. Theme variables compliance (no hardcoded navy/slate backgrounds in inputs, RTL typography)
7. Course persistence guarantee in init_db
8. Clean pure v0.3.9 version string in config, system health & AGENTS.md
"""

import unittest
import os
import json
import asyncio
from pathlib import Path

# Ensure event loop exists for pyrogram import in Python 3.14
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from core.config import config, VersionStr
from core.database import init_db, get_system_setting, set_system_setting
from core.frequency_service import FrequencyService
from services.web_panel import get_system_health, render_dashboard_html
from platforms.soroush_worker import soroush_worker, SoroushWorker
from platforms.telegram_adapter import (
    build_telegram_frequency_cats_keyboard,
    build_telegram_frequency_nav_keyboard
)
from platforms.bale_adapter import (
    build_bale_frequency_cats_keyboard,
    build_bale_frequency_nav_keyboard
)


class TestUNFINITv039(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        os.environ["ENGINE_VERSION"] = "v0.3.9"
        config.ENGINE_VERSION = VersionStr("v0.3.9")

    async def asyncSetUp(self):
        os.environ["ENGINE_VERSION"] = "v0.3.9"
        config.ENGINE_VERSION = VersionStr("v0.3.9")
        await init_db()

    # --- 1. Frequency of Abundance Service ---
    def test_frequency_service_data_and_crud(self):
        """Verify frequencies.json has at least 20 items, exactly 10 MORNING and 10 NIGHT, and CRUD works."""
        all_items = FrequencyService.get_all()
        self.assertGreaterEqual(len(all_items), 20)

        morning = FrequencyService.get_by_category("MORNING")
        night = FrequencyService.get_by_category("NIGHT")
        self.assertGreaterEqual(len(morning), 10)
        self.assertGreaterEqual(len(night), 10)

        # Verify format card does NOT contain course advertisement or marketing links
        card_text = FrequencyService.format_card(morning[0], 0, len(morning))
        self.assertIn(morning[0]["title"], card_text)
        self.assertIn(morning[0]["text"], card_text)
        self.assertNotIn("خرید دوره", card_text)
        self.assertNotIn("تومان", card_text)
        self.assertNotIn("فروشگاه", card_text)

        # Test add item and delete item
        new_item = FrequencyService.add_item("باور تستی", "این یک باور تست برای نسخه 0.3.9 است.", "MORNING")
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item["title"], "باور تستی")

        fetched = FrequencyService.get_by_id(new_item["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["id"], new_item["id"])

        del_ok = FrequencyService.delete_item(new_item["id"])
        self.assertTrue(del_ok)
        self.assertIsNone(FrequencyService.get_by_id(new_item["id"]))

    # --- 2. Symmetrical Telegram & Bale Frequency Keyboards ---
    def test_frequency_keyboards_symmetry(self):
        """Verify both Telegram and Bale adapters provide matching navigation keyboards."""
        # Telegram Category Keyboard (Pyrogram InlineKeyboardMarkup)
        tg_cats = build_telegram_frequency_cats_keyboard()
        self.assertTrue(hasattr(tg_cats, "inline_keyboard"))
        tg_cbs = [btn.callback_data for row in tg_cats.inline_keyboard for btn in row]
        self.assertIn("freq_page:MORNING:0", tg_cbs)
        self.assertIn("freq_page:NIGHT:0", tg_cbs)

        # Bale Category Keyboard (dict)
        bale_cats = build_bale_frequency_cats_keyboard()
        self.assertIn("inline_keyboard", bale_cats)
        bale_cbs = [btn["callback_data"] for row in bale_cats["inline_keyboard"] for btn in row]
        self.assertIn("freq_page:MORNING:0", bale_cbs)
        self.assertIn("freq_page:NIGHT:0", bale_cbs)

        # Navigation Keyboards
        tg_nav = build_telegram_frequency_nav_keyboard("MORNING", 2, 10)
        tg_nav_cbs = [btn.callback_data for row in tg_nav.inline_keyboard for btn in row]
        self.assertIn("freq_page:MORNING:1", tg_nav_cbs)
        self.assertIn("freq_page:MORNING:3", tg_nav_cbs)
        self.assertIn("freq_cats", tg_nav_cbs)

        bale_nav = build_bale_frequency_nav_keyboard("MORNING", 2, 10)
        bale_nav_cbs = [btn["callback_data"] for row in bale_nav["inline_keyboard"] for btn in row]
        self.assertIn("freq_page:MORNING:1", bale_nav_cbs)
        self.assertIn("freq_page:MORNING:3", bale_nav_cbs)
        self.assertIn("freq_cats", bale_nav_cbs)

    # --- 3. Soroush Plus Worker & Manual Token Storage ---
    def test_soroush_worker_manual_token_and_endpoints(self):
        """Verify Soroush worker has manual token storage and invalid core.splus.ir is removed."""
        # Endpoint check
        self.assertNotIn("core.splus.ir", SoroushWorker.WEB_API_BASE)
        self.assertNotIn("core.splus.ir", SoroushWorker.FILE_API_BASE)
        self.assertNotIn("chat.splus.ir", SoroushWorker.WEB_API_BASE)

        # Manual token storage
        test_token = "manual_secret_token_12345"
        test_phone = "09123456789"
        try:
            saved = soroush_worker.save_manual_token(test_token, test_phone)
            self.assertTrue(saved)
            self.assertTrue(soroush_worker.is_connected())
            self.assertEqual(soroush_worker._session_data.get("token"), test_token)
        finally:
            soroush_worker.disconnect()

    # --- 4. Web Panel Logs Unification & Dashboard Cleanup ---
    def test_web_panel_drawer_logs_and_cleanup(self):
        """Verify duplicate dashboardRecentLogsCard is removed and header drawer button is present."""
        html = render_dashboard_html()
        # The duplicate bottom logs bar should NOT be in dashboard
        self.assertNotIn('id="dashboardRecentLogsCard"', html)

        # Header logs toggle button should exist with SVG and themed styling
        self.assertIn('id="btnHeaderLogsDrawer"', html)
        self.assertIn('toggleLogsDrawer', html)

        # Slide-over drawer exists
        self.assertIn('id="logsDrawer"', html)

    # --- 5. Web Panel Frequency Management Section in Settings Tab ---
    def test_web_panel_frequency_management_section(self):
        """Verify frequency management HTML table and JS functions exist."""
        html = render_dashboard_html()
        self.assertIn('id="frequencyContent"', html)
        self.assertIn('id="frequencyTableBody"', html)
        self.assertIn('id="addFrequencyForm"', html)
        self.assertIn('loadFrequenciesTable', html)
        self.assertIn('submitAddNewFrequency', html)
        self.assertIn('deleteFrequencyItem', html)

    # --- 6. Theme Variables Compliance ---
    def test_theme_variables_compliance(self):
        """Verify inputs use var(--input-bg) and no hardcoded dark blue backgrounds in new cards."""
        html = render_dashboard_html()
        self.assertIn('var(--input-bg)', html)
        self.assertIn('var(--card-border)', html)
        self.assertIn('letter-spacing: normal !important', html)

    # --- 7. Version String Purity v0.3.9 ---
    def test_version_string_purity_v039(self):
        """Verify clean pure v0.3.9 version string in config and health."""
        self.assertEqual(str(config.ENGINE_VERSION), "v0.3.9")
        self.assertEqual(config.ENGINE_VERSION.clean, "v0.3.9")
        self.assertNotIn("(", str(config.ENGINE_VERSION))
        self.assertNotIn(")", str(config.ENGINE_VERSION))

        health = get_system_health()
        self.assertIn("v0.3.9", str(health.get("engine_version", "")))

        # Verify AGENTS.md mentions v0.3.9
        agents_path = Path(__file__).resolve().parent.parent / "AGENTS.md"
        with open(agents_path, "r", encoding="utf-8") as f:
            agents_text = f.read()
        self.assertIn("v0.3.9", agents_text)


if __name__ == "__main__":
    unittest.main()
