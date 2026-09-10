import unittest
import os
os.environ["TESTING"] = "true"
import asyncio
import sqlite3
from pathlib import Path

from core.config import config
from core.database import init_db, get_db_path, fix_mojibake, set_system_setting, get_system_setting

class TestV259Fast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_01_version_bump(self):
        self.assertTrue(config.ENGINE_VERSION >= "v25.5.9")

    def test_02_fix_mojibake(self):
        # 1. Broken latin-1 decoded Persian string
        raw_bytes = "پنل مدیریت".encode("utf-8")
        mojibake = raw_bytes.decode("latin1")
        self.assertEqual(fix_mojibake(mojibake), "پنل مدیریت")

        # 2. Already clean Persian string
        clean = "فروشگاه دوره‌های آموزشی UNFINIT"
        self.assertEqual(fix_mojibake(clean), clean)

        # 3. None or empty string fallback
        self.assertEqual(fix_mojibake(None), "فروشگاه دوره‌های آموزشی UNFINIT")
        self.assertEqual(fix_mojibake(""), "فروشگاه دوره‌های آموزشی UNFINIT")

    def test_03_database_startup_and_mojibake_cleanup(self):
        # Insert a simulated mojibake record
        asyncio.run(set_system_setting("STORE_NAME", "Ù¾ÙÙ ÙØ¯ÛØ±ÛØª"))
        # Run init_db which should purge any mojibake
        asyncio.run(init_db())

        val = asyncio.run(get_system_setting("STORE_NAME"))
        self.assertEqual(val, "فروشگاه دوره‌های آموزشی UNFINIT")
        self.assertIn("UNFINIT", config.STORE_NAME)
        self.assertNotIn("Ù", config.STORE_NAME)
        self.assertNotIn("Ø", config.STORE_NAME)

    def test_04_web_panel_dynamic_texts_and_version(self):
        from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
        health = get_system_health()
        self.assertTrue(any(v in health["engine_version"] for v in ("v25.5.9", "v25.6.0", "v25.6.1")))

        dash = render_dashboard_html()
        self.assertTrue(any(v in dash for v in ("v25.5.9", "v25.6.0", "v25.6.1")))
        self.assertIn("cfg_STORE_NAME", dash)
        self.assertIn("cfg_WELCOME_TEXT", dash)
        self.assertIn("مدیریت پیام‌ها و کانال‌ها", dash)

        store = render_storefront_html()
        self.assertTrue(any(v in store for v in ("v25.5.9", "v25.6.0", "v25.6.1")))
        self.assertIn("baleCustomerName", store)

        with open("services/web_panel.py", "r", encoding="utf-8") as f:
            wp_code = f.read()
        self.assertNotIn("v25.5.8", wp_code)
        self.assertIn("https://ble.ir/abasmanesh365bot?start=", wp_code)

    def test_05_bale_adapter_ord_start_and_metadata(self):
        with open("platforms/bale_adapter.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("param.startswith(\"ord_\")", code)
        self.assertIn("StoreService.get_order", code)
        self.assertIn("send_invoice", code)
        self.assertIn("metadata=drop", code)

    def test_06_telegram_adapter_metadata_fallback(self):
        with open("platforms/telegram_adapter.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("metadata=drop", code)

    def test_07_ai_agent_service_speech_recognition_and_fallback(self):
        from services.ai_agent_service import ai_agent_service
        self.assertTrue(hasattr(ai_agent_service, "transcribe_audio"))
        self.assertTrue(hasattr(ai_agent_service, "transcribe_and_summarize_audio"))

        with open("services/ai_agent_service.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("speech_recognition", code)
        self.assertIn("recognize_google", code)
        self.assertIn("language=\"fa-IR\"", code)
        self.assertIn("Metadata Copilot", code)

    def test_08_requirements_speech_recognition(self):
        with open("requirements.txt", "r", encoding="utf-8") as f:
            reqs = f.read()
        self.assertIn("SpeechRecognition>=3.10.0", reqs)

if __name__ == "__main__":
    unittest.main()
