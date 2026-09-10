import unittest
import os
os.environ["TESTING"] = "true"
import json
import urllib.parse
from pathlib import Path

from core.config import config
from services.media_service import clean_display_filename

class TestV255Fast(unittest.TestCase):
    def test_01_version_bump(self):
        self.assertIn(config.ENGINE_VERSION, ("v0.1.0",))

    def test_02_bale_adapter_urllib_import(self):
        import platforms.bale_adapter as ba
        self.assertTrue(hasattr(ba, "urllib"))
        self.assertTrue(hasattr(ba.urllib, "parse"))

    def test_03_persian_filename_unquoting(self):
        expected = "معرفی_دوره_آموزشی.mp3"
        quoted = urllib.parse.quote(expected)
        unquoted = urllib.parse.unquote(quoted)
        cleaned = clean_display_filename(unquoted)
        self.assertEqual(cleaned, expected)

    def test_04_courses_canonical_integrity(self):
        courses_file = config.COURSES_JSON_FILE
        self.assertTrue(courses_file.exists())
        with open(courses_file, "r", encoding="utf-8") as f:
            courses = json.load(f)
        pids = [c["product_id"] for c in courses]
        self.assertEqual(len(pids), 3)
        self.assertEqual(pids, ["prod_01", "prod_02", "prod_03"])
        self.assertNotIn("gift_01", pids)

    def test_05_settings_clean_state(self):
        settings_file = config.SETTINGS_JSON_FILE
        self.assertTrue(settings_file.exists())
        with open(settings_file, "r", encoding="utf-8") as f:
            st = json.load(f)
        self.assertEqual(st.get("bale_payment_token", ""), "")
        self.assertEqual(st.get("tg_fjoin_channel", ""), "")
        self.assertIn("BALE_BOT_TOKEN", st)

    def test_06_database_seed_no_gift(self):
        from core.database import init_db, get_db_connection
        import asyncio
        asyncio.run(init_db())
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT product_id FROM products")
        pids = [r[0] for r in cur.fetchall()]
        conn.close()
        self.assertNotIn("gift_01", pids)
        self.assertEqual(sorted(pids), ["prod_01", "prod_02", "prod_03"])

if __name__ == "__main__":
    unittest.main()
