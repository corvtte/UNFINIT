import unittest
import os
import re
import asyncio
import subprocess
import tempfile
from pathlib import Path
from core.config import config
from services.web_panel import (
    render_dashboard_html,
    render_storefront_html,
    get_system_health,
    handle_store_get_orders,
    handle_store_delete_order
)
from services.store_service import StoreService, OrderItem, ProductItem

class TestV2574Fast(unittest.TestCase):
    def test_01_version_v25_7_4_sync(self):
        self.assertEqual(config.ENGINE_VERSION, "v25.7.4")
        health = get_system_health()
        self.assertIn("v25.7.4", health["engine_version"])
        dash_html = render_dashboard_html()
        self.assertIn("v25.7.4", dash_html)
        store_html = render_storefront_html()
        self.assertIn("v25.7.4", store_html)
        self.assertTrue(os.path.exists(".env.example"))
        with open(".env.example", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("ENGINE_VERSION=v25.7.4", content)

    def test_02_bale_adapter_imports_and_safe_invoicing(self):
        with open("platforms/bale_adapter.py", encoding="utf-8") as f:
            code = f.read()
        # Essential imports
        self.assertIn("import os", code)
        self.assertIn("import sys", code)
        self.assertIn("import asyncio", code)
        self.assertIn("import json", code)
        # Safe photo_url logic (reject relative or invalid URLs to prevent Bale 400 error)
        self.assertIn('if final_photo_url and (final_photo_url.startswith("https://") or final_photo_url.startswith("http://")):', code)
        # Verify pure welcome text for regular users in start
        self.assertIn('await bale.send_message(chat_id, w_text, reply_markup=get_bale_customer_keyboard())', code)
        # Verify delivery message formatting via StoreService
        self.assertIn("StoreService.format_delivery_message", code)

    def test_03_telegram_adapter_receipt_and_welcome(self):
        with open("platforms/telegram_adapter.py", encoding="utf-8") as f:
            code = f.read()
        # Receipt submission in photo_handler
        self.assertIn("await_receipt", code)
        self.assertIn("uploads/receipts", code)
        self.assertIn("StoreService.submit_card_receipt", code)
        self.assertIn("StoreService.notify_admin_card_order", code)
        self.assertIn("فیش واریزی شما با موفقیت دریافت شد", code)
        # Regular customer start handler has pure welcome text
        self.assertIn('w_text = fix_mojibake(await get_system_setting("WELCOME_TEXT", config.WELCOME_TEXT)', code)
        self.assertIn("await message.reply_text(w_text, parse_mode=enums.ParseMode.HTML, reply_markup=get_customer_keyboard())", code)
        # Order approval sends complete blockquote access box via StoreService
        self.assertIn("StoreService.format_delivery_message", code)

    def test_04_store_service_products_and_order_deletion(self):
        # Default get_all_products(active_only=False)
        prods = asyncio.run(StoreService.get_all_products(active_only=False))
        self.assertIsInstance(prods, list)
        
        # Verify submit_card_receipt method exists and handles calls
        res = asyncio.run(StoreService.submit_card_receipt("non_existent_ord", receipt_file_id="fid_123"))
        self.assertTrue(res)

        # Verify delete_order method exists and handles calls
        res_del = asyncio.run(StoreService.delete_order("non_existent_ord"))
        self.assertTrue(res_del)

    def test_05_noora_model_trio_and_minimal_studio(self):
        dash_html = render_dashboard_html()
        # Verify the 3 specific free models in studio select
        self.assertIn('value="stepfun-3.7-flash"', dash_html)
        self.assertIn('value="mimo-v2.5-free"', dash_html)
        self.assertIn('value="qwen2.5-72b"', dash_html)
        # Verify settings config has select dropdown for cfg_NARA_MODEL
        self.assertIn('id="cfg_NARA_MODEL"', dash_html)
        self.assertIn('<select', dash_html)
        # Verify quick prompts bar is removed
        self.assertNotIn("quick-prompts", dash_html)
        self.assertNotIn("نوشتن سناریو", dash_html)

    def test_06_orders_table_delete_button_and_api(self):
        dash_html = render_dashboard_html()
        # Verify delete button and js function in dashboard
        self.assertIn("deleteStoreOrder", dash_html)
        self.assertIn("🗑 حذف", dash_html)
        # Verify app.py has the route
        with open("app.py", encoding="utf-8") as f:
            app_code = f.read()
        self.assertIn("/api/store/orders/delete", app_code)
        self.assertIn("handle_store_delete_order", app_code)

    def test_07_javascript_syntax_cleanliness(self):
        # Test storefront JS
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

        # Test dashboard JS
        dash_html = render_dashboard_html()
        dash_scripts = re.findall(r"<script>(.*?)</script>", dash_html, re.DOTALL)
        self.assertTrue(len(dash_scripts) > 0)
        with tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w", encoding="utf-8") as tf:
            tf.write(dash_scripts[0])
            dash_path = tf.name
        try:
            p = subprocess.run(["node", "--check", dash_path], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, f"Dashboard script syntax error: {p.stderr}")
        finally:
            if os.path.exists(dash_path):
                os.remove(dash_path)

if __name__ == "__main__":
    unittest.main()
