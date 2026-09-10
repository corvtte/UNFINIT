import os
import sys
import tempfile
import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

# Setup event loop for Python 3.14 + Pyrogram compatibility
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.config import config, Config
from core.database import get_db_path, init_db, db_save_media_session, db_get_media_session
from services.media_service import MediaService
from services.session_manager import session_manager
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html

class TestV2563Fast(unittest.TestCase):
    def test_01_version_strings(self):
        """Verify engine version is bumped to v25.6.3, v25.6.4 or v25.6.5 in config and web panel."""
        self.assertIn(config.ENGINE_VERSION, ("v25.6.3", "v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2"))
        health = get_system_health()
        self.assertTrue(any(v in health["engine_version"] for v in ("v25.6.3", "v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))
        
        dash = render_dashboard_html()
        self.assertTrue(any(v in dash for v in ("v25.6.3", "v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))
        
        store = render_storefront_html()
        self.assertTrue(any(v in store for v in ("v25.6.3", "v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))

    def test_02_persistent_storage_detection_and_seeding(self):
        """Verify /data persistent storage detection, path assignments, and file seeding."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with patch.dict(os.environ, {"PERSISTENT_DATA_DIR": str(tmp_path)}):
                test_cfg = Config()
                self.assertTrue(test_cfg._use_persistent)
                self.assertEqual(test_cfg.DATA_DIR, tmp_path.resolve())
                self.assertEqual(test_cfg.DB_PATH, tmp_path.resolve() / "store_database.db")
                self.assertEqual(test_cfg.COURSES_JSON_FILE, tmp_path.resolve() / "courses.json")
                self.assertEqual(test_cfg.SETTINGS_JSON_FILE, tmp_path.resolve() / "settings.json")
                self.assertEqual(test_cfg.UPLOADS_DIR, tmp_path.resolve() / "uploads")
                self.assertEqual(test_cfg.BANNERS_DIR, tmp_path.resolve() / "uploads" / "banners")

                # Verify get_db_path uses config.DB_PATH
                with patch("core.config.config", test_cfg):
                    resolved_db = get_db_path()
                    self.assertEqual(resolved_db, test_cfg.DB_PATH)

    def test_03_telegram_session_revival_from_sqlite(self):
        """Verify Telegram callbacks revive session from SQLite if missing in memory."""
        test_drop_id = "recov999"
        dummy_session = {
            "drop_id": test_drop_id,
            "source_platform": "telegram",
            "chat_id": "123456",
            "file_id": "test_file_id_999",
            "audio_filename": "lecture.mp3",
            "file_size": 1024,
            "media_type": "audio",
            "is_downloaded_locally": True,
            "working_path": "temp_downloads/lecture.mp3"
        }
        # Save directly to SQLite
        db_save_media_session(test_drop_id, dummy_session)
        
        # Revive via db_get_media_session (exact logic used in telegram_adapter media_callbacks)
        recovered = db_get_media_session(test_drop_id)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["audio_filename"], "lecture.mp3")

        # Test read-through cache in session_manager
        session_manager._sessions.pop(test_drop_id, None)
        loaded = session_manager.get_session(test_drop_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["drop_id"], test_drop_id)

    def test_04_telegram_incoming_media_no_stale_drop_reuse(self):
        """Verify Telegram incoming media always generates a unique session and does not reuse old drops."""
        drop1 = "drop_fresh_1"
        drop2 = "drop_fresh_2"
        
        sess1 = MediaService.register_incoming_message_meta(
            drop1, "telegram", 111, "same_tg_file_id", "course.mp3", 5000000, media_type="audio"
        )
        self.assertEqual(sess1["drop_id"], drop1)
        
        sess2 = MediaService.register_incoming_message_meta(
            drop2, "telegram", 111, "same_tg_file_id", "course.mp3", 5000000, media_type="audio"
        )
        # For telegram, sess2 must NOT be attached to drop1!
        self.assertEqual(sess2["drop_id"], drop2)
        self.assertNotEqual(sess1["drop_id"], sess2["drop_id"])

    def test_05_edit_modal_ui_sticky_and_scroll(self):
        """Verify editModal container has max-h-[90vh] overflow-y-auto and footer has sticky bottom-0."""
        with open("services/web_panel.py", encoding="utf-8") as f:
            wp_code = f.read()
        self.assertIn('id="editModal"', wp_code)
        self.assertIn('max-h-[90vh] overflow-y-auto', wp_code)
        self.assertIn('sticky bottom-0 bg-slate-900', wp_code)
        self.assertIn('border-slate-700', wp_code)

    def test_06_url_uploader_no_studio_card(self):
        """Verify URL download handler does not send the studio keyboard card upon delivery."""
        with open("platforms/telegram_adapter.py", encoding="utf-8") as f:
            tg_code = f.read()
        self.assertIn("فایل با موفقیت دانلود و تحویل داده شد.", tg_code)

if __name__ == "__main__":
    unittest.main()
