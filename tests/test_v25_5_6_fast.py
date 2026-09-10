import unittest
import os
os.environ["TESTING"] = "true"
import json
import urllib.parse
from pathlib import Path

from core.config import config
from services.session_manager import session_manager
from core.database import init_db, db_save_media_session, db_get_media_session, db_delete_media_session

class TestV256Fast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import asyncio
        asyncio.run(init_db())

    def test_01_version_bump(self):
        self.assertEqual(config.ENGINE_VERSION, "v25.5.6")

    def test_02_bale_adapter_is_v_scoping(self):
        with open("platforms/bale_adapter.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn('is_v = bool(msg.get("video"))', code)
        idx_is_v = code.find('is_v = bool(msg.get("video"))')
        idx_use = code.find('media_type="video" if is_v else "audio"', idx_is_v)
        self.assertGreater(idx_use, idx_is_v, "is_v must be assigned before being checked")

    def test_03_persian_unquoting_in_bale(self):
        with open("platforms/bale_adapter.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("clean_title = urllib.parse.unquote(str(title)).strip()", code)
        self.assertIn("clean_performer = urllib.parse.unquote(str(performer)).strip()", code)
        self.assertIn("clean_caption = BaleFormatter.clean_text(urllib.parse.unquote(str(caption)))", code)

    def test_04_telegram_progress_bar(self):
        with open("platforms/telegram_adapter.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("در حال دانلود از مبدا", code)
        self.assertIn("progress=progress_hook", code)

    def test_05_instant_draft_tags_save(self):
        import asyncio
        from services.web_panel import handle_studio_edit_tags_async

        drop_id = "test_fast_drop_001"
        session_manager.update_session(drop_id, {
            "drop_id": drop_id,
            "filename": "test_track.mp3",
            "created_at": "2026-09-05T01:00:00"
        })

        payload = {
            "drop_id": drop_id,
            "title": "آموزش برنامه‌نویسی پیشرفته",
            "artist": "استاد مهدوی",
            "album": "دوره جامع پایتون",
            "new_filename": "Advanced_Python.mp3"
        }

        res = asyncio.run(handle_studio_edit_tags_async(payload))
        self.assertTrue(res.get("ok"))

        # Verify session in memory
        sess = session_manager.get_session(drop_id)
        self.assertIsNotNone(sess)
        self.assertEqual(sess.get("draft_tags", {}).get("title"), "آموزش برنامه‌نویسی پیشرفته")
        self.assertEqual(sess.get("draft_tags", {}).get("artist"), "استاد مهدوی")
        self.assertEqual(sess.get("draft_tags", {}).get("album"), "دوره جامع پایتون")
        self.assertEqual(sess.get("draft_tags", {}).get("new_filename"), "Advanced_Python.mp3")
        self.assertEqual(sess.get("embed_meta", {}).get("title"), "آموزش برنامه‌نویسی پیشرفته")

        # Verify SQLite DB persistence
        db_sess = db_get_media_session(drop_id)
        self.assertIsNotNone(db_sess)
        self.assertEqual(db_sess.get("draft_tags", {}).get("title"), "آموزش برنامه‌نویسی پیشرفته")

        # Cleanup
        session_manager.remove_session(drop_id)
        db_delete_media_session(drop_id)

    def test_06_studio_table_no_cover_and_sorting(self):
        from services.web_panel import render_studio_table_rows, render_dashboard_html

        dash = render_dashboard_html()
        # Verify table header has no cover th
        self.assertNotIn('<th class="py-3 px-2 text-center w-16">کاور</th>', dash)
        # Verify sort select exists
        self.assertIn('id="studioSortSelect"', dash)
        self.assertIn("changeStudioSort(this.value)", dash)

        # Setup 2 mock sessions
        session_manager.update_session("drop_a", {
            "drop_id": "drop_a",
            "filename": "bbb.mp3",
            "file_size": 1000,
            "created_at": "2026-09-05T01:00:00"
        })
        session_manager.update_session("drop_b", {
            "drop_id": "drop_b",
            "filename": "aaa.mp3",
            "file_size": 2000,
            "created_at": "2026-09-05T02:00:00"
        })

        # Test newest sort
        html_newest = render_studio_table_rows(sort_by="newest")
        self.assertIn("row_drop_b", html_newest)
        self.assertIn("row_drop_a", html_newest)
        self.assertLess(html_newest.find("row_drop_b"), html_newest.find("row_drop_a"))

        # Test oldest sort
        html_oldest = render_studio_table_rows(sort_by="oldest")
        self.assertLess(html_oldest.find("row_drop_a"), html_oldest.find("row_drop_b"))

        # Test size_desc sort
        html_size = render_studio_table_rows(sort_by="size_desc")
        self.assertLess(html_size.find("row_drop_b"), html_size.find("row_drop_a"))

        # Test name_asc sort
        html_name = render_studio_table_rows(sort_by="name_asc")
        self.assertLess(html_name.find("row_drop_b"), html_name.find("row_drop_a"))

        # Verify cutter button data attributes
        self.assertIn('data-drop-id="drop_a"', html_newest)
        self.assertIn('data-filename="bbb.mp3"', html_newest)

        # Cleanup
        session_manager.remove_session("drop_a")
        session_manager.remove_session("drop_b")

    def test_07_bale_payment_token_emerald_style(self):
        from services.web_panel import render_dashboard_html
        dash = render_dashboard_html()
        self.assertIn('id="cfg_BALE_PAYMENT_TOKEN"', dash)
        self.assertIn("border-emerald-500/80 text-emerald-400", dash)
        self.assertIn("focus:border-emerald-400", dash)

    def test_08_handle_studio_table_html_sort_param(self):
        from services.web_panel import handle_studio_table_html
        res = handle_studio_table_html(sort_by="oldest")
        self.assertTrue(res.get("ok"))
        self.assertIn("html", res)

if __name__ == "__main__":
    unittest.main()
