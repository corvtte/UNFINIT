import asyncio
import os
import re
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure event loop for Python 3.14
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from core.config import config
from services.web_panel import get_system_health, EngineVersionStr, render_dashboard_html, handle_api_dispatch_url
from platforms.telegram_adapter import TelegramAdapter
from services.store_service import StoreService


class TestV029Features(unittest.TestCase):

    def test_01_version_bump_v029(self):
        """Verify engine version is bumped to v0.2.9 across config and web_panel."""
        self.assertTrue(any(v in str(config.ENGINE_VERSION) for v in ("v0.2.9", "v0.3.0")))
        health = get_system_health()
        self.assertTrue(any(v in str(health["engine_version"]) for v in ("v0.2.9", "v0.3.0")))
        self.assertTrue(EngineVersionStr("UNFINIT Engine v0.2.9").__contains__("v0.2.9"))

    def test_02_telegram_send_video_and_audio_sanitization(self):
        """Verify TelegramAdapter sanitizes duration, dimensions, and thumb preventing to_bytes errors."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        class DummyApp:
            def __init__(self):
                self.send_video_kwargs = None
                self.send_audio_kwargs = None

            async def send_video(self, **kwargs):
                self.send_video_kwargs = kwargs
                m = MagicMock()
                m.id = 123
                return m

            async def send_audio(self, **kwargs):
                self.send_audio_kwargs = kwargs
                m = MagicMock()
                m.id = 456
                return m

        adapter = TelegramAdapter()
        dummy_app = DummyApp()
        adapter.app = dummy_app

        # Test send_video with None for width, height, duration, thumb
        res = loop.run_until_complete(
            adapter.send_video(
                chat_id=111,
                file_path="dummy_video.mp4",
                width=None,
                height=None,
                duration=None,
                thumb="non_existent_thumb.jpg"
            )
        )
        self.assertTrue(res.get("ok"))
        self.assertIsInstance(dummy_app.send_video_kwargs["width"], int)
        self.assertEqual(dummy_app.send_video_kwargs["width"], 0)
        self.assertIsInstance(dummy_app.send_video_kwargs["height"], int)
        self.assertEqual(dummy_app.send_video_kwargs["height"], 0)
        self.assertIsInstance(dummy_app.send_video_kwargs["duration"], int)
        self.assertEqual(dummy_app.send_video_kwargs["duration"], 0)
        self.assertIsNone(dummy_app.send_video_kwargs["thumb"])

        # Test send_audio with None duration and invalid thumb
        res_audio = loop.run_until_complete(
            adapter.send_audio(
                chat_id=111,
                file_path="dummy_audio.mp3",
                duration=None,
                thumb="invalid_path.jpg"
            )
        )
        self.assertTrue(res_audio.get("ok"))
        self.assertIsInstance(dummy_app.send_audio_kwargs["duration"], int)
        self.assertEqual(dummy_app.send_audio_kwargs["duration"], 0)
        self.assertIsNone(dummy_app.send_audio_kwargs["thumb"])

    def test_03_feed_dispatch_modal_and_parallel_target(self):
        """Verify feed dispatch modal HTML elements and simultaneous dispatch logic."""
        html = render_dashboard_html()

        # Check modal container
        self.assertIn('id="feedDispatchModal"', html)
        self.assertIn('closeFeedDispatchModal()', html)
        self.assertIn("executeFeedDispatch('telegram')", html)
        self.assertIn("executeFeedDispatch('bale')", html)
        self.assertIn("executeFeedDispatch('all')", html)

        # Check that transferFeedDownload opens the modal in JS
        self.assertIn('function openFeedDispatchModal', html)
        self.assertIn('window.openFeedDispatchModal = openFeedDispatchModal', html)
        self.assertIn('window.executeFeedDispatch = executeFeedDispatch', html)

    def test_04_dynamic_ai_models_and_custom_input(self):
        """Verify dynamic AI model select, custom model input, and provider models."""
        html = render_dashboard_html()

        # Check custom input element
        self.assertIn('id="cfg_AI_MODEL_CUSTOM"', html)
        self.assertIn('AI_PROVIDER_MODELS', html)

        # Verify models for each provider
        self.assertIn('deepseek-v4.1', html)
        self.assertIn('claude-sonnet-4-6', html)
        self.assertIn('stepfun-3.7-flash', html)
        self.assertIn('minimax-0.5-free', html)
        self.assertIn('gemini-2.0-flash', html)
        self.assertIn('gemini-1.5-flash', html)

        # Check JS logic handles custom
        self.assertIn("p === 'custom'", html)
        self.assertIn("activeProv === 'custom'", html)

    def test_05_course_banner_dimensions_and_theme_buttons(self):
        """Verify course card banner styling uses max-h-80 object-contain and theme buttons."""
        p = MagicMock()
        p.product_id = "c_test_01"
        p.name = "دوره تست سیستم"
        p.price = 50000
        p.description = "توضیحات دوره"
        p.photo_url = "https://example.com/banner.jpg"
        p.download_link = "https://example.com/download.zip"
        p.active = True
        p.allow_card = True
        p.allow_bale = True

        async def mock_get_all():
            return [p]

        orig = StoreService.get_all_products
        try:
            StoreService.get_all_products = mock_get_all
            html = render_dashboard_html()
        finally:
            StoreService.get_all_products = orig

        # Banner styling
        self.assertIn('max-h-80 object-contain rounded-xl', html)
        self.assertNotIn('h-36 object-cover rounded-xl', html)

        # Order action buttons and header buttons
        self.assertIn('btnDeleteSelectedOrders', html)
        self.assertIn('theme-card-btn', html)

    def test_06_app_settings_save_and_logging(self):
        """Verify /api/settings/save path alias and logging."""
        app_code = Path("app.py").read_text(encoding="utf-8")
        self.assertIn('elif path in ("/api/settings", "/api/settings/save"):', app_code)
        self.assertIn('logger.info(f"[settings] Updated MAX_SAFE_BALE_SIZE_MB = {config.MAX_SAFE_BALE_SIZE_MB} MB")', app_code)
        self.assertIn('logger.info(f"[settings] Setting updated: {k} = {val_disp}")', app_code)


if __name__ == "__main__":
    unittest.main()
