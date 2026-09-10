import unittest
import os
os.environ["TESTING"] = "true"
import asyncio
import sqlite3
from pathlib import Path

from core.config import config
from core.database import init_db, get_db_path

class TestV258Fast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_01_version_bump(self):
        self.assertEqual(config.ENGINE_VERSION, "v25.5.8")

    def test_02_database_startup_cleanup(self):
        conn = sqlite3.connect(get_db_path())
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT product_id FROM products ORDER BY product_id")
            prod_ids = [row[0] for row in cursor.fetchall()]
            self.assertEqual(prod_ids, ["prod_01", "prod_02", "prod_03"], f"Expected only prod_01, prod_02, prod_03, found: {prod_ids}")
            
            # Verify no test media drops remain
            cursor.execute("SELECT drop_id FROM media_sessions WHERE drop_id LIKE '%test%' OR drop_id LIKE '%cleanup%'")
            test_drops = cursor.fetchall()
            self.assertEqual(len(test_drops), 0, f"Expected no test media drops, found: {test_drops}")
            
            # Verify clean store name in config
            self.assertIn("UNFINIT", config.STORE_NAME)
        finally:
            conn.close()

    def test_03_bale_adapter_shaparak_and_ai(self):
        with open("platforms/bale_adapter.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("invoice_", code)
        self.assertIn("ord_", code)
        self.assertIn("course_", code)
        self.assertIn("bmeta:ai_transcribe:", code)
        self.assertIn("action == \"ai_transcribe\"", code)
        self.assertIn("استخراج متن و کپشن با AI", code)

    def test_04_telegram_adapter_ai_transcribe(self):
        with open("platforms/telegram_adapter.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("smeta:ai_transcribe:", code)
        self.assertIn("action == \"ai_transcribe\"", code)
        self.assertIn("استخراج متن و کپشن با AI", code)

    def test_05_ai_agent_service_whisper_and_summarization(self):
        from services.ai_agent_service import AIAgentService, ai_agent_service
        self.assertTrue(hasattr(ai_agent_service, "transcribe_audio"))
        self.assertTrue(hasattr(ai_agent_service, "transcribe_and_summarize_audio"))
        with open("services/ai_agent_service.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("stepfun-3.7-flash", code)
        self.assertIn("whisper", code)

    def test_06_requirements_tgcrypto(self):
        with open("requirements.txt", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("tgcrypto>=1.2.5", content)
        self.assertNotIn("# tgcrypto", content)

    def test_07_web_panel_version_and_dark_css(self):
        from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
        health = get_system_health()
        self.assertIn("v25.5.8", health["engine_version"])
        dash = render_dashboard_html()
        self.assertIn("v25.5.8", dash)
        self.assertIn("#1e293b", dash)  # Dark input background CSS
        store = render_storefront_html()
        self.assertIn("v25.5.8", store)
        
        # Ensure no leftover v25.5.7 in web_panel.py
        with open("services/web_panel.py", "r", encoding="utf-8") as f:
            wp_code = f.read()
        self.assertNotIn("v25.5.7", wp_code)
        self.assertIn("btnBalePaySubmit", wp_code)
        self.assertIn("btn.disabled = false", wp_code)

if __name__ == "__main__":
    unittest.main()
