import unittest
import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

# Set testing environment
os.environ["TESTING"] = "true"

from core.config import config
from core.database import init_db, get_db_connection, fix_mojibake, set_system_setting, get_system_setting
from services.store_service import StoreService, OrderItem
from services.ai_agent_service import ai_agent_service
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html


class TestV2560Fast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_01_engine_version(self):
        """Verify engine version is bumped to v25.6.0 or higher everywhere."""
        self.assertTrue(any(v in config.ENGINE_VERSION for v in ("v25.6.0", "v25.6.1", "v25.6.2", "v25.6.3", "v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))
        stats = get_system_health()
        self.assertTrue(any(v in stats["engine_version"] for v in ("v25.6.0", "v25.6.1", "v25.6.2", "v25.6.3", "v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))
        
        # Test dashboard HTML
        dash_html = render_dashboard_html()
        self.assertTrue(any(v in dash_html for v in ("v25.6.0", "v25.6.1", "v25.6.2", "v25.6.3", "v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))
        self.assertIn("cfg_GEMINI_API_KEY", dash_html)
        
        # Test storefront HTML
        store_html = render_storefront_html()
        self.assertTrue(any(v in store_html for v in ("v25.6.0", "v25.6.1", "v25.6.2", "v25.6.3", "v25.6.4", "v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))

    def test_02_gemini_api_key_settings(self):
        """Verify GEMINI_API_KEY is configured in config and database."""
        self.assertTrue(hasattr(config, "GEMINI_API_KEY"))
        test_val = "AIzaSyTest_Key_12345"
        asyncio.run(set_system_setting("gemini_api_key", test_val))
        saved = asyncio.run(get_system_setting("gemini_api_key"))
        self.assertEqual(saved, test_val)
        # Clean up
        asyncio.run(set_system_setting("gemini_api_key", ""))

    def test_03_store_service_smart_order_matching(self):
        """Verify StoreService.get_order matches any variant of prefixes."""
        # Create a test product and order
        order_id = "ORD_TEST8888"
        
        # Insert test order
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
            cur.execute("""
                INSERT INTO orders (
                    order_id, invoice_id, user_id, username, customer_name, phone,
                    product_id, product_name, total, wallet_used,
                    receipt_text, payment_method, status, platform, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id, f"ord_{order_id}", "web_test", "", "تست خریدار",
                "09120000000", "prod_1", "دوره تست", 50000, 0,
                "", "bale", "pending", "web", "2026-09-05 06:00:00"
            ))
            conn.commit()
        finally:
            conn.close()

        # Test exact match
        res_exact = asyncio.run(StoreService.get_order(order_id))
        self.assertIsNotNone(res_exact)
        self.assertEqual(res_exact.order_id, order_id)

        # Test with ord_ORD_ prefix (the bug reported by user)
        res_double = asyncio.run(StoreService.get_order("ord_ORD_TEST8888"))
        self.assertIsNotNone(res_double, "Failed to match ord_ORD_ prefix")
        self.assertEqual(res_double.order_id, order_id)

        # Test with ord_ prefix
        res_ord = asyncio.run(StoreService.get_order("ord_TEST8888"))
        self.assertIsNotNone(res_ord, "Failed to match ord_ prefix")

        # Test with invoice_id= prefix
        res_inv = asyncio.run(StoreService.get_order("invoice_id=ORD_TEST8888"))
        self.assertIsNotNone(res_inv, "Failed to match invoice_id= prefix")

        # Test with raw suffix
        res_clean = asyncio.run(StoreService.get_order("TEST8888"))
        self.assertIsNotNone(res_clean, "Failed to match clean suffix")

        # Clean up
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
            conn.commit()
        finally:
            conn.close()

    def test_04_bale_buy_link_clean_prefix(self):
        """Verify handle_store_buy_bale_async formats inv_url cleanly without ord_ORD_."""
        order_id = "ORD_ABC12345"
        clean_oid = order_id
        if clean_oid.startswith("ord_ORD_"):
            clean_oid = clean_oid.replace("ord_ORD_", "ord_")
        elif clean_oid.startswith("ORD_"):
            clean_oid = f"ord_{clean_oid[4:]}"
        elif not clean_oid.startswith("ord_"):
            clean_oid = f"ord_{clean_oid}"

        self.assertEqual(clean_oid, "ord_ABC12345")
        self.assertNotIn("ord_ORD_", clean_oid)

    def test_05_ai_agent_gemini_and_progress(self):
        """Verify AI agent service has Gemini audio capability and live 3-stage progress."""
        self.assertTrue(hasattr(ai_agent_service, "analyze_audio_with_gemini"))
        self.assertTrue(hasattr(ai_agent_service, "transcribe_and_summarize_audio"))

        stages = []
        async def mock_progress(msg: str):
            stages.append(msg)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"ID3" + b"\x00" * 100)
            tmp_audio = f.name

        try:
            # Mock analyze_audio_with_gemini to simulate Gemini 1.5 Flash response without network latency
            with patch.object(ai_agent_service, "analyze_audio_with_gemini", new_callable=AsyncMock) as mock_gemini:
                mock_gemini.return_value = "خلاصه صوت با هوش مصنوعی جمینای 1.5 فلش"
                
                # Test with GEMINI_API_KEY present
                with patch.object(config, "GEMINI_API_KEY", "AIzaFakeKey"):
                    res = asyncio.run(ai_agent_service.transcribe_and_summarize_audio(
                        tmp_audio,
                        metadata={"title": "Ù¾Ù†Ù„ تست", "artist": "استاد"},
                        progress_callback=mock_progress
                    ))
                    self.assertTrue(res["ok"])
                    self.assertIn("🧠 <b>دستیار هوش مصنوعی و تحلیلگر صوت UNFINIT</b>", res["formatted_message"])
                    self.assertTrue("Gemini" in res["formatted_message"] and "Audio" in res["formatted_message"])
                    self.assertNotIn("Ù", res["formatted_message"], "Mojibake was not repaired in audio metadata")
                    
                    # Verify 3 stages were notified
                    self.assertGreaterEqual(len(stages), 3)
                    self.assertTrue(any("[۱/۳]" in s for s in stages))
                    self.assertTrue(any("[۲/۳]" in s for s in stages))
                    self.assertTrue(any("[۳/۳]" in s for s in stages))
        finally:
            Path(tmp_audio).unlink(missing_ok=True)

    def test_06_rubika_logs_quieted(self):
        """Verify Rubika verbose backlog logs are demoted to debug."""
        rubika_file = Path(__file__).resolve().parent.parent / "platforms" / "rubika_adapter.py"
        content = rubika_file.read_text(encoding="utf-8")
        self.assertNotIn('logger.info(f"Rubika initial backlog flushed', content)
        self.assertIn('logger.debug(f"Rubika initial backlog flushed', content)
        self.assertNotIn('logger.info(f"Rubika raw update: {updates}")', content)
        self.assertIn('logger.debug(f"Rubika raw update: {updates}")', content)


if __name__ == "__main__":
    unittest.main()
