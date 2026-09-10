import unittest
import os
import re
import subprocess
from pathlib import Path
from core.config import config
from core.jalali import gregorian_to_jalali, format_to_jalali, get_shamsi_now_string
from services.web_panel import (
    render_dashboard_html,
    render_storefront_html,
    get_system_health,
    handle_store_get_orders
)
from services.store_service import StoreService, OrderItem, ProductItem

class TestV2573Fast(unittest.TestCase):
    def test_01_engine_version_and_clean_env(self):
        self.assertIn(config.ENGINE_VERSION, ("v25.7.3", "v25.7.4"))
        # env.example must be deleted, .env.example must exist
        self.assertFalse(os.path.exists("env.example"), "env.example must be deleted")
        self.assertTrue(os.path.exists(".env.example"), ".env.example must exist")
        with open(".env.example", encoding="utf-8") as f:
            content = f.read()
            self.assertTrue(any(f"ENGINE_VERSION={v}" in content for v in ("v25.7.3", "v25.7.4")))

    def test_02_health_and_titles_version(self):
        health = get_system_health()
        self.assertTrue(any(v in health["engine_version"] for v in ("v25.7.3", "v25.7.4")))
        dash_html = render_dashboard_html()
        self.assertTrue(any(f"UNFINIT Store Engine {v}" in dash_html for v in ("v25.7.3", "v25.7.4")))
        store_html = render_storefront_html()
        self.assertTrue(any(v in store_html for v in ("v25.7.3", "v25.7.4")))

    def test_03_jalali_calendar_accuracy(self):
        # 2026-09-09 is 18 Shahrivar 1405
        jy, jm, jd = gregorian_to_jalali(2026, 9, 9)
        self.assertEqual((jy, jm, jd), (1405, 6, 18))
        # 2026-03-21 is 1 Farvardin 1405
        self.assertEqual(gregorian_to_jalali(2026, 3, 21), (1405, 1, 1))
        # format_to_jalali
        formatted = format_to_jalali("2026-09-09 20:03:15")
        self.assertIn("شهریور", formatted)
        self.assertIn("1405", formatted)
        self.assertIn("20:03", formatted)

    def test_04_bale_adapter_photo_reply_markup_and_https(self):
        with open("platforms/bale_adapter.py", encoding="utf-8") as f:
            code = f.read()
        # send_photo and send_photo_by_id must have reply_markup
        self.assertIn("def send_photo(", code)
        self.assertIn("reply_markup: Optional[Dict[str, Any]] = None", code)
        self.assertIn("def send_photo_by_id(", code)
        # photo_url in send_invoice & create_invoice_link must ensure https
        self.assertIn('p_url.startswith("https://")', code)
        # Receipt forwarding in Bale must have NO second send_message
        self.assertIn("await bale.send_photo_by_id(admin_id, f_id, caption=admin_txt, reply_markup=admin_kb)", code)
        self.assertNotIn("await bale.send_message(admin_id, admin_txt, reply_markup=admin_kb)", code)

    def test_05_store_service_single_message_receipt(self):
        with open("services/store_service.py", encoding="utf-8") as f:
            code = f.read()
        # Approve and reject buttons text
        self.assertIn("✅ تایید سفارش و ارسال دوره", code)
        self.assertIn("❌ رد سفارش", code)
        self.assertIn("format_to_jalali", code)

    def test_06_store_orders_platform_and_payment_split(self):
        orders_resp = handle_store_get_orders()
        self.assertTrue(orders_resp["ok"])
        for ord_item in orders_resp.get("orders", []):
            self.assertIn(ord_item["platform"], ("telegram", "bale", "web"))
            self.assertIn(ord_item["payment_method"], ("card_to_card", "bale_online", "zarinpal"))
            self.assertIsInstance(ord_item["created_at"], str)

    def test_07_theme_variables_and_6px_scrollbars(self):
        dash_html = render_dashboard_html()
        self.assertIn("--card-bg: #0f172a;", dash_html)
        self.assertIn("--card-bg: #1e2030;", dash_html)
        self.assertIn("width: 6px;", dash_html)
        self.assertIn("UNFINIT Classic", dash_html)
        store_html = render_storefront_html()
        self.assertIn("width: 6px;", store_html)

    def test_08_storefront_and_dashboard_node_check(self):
        import tempfile
        store_html = render_storefront_html()
        scripts = re.findall(r"<script>(.*?)</script>", store_html, re.DOTALL)
        self.assertTrue(len(scripts) > 0)
        with tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w", encoding="utf-8") as tf:
            tf.write(scripts[0])
            tf_path = tf.name
        try:
            p = subprocess.run(["node", "--check", tf_path], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, f"Storefront script syntax error: {p.stderr}")
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

if __name__ == "__main__":
    unittest.main()
