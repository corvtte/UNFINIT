import os
import re
import tempfile
import subprocess
import py_compile
import unittest

from core.config import config
from services.media_service import clean_display_filename
from services.session_manager import session_manager
from services.web_panel import render_dashboard_html, render_storefront_html
from core.database import db_save_media_session, db_delete_media_session

class TestV2554Fast(unittest.TestCase):
    def test_compilation(self):
        py_compile.compile("app.py", doraise=True)
        py_compile.compile("core/config.py", doraise=True)
        py_compile.compile("services/web_panel.py", doraise=True)
        py_compile.compile("services/media_service.py", doraise=True)
        py_compile.compile("services/session_manager.py", doraise=True)
        py_compile.compile("platforms/bale_adapter.py", doraise=True)

    def test_persian_filename_unquoting(self):
        raw_persian = "%D9%85%D8%B9%D8%B1%D9%81%DB%8C_%D8%AF%D9%88%D8%B1%D9%87.mp3"
        clean = clean_display_filename(raw_persian)
        self.assertEqual(clean, "معرفی_دوره.mp3")

        prefixed_persian = "compressed_a1b2c3d4e5f6_%D9%85%D9%88%D8%B2%DB%8C%DA%A9.mp3"
        clean_prefixed = clean_display_filename(prefixed_persian)
        self.assertEqual(clean_prefixed, "موزیک.mp3")

    def test_sqlite_session_recovery(self):
        test_drop_id = "test_sqlite_recov_99"
        dummy_data = {"drop_id": test_drop_id, "audio_filename": "تست.mp3", "media_type": "audio", "file_id": "bale_fid_123"}
        db_save_media_session(test_drop_id, dummy_data)

        # Clear from memory
        session_manager._sessions.pop(test_drop_id, None)
        self.assertNotIn(test_drop_id, session_manager._sessions)

        # Should recover seamlessly from SQLite
        recov = session_manager.get_session(test_drop_id)
        self.assertIsNotNone(recov)
        self.assertEqual(recov.get("file_id"), "bale_fid_123")

        # Cleanup
        session_manager._sessions.pop(test_drop_id, None)
        db_delete_media_session(test_drop_id)

    def test_dashboard_js_syntax_clean(self):
        html = render_dashboard_html()
        scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
        self.assertGreaterEqual(len(scripts), 2)
        for i, s in enumerate(scripts):
            fd, path = tempfile.mkstemp(suffix='.js', text=True)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(s)
            p = subprocess.run(['node', '--check', path], capture_output=True)
            os.remove(path)
            self.assertEqual(p.returncode, 0, f"Script #{i+1} has JS syntax error")

    def test_version_strings(self):
        self.assertEqual(config.ENGINE_VERSION, "v25.5.4")
        dash_html = render_dashboard_html()
        store_html = render_storefront_html()
        self.assertIn("v25.5.4", dash_html)
        self.assertIn("v25.5.4", store_html)

if __name__ == "__main__":
    unittest.main()
