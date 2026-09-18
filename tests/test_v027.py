import asyncio
import os
import unittest
from pathlib import Path

# Ensure event loop for Python 3.14
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from core.config import config
from services.web_panel import get_system_health, EngineVersionStr, render_dashboard_html
from services.ai_service import (
    AI_PROVIDERS,
    get_provider_config,
    generate_ai_response,
    format_ai_response_with_badge
)
from services.feed_scraper import get_latest_free_downloads


class TestV027Features(unittest.TestCase):

    def test_01_version_bump_v027(self):
        self.assertTrue(any(v in str(config.ENGINE_VERSION) for v in ('v0.2.7', 'v0.2.8', 'v0.2.9', 'v0.3.0', 'v0.3.1', 'v0.3.2', 'v0.3.3', 'v0.3.4', 'v0.3.5')))
        health = get_system_health()
        self.assertTrue(any(v in str(health["engine_version"]) for v in ('v0.2.7', 'v0.2.8', 'v0.2.9', 'v0.3.0', 'v0.3.1', 'v0.3.2', 'v0.3.3', 'v0.3.4', 'v0.3.5')))
        self.assertTrue(EngineVersionStr("UNFINIT Engine v0.2.7").__contains__("v0.2.7"))

    def test_02_admin_hub_cleanup_and_symmetry(self):
        dash = render_dashboard_html()
        self.assertIn("مدیریت دسترسی‌ها و شناسه مدیران", dash)
        self.assertIn("👑", dash)
        self.assertIn("grid grid-cols-1 md:grid-cols-2 gap-4", dash)
        self.assertIn('id="cfg_TELEGRAM_OWNER_ID"', dash)
        self.assertIn('id="cfg_BALE_OWNER_ID"', dash)
        self.assertIn('id="cfg_TELEGRAM_FORUM_GROUP_ID"', dash)
        self.assertIn('id="cfg_ADMIN_USER_IDS"', dash)
        self.assertIn('type="hidden" id="cfg_RUBIKA_OWNER_ID"', dash)

    def test_03_multi_provider_ai_hub(self):
        self.assertIn("vyceai", AI_PROVIDERS)
        self.assertIn("nara", AI_PROVIDERS)
        self.assertIn("gemini", AI_PROVIDERS)
        self.assertIn("custom", AI_PROVIDERS)

        self.assertTrue(hasattr(config, "VYCEAI_API_KEY"))
        self.assertTrue(hasattr(config, "AI_PROVIDER"))
        self.assertTrue(hasattr(config, "NARA_API_KEY"))
        self.assertTrue(hasattr(config, "GEMINI_API_KEY"))

        vyce_cfg = get_provider_config("vyceai")
        self.assertEqual(vyce_cfg["base_url"], "https://api.vyceai.com/v1")
        self.assertIn("deepseek-v4.1", vyce_cfg["model"])

        nara_cfg = get_provider_config("nara")
        self.assertEqual(nara_cfg["base_url"], "https://router.bynara.id/v1")

        gemini_cfg = get_provider_config("gemini")
        self.assertIn("googleapis.com", gemini_cfg["base_url"])

        # Strict No-Fake-Badge Policy
        res = asyncio.run(generate_ai_response("تست متن", provider="vyceai", api_key=""))
        self.assertFalse(res["ok"])
        self.assertIn("کلید دسترسی", res["error"])
        formatted = format_ai_response_with_badge(res)
        self.assertNotIn("🧠 DeepSeek-v4.1", formatted)
        self.assertNotIn("🧠 Claude", formatted)
        self.assertIn("❌", formatted)

    def test_04_live_logs_container_and_header(self):
        dash = render_dashboard_html()
        self.assertIn('dir="ltr"', dash)
        self.assertIn('font-mono text-xs max-h-96 overflow-y-auto bg-slate-950/90 text-emerald-400 p-4 rounded-xl border border-slate-800', dash)
        self.assertIn('clearLiveLogs()', dash)
        self.assertIn('window.clearLiveLogs = clearLiveLogs', dash)
        self.assertIn('handleAiProviderChange', dash)
        self.assertIn('class="rounded-full px-4', dash)

    def test_05_feed_scraper_module(self):
        items = asyncio.run(get_latest_free_downloads(limit=5))
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)
        first = items[0]
        self.assertIn("title", first)
        self.assertIn("links", first)

        dash = render_dashboard_html()
        self.assertIn('id="feedDownloadsContainer"', dash)
        self.assertIn('id="btnRefreshFeed"', dash)
        self.assertIn("رصد و دریافت هدایای دانلودی سایت", dash)
        self.assertIn("fetchFeedDownloads", dash)
        self.assertIn("transferFeedDownload", dash)


if __name__ == "__main__":
    unittest.main()
