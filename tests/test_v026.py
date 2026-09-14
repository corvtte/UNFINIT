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
from services.ai_service import ai_service, format_model_badge
from platforms.bale_adapter import format_bale_transfer_progress


class TestV026Upgrade(unittest.TestCase):

    def test_version_bump(self):
        self.assertEqual(config.ENGINE_VERSION, "v0.2.6")
        health = get_system_health()
        self.assertIn("v0.2.6", health["engine_version"])
        self.assertTrue(EngineVersionStr("UNFINIT Engine v0.2.6").__contains__("v0.2.6"))

    def test_vyceai_config_defaults(self):
        self.assertEqual(config.AI_BASE_URL, "https://api.vyceai.com/v1")
        self.assertEqual(config.AI_MODEL, "deepseek-v4.1")

    def test_ai_model_badge_formatting(self):
        badge1 = format_model_badge("deepseek-v4.1")
        self.assertIn("DeepSeek-v4.1", badge1)
        self.assertTrue(badge1.startswith("\n\n🧠"))

        badge2 = format_model_badge("claude-sonnet-4-6")
        self.assertIn("Claude-Sonnet-4.6", badge2)

        badge3 = format_model_badge("agnes-3.0-flash")
        self.assertIn("Agnes-3.0-Flash", badge3)

        badge4 = format_model_badge("deepseek-v4-flash")
        self.assertIn("DeepSeek-v4-Flash", badge4)

    def test_bale_progress_formatting(self):
        msg = format_bale_transfer_progress(50 * 1024 * 1024, 100 * 1024 * 1024, 20.0, stage_title="دانلود: test_song.mp3")
        self.assertIn("test_song.mp3", msg)
        self.assertIn("50%", msg)
        self.assertIn("2.50 MB/s", msg)
        self.assertIn("50.00 MB", msg)
        self.assertIn("100.00 MB", msg)

    def test_bale_throttling_condition(self):
        def should_edit(now, last_edit_time, current_percent, last_percent):
            return ((now - last_edit_time >= 3.0 and current_percent - last_percent >= 5) or current_percent == 100)

        # Less than 3 seconds elapsed
        self.assertFalse(should_edit(102.0, 100.0, 10, 0))
        # 3 seconds elapsed but percent jump < 5%
        self.assertFalse(should_edit(103.5, 100.0, 4, 0))
        # 3 seconds elapsed and percent jump >= 5%
        self.assertTrue(should_edit(103.5, 100.0, 5, 0))
        self.assertTrue(should_edit(105.0, 100.0, 20, 10))
        # 100% completion always fires regardless of time or percent step
        self.assertTrue(should_edit(100.1, 100.0, 100, 99))

    def test_theme_switcher_and_logo_styles(self):
        html = render_dashboard_html()
        # Theme switcher rounded-full classes
        self.assertIn('appearance-none rounded-full bg-transparent border-0 outline-none w-full cursor-pointer px-3', html)
        self.assertIn('rounded-full overflow-hidden border border-slate-700', html)
        # Accent background styling for logos
        self.assertIn('id="headerLogoContainer" style="background: var(--accent-color, #06b6d4);"', html)
        self.assertIn('id="loginLogoContainer" style="background: var(--accent-color, #06b6d4);"', html)
        # VyceAI Accordion fields in HTML
        self.assertIn('id="cfg_AI_BASE_URL"', html)
        self.assertIn('id="cfg_AI_API_KEY"', html)
        self.assertIn('id="cfg_AI_MODEL"', html)
        self.assertIn('deepseek-v4.1', html)


if __name__ == "__main__":
    unittest.main()
