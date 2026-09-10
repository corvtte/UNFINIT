import unittest
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Set test environment
os.environ["ENGINE_VERSION"] = "v25.6.1"
os.environ["GEMINI_MODEL"] = "gemini-3.6-flash"
os.environ["NARA_MODEL"] = "mimo-v2.5-free"

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.config import config
from core.database import (
    init_db,
    get_system_setting,
    set_system_setting,
    sync_settings_to_json_and_env
)
from services.web_panel import (
    get_system_health,
    render_dashboard_html,
    render_storefront_html
)
from services.ai_agent_service import AIAgentService, ai_agent_service

class TestV2561Fast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_01_engine_version_and_config(self):
        """Verify engine version is bumped to v25.6.1 or v25.6.2 and config defaults are correct."""
        # Test config
        self.assertTrue(config.ENGINE_VERSION in ("v25.6.1", "v25.6.2", "v25.6.3", "v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2"))
        self.assertTrue(config.GEMINI_MODEL.startswith("gemini-"))
        self.assertEqual(config.NARA_MODEL, "mimo-v2.5-free")

        stats = get_system_health()
        self.assertTrue(any(v in stats["engine_version"] for v in ("v25.6.1", "v25.6.2", "v25.6.3", "v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))

        # Test dashboard HTML contains model selector
        dash_html = render_dashboard_html()
        self.assertTrue(any(v in dash_html for v in ("v25.6.1", "v25.6.2", "v25.6.3", "v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))
        self.assertIn("cfg_GEMINI_API_KEY", dash_html)
        self.assertIn("cfg_GEMINI_MODEL", dash_html)
        self.assertTrue("gemini_models_list" in dash_html or "<select id=\"cfg_GEMINI_MODEL\"" in dash_html)
        self.assertIn("gemini-3.6-flash", dash_html)
        self.assertIn("gemini-3.7-flash", dash_html)
        
        # Test storefront HTML
        store_html = render_storefront_html()
        self.assertTrue(any(v in store_html for v in ("v25.6.1", "v25.6.2", "v25.6.3", "v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))

    def test_02_gemini_model_settings_db(self):
        """Verify GEMINI_MODEL is stored, retrieved, and synced in SQLite database."""
        self.assertTrue(hasattr(config, "GEMINI_MODEL"))
        test_model = "gemini-3.7-flash"
        asyncio.run(set_system_setting("gemini_model", test_model))
        saved = asyncio.run(get_system_setting("gemini_model"))
        self.assertEqual(saved, test_model)

        # Test sync_settings_to_json_and_env includes GEMINI_MODEL
        old_testing = os.environ.pop("TESTING", None)
        try:
            sync_settings_to_json_and_env()
        finally:
            if old_testing is not None:
                os.environ["TESTING"] = old_testing
        if config.SETTINGS_JSON_FILE.exists():
            import json
            with open(config.SETTINGS_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("GEMINI_MODEL", data)

    def test_03_ai_agent_service_model_and_timeout(self):
        """Verify AIAgentService uses mimo-v2.5-free, 180s timeout, and no mistral-large."""
        service = AIAgentService()
        self.assertIn("mimo-v2.5-free", service.SUPPORTED_FREE_MODELS)
        self.assertNotIn("mistral-large", service.SUPPORTED_FREE_MODELS)

        with patch.object(config, "NARA_API_KEY", "sk-fake-nara-key"):
            with patch("services.ai_agent_service.OpenAI") as mock_openai:
                client = service._get_client()
                mock_openai.assert_called_once()
                call_kwargs = mock_openai.call_args[1]
                self.assertEqual(call_kwargs["timeout"], 180.0)

    def test_04_analyze_audio_with_gemini_ffmpeg_and_cascade(self):
        """Verify analyze_audio_with_gemini invokes FFmpeg compression and cascades models."""
        service = AIAgentService()
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"dummy mp3 audio data")
            tmp_audio = f.name

        try:
            # Test with dummy Gemini API key
            with patch.object(config, "GEMINI_API_KEY", "AIzaFakeKey"):
                with patch.object(config, "GEMINI_MODEL", "gemini-3.7-flash"):
                    with patch("subprocess.run") as mock_subproc:
                        mock_subproc.return_value = MagicMock(returncode=0)
                        
                        # Mock aiohttp session
                        mock_resp = AsyncMock()
                        mock_resp.status = 200
                        mock_resp.json.return_value = {
                            "candidates": [
                                {"content": {"parts": [{"text": "تحلیل صوتی هوشمند جمینای"}]}}
                            ]
                        }

                        mock_session_inst = MagicMock()
                        mock_post_ctx = MagicMock()
                        mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
                        mock_post_ctx.__aexit__ = AsyncMock(return_value=None)
                        mock_session_inst.post.return_value = mock_post_ctx
                        mock_session_inst.__aenter__ = AsyncMock(return_value=mock_session_inst)
                        mock_session_inst.__aexit__ = AsyncMock(return_value=None)

                        with patch("aiohttp.ClientSession", return_value=mock_session_inst):
                            res = asyncio.run(service.analyze_audio_with_gemini(tmp_audio, "تست پرامپت"))
                            
                            # Verify ffmpeg compression command was called with compact settings
                            mock_subproc.assert_called_once()
                            cmd_called = mock_subproc.call_args[0][0]
                            self.assertIn("ffmpeg", cmd_called)
                            self.assertIn("-ac", cmd_called)
                            self.assertIn("1", cmd_called)
                            self.assertIn("-ar", cmd_called)
                            self.assertIn("16000", cmd_called)
                            self.assertIn("-b:a", cmd_called)
                            self.assertIn("32k", cmd_called)

                            self.assertEqual(res, "تحلیل صوتی هوشمند جمینای")
                            # Verify requested URL started with user's gemini-3.7-flash
                            first_call_url = mock_session_inst.post.call_args[0][0]
                            self.assertIn("gemini-3.7-flash", first_call_url)
        finally:
            Path(tmp_audio).unlink(missing_ok=True)

    def test_05_transcribe_and_summarize_audio_flow(self):
        """Verify transcribe_and_summarize_audio with 3-stage progress and Gemini integration."""
        stages = []
        async def mock_progress(msg):
            stages.append(msg)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"dummy mp3 data")
            tmp_audio = f.name

        try:
            with patch.object(ai_agent_service, "analyze_audio_with_gemini", new_callable=AsyncMock) as mock_gemini:
                mock_gemini.return_value = "خلاصه صوت با مدل چندگانه هوش مصنوعی جمینای"
                
                with patch.object(config, "GEMINI_API_KEY", "AIzaFakeKey"):
                    with patch.object(config, "GEMINI_MODEL", "gemini-3.6-flash"):
                        res = asyncio.run(ai_agent_service.transcribe_and_summarize_audio(
                            tmp_audio,
                            metadata={"title": "آموزش گیت", "artist": "مدرس"},
                            progress_callback=mock_progress
                        ))
                        self.assertTrue(res["ok"])
                        self.assertIn("🧠 <b>دستیار هوش مصنوعی و تحلیلگر صوت UNFINIT</b>", res["formatted_message"])
                        self.assertIn("Google Gemini", res["formatted_message"])
                        self.assertIn("gemini-3.6-flash", res["formatted_message"])
                        
                        # Verify all 3 stages were executed
                        self.assertGreaterEqual(len(stages), 3)
                        self.assertTrue(any("[۱/۳]" in s for s in stages))
                        self.assertTrue(any("[۲/۳]" in s for s in stages))
                        self.assertTrue(any("[۳/۳]" in s for s in stages))
        finally:
            Path(tmp_audio).unlink(missing_ok=True)

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("ENGINE_VERSION", None)
        config.reload_from_environ()

if __name__ == "__main__":
    unittest.main()
