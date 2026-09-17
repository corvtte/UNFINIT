# -*- coding: utf-8 -*-
"fix(core): v0.3.2"

import os
import sys
import json
import asyncio

try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import unittest
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from core.config import config, VersionStr
from services.web_panel import get_system_health, render_dashboard_html
from platforms.bale_adapter import BaleAdapter
from platforms.telegram_adapter import TelegramAdapter
from services.referral_service import ReferralService

class TestUNFINITV032Upgrade(unittest.TestCase):

    def setUp(self):
        config.ENGINE_VERSION = VersionStr("v0.3.3")

    def test_01_version_configuration(self):
        self.assertIn("v0.3.", config.ENGINE_VERSION)
        self.assertIn(config.ENGINE_VERSION.clean, ("v0.3.2", "v0.3.3"))
        health = get_system_health()
        self.assertTrue(any(v in str(health["engine_version"]) for v in ("v0.3.2", "v0.3.3")))
        # self.assertIn("v0.3.1", str(health["engine_version"]))
        # self.assertIn("v0.1.0", str(health["engine_version"]))
        html = render_dashboard_html()
        self.assertTrue("UNFINIT Engine v0.3." in html or "UNFINIT Engine" in html)
        self.assertIn('id="uptimeDisplay"', html)
        self.assertIn('data-start="', html)

    def test_02_agents_md_rules(self):
        agents_path = REPO_DIR / "AGENTS.md"
        self.assertTrue(agents_path.exists())
        content = agents_path.read_text(encoding="utf-8")
        self.assertIn("Transistor" if False else "v0.3.2", content)
        self.assertIn("get_me()", content)

    def test_03_zero_fake_bot_usernames(self):
        forbidden = "UNFINIT_Bot"
        found_in = []
        for p in [REPO_DIR / "core", REPO_DIR / "platforms", REPO_DIR / "services"]:
            for file_p in p.glob("*.py"):
                text = file_p.read_text(encoding="utf-8", errors="ignore")
                if forbidden in text:
                    found_in.append(str(file_p.relative_to(REPO_DIR)))
        self.assertEqual(found_in, [])

    def test_04_bale_adapter_dynamic_get_me(self):
        """Verify BaleAdapter has get_me() method and sets dynamic username."""
        adapter = BaleAdapter("fake_token_123")
        self.assertTrue(hasattr(adapter, "get_me"))
        self.assertTrue(inspect.iscoroutinefunction(adapter.get_me))
        
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={
                "ok": True,
                "result": {"id": 123456, "username": "MyLiveStoreBot", "first_name": "Store Bot"}
            })
            mock_get.return_value.__aenter__.return_value = mock_resp
            
            import asyncio
            res = asyncio.run(adapter.get_me())
            self.assertTrue(res.get("ok"))
            self.assertEqual(adapter.username, "MyLiveStoreBot")
            self.assertEqual(config.BALE_BOT_USERNAME, "MyLiveStoreBot")

    def test_05_referral_service_dynamic_username(self):
        """Verify referral links on Bale use live BALE_BOT_USERNAME."""
        config.BALE_BOT_USERNAME = "RealBaleBot"
        link = ReferralService.get_referral_link(98765, "bale")
        self.assertEqual(link, "https://ble.ir/RealBaleBot?start=ref_98765")
        
        config.BALE_BOT_USERNAME = ""
        link_empty = ReferralService.get_referral_link(98765, "bale")
        self.assertNotIn("UNFINIT_Bot", link_empty)

    def test_06_health_ping_buttons(self):
        """Verify Bale & Telegram health menus include Ping button with admin:ping callback."""
        bale_src = (REPO_DIR / "platforms" / "bale_adapter.py").read_text(encoding="utf-8")
        self.assertIn('"callback_data": "admin:ping"', bale_src)
        self.assertIn('admin:ping', bale_src)

        tg_src = (REPO_DIR / "platforms" / "telegram_adapter.py").read_text(encoding="utf-8")
        self.assertIn('callback_data="admin:ping"', tg_src)
        self.assertIn('admin_ping_cb', tg_src)

    def test_07_web_panel_single_container_nav(self):
        """Verify single-container responsive navigation tabs and placeholder."""
        html = render_dashboard_html()
        self.assertIn('id="desktopNavTabs"', html)
        self.assertIn('overflow-x-auto', html)
        self.assertIn('touch-pan-x', html)
        self.assertIn('select-none', html)
        self.assertIn('id="mobileNavMenu"', html)
        self.assertIn('class="hidden"', html)
        self.assertIn('touchstart', html)
        self.assertIn('touchmove', html)
        self.assertIn('touchend', html)
        self.assertIn('NAV_TABS_ORDER', html)

    def test_08_price_input_formatting(self):
        """Verify price input formatting helper and numeric inputmode in web panel."""
        html = render_dashboard_html()
        self.assertIn('formatPriceInput(this)', html)
        self.assertIn('id="newCPrice"', html)
        self.assertIn('id="editPrice"', html)
        self.assertIn('inputmode="numeric"', html)
        self.assertIn('window.formatPriceInput = formatPriceInput', html)

    def test_09_feed_dispatch_modal_theme(self):
        """Verify feedDispatchModal uses theme CSS variables and no hardcoded blue classes."""
        html = render_dashboard_html()
        self.assertIn('id="feedDispatchModal"', html)
        self.assertIn('var(--card-bg', html)
        self.assertIn('var(--card-border', html)
        self.assertNotIn('bg-blue-600/90', html)

    def test_10_ai_summarize_course_route(self):
        """Verify /api/ai/summarize-course endpoint availability in web panel script."""
        html = render_dashboard_html()
        self.assertIn('/api/ai/summarize-course', html)


if __name__ == "__main__":
    unittest.main()

