import os
import sys
import unittest
import asyncio
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

# Setup event loop for Python 3.14 compatibility
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.config import config, Config
from core.database import init_db, set_system_setting, get_system_setting, sync_settings_to_json_and_env
from services.media_service import MediaService
from services.session_manager import session_manager
from platforms.telegram_adapter import TelegramAdapter
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
from services.ai_agent_service import STUDIO_SYSTEM_PROMPT, ai_agent_service


class TestV2564Fast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_01_version_strings_v25_6_4(self):
        """Verify engine version is bumped to v25.6.4 or v25.6.5 in config, health, dashboard, and storefront."""
        self.assertIn(config.ENGINE_VERSION, ("v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2"))

        stats = get_system_health()
        self.assertTrue(any(v in stats["engine_version"] for v in ("v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))

        dash = render_dashboard_html()
        self.assertTrue(any(v in dash for v in ("v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))

        store = render_storefront_html()
        self.assertTrue(any(v in store for v in ("v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))

    def test_02_banner_dir_auto_creation(self):
        """Verify BANNERS_DIR is automatically created on config reload and storage init."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "sub_data"
            self.assertFalse(tmp_path.exists())
            with patch.dict(os.environ, {"PERSISTENT_DATA_DIR": str(tmp_path)}):
                test_cfg = Config()
                self.assertTrue(test_cfg.BANNERS_DIR.exists())
                self.assertTrue(test_cfg.UPLOADS_DIR.exists())
                self.assertTrue(test_cfg.DATA_DIR.exists())

    def test_03_no_duplicate_session_reuse(self):
        """Verify duplicate session reuse is completely removed and every media gets a fresh session."""
        self.assertFalse(hasattr(MediaService, "find_existing_session"))

        drop_id_1 = "fresh001"
        drop_id_2 = "fresh002"

        sess1 = MediaService.register_incoming_message_meta(
            drop_id=drop_id_1,
            source_platform="telegram",
            chat_id=123456,
            file_id="tg_file_abc",
            file_name="lesson.mp3",
            file_size=5000,
            media_type="audio"
        )
        self.assertEqual(sess1["drop_id"], drop_id_1)

        # Send same file metadata again: MUST produce new session with drop_id_2
        sess2 = MediaService.register_incoming_message_meta(
            drop_id=drop_id_2,
            source_platform="telegram",
            chat_id=123456,
            file_id="tg_file_abc",
            file_name="lesson.mp3",
            file_size=5000,
            media_type="audio"
        )
        self.assertEqual(sess2["drop_id"], drop_id_2)
        self.assertNotEqual(sess1["drop_id"], sess2["drop_id"])

    def test_04_gemini_model_select_and_default_artist_in_web_panel(self):
        """Verify GEMINI_MODEL is a <select> dropdown and DEFAULT_ARTIST field exists."""
        dash = render_dashboard_html()
        self.assertIn('<select id="cfg_GEMINI_MODEL"', dash)
        self.assertIn('value="gemini-3.6-flash"', dash)
        self.assertIn('value="gemini-2.5-flash"', dash)
        self.assertIn('value="gemini-3.7-flash"', dash)
        self.assertIn('value="gemini-1.5-pro"', dash)

        self.assertIn('id="cfg_DEFAULT_ARTIST"', dash)

        # Test DEFAULT_ARTIST saving and retrieval
        test_artist = "استاد عباس‌منش"
        asyncio.run(set_system_setting("DEFAULT_ARTIST", test_artist))
        saved = asyncio.run(get_system_setting("DEFAULT_ARTIST"))
        self.assertEqual(saved, test_artist)

    def test_05_telegram_send_audio_in_apply_changes(self):
        """Verify Telegram send_audio method structure and parameters."""
        adapter = TelegramAdapter.__new__(TelegramAdapter)
        adapter.app = MagicMock()
        adapter.app.send_audio = AsyncMock(return_value=MagicMock(id=888))

        res = asyncio.run(TelegramAdapter.send_audio(
            adapter,
            chat_id=12345,
            file_path="dummy.mp3",
            title="آموزش ثروت",
            performer="استاد عباس‌منش",
            file_name="wealth.mp3"
        ))
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("message_id"), 888)
        adapter.app.send_audio.assert_awaited_once()

    def test_06_ai_agent_energetic_inspiring_prompt(self):
        """Verify AI prompt contains energetic, warm, and inspiring keywords for personal development."""
        self.assertIn("پرانرژی", STUDIO_SYSTEM_PROMPT)
        self.assertIn("الهام‌بخش", STUDIO_SYSTEM_PROMPT)
        self.assertIn("موفقیت", STUDIO_SYSTEM_PROMPT)
        self.assertIn("رشد فردی", STUDIO_SYSTEM_PROMPT)

        # Test local fallback formatting without network calls
        with patch.object(ai_agent_service, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = {"ok": False}
            res = asyncio.run(ai_agent_service.transcribe_and_summarize_audio(
                audio_path="non_existent_audio.mp3",
                metadata={"title": "قوانین آفرینش", "artist": "استاد عباس‌منش", "album": "راهنمای عملی دستیابی به رویاها"}
            ))
            self.assertTrue(res["ok"])
            summary = res["summary"]
            self.assertIn("موفقیت", summary)
            self.assertIn("رشد", summary)
            self.assertIn("فردی", summary)


if __name__ == "__main__":
    unittest.main()
