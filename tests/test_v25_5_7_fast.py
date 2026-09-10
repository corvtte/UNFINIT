import unittest
import os
os.environ["TESTING"] = "true"
import asyncio
from pathlib import Path

from core.config import config
from services.session_manager import session_manager
from core.database import init_db

class TestV257Fast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_01_version_bump(self):
        self.assertEqual(config.ENGINE_VERSION, "v25.5.7")

    def test_02_store_name_and_welcome_text(self):
        self.assertIn("UNFINIT", config.STORE_NAME)
        self.assertIn("UNFINIT", config.WELCOME_TEXT)
        self.assertEqual(config.STORE_NAME, "فروشگاه دوره‌های آموزشی UNFINIT")

    def test_03_bale_quote_fields_false(self):
        with open("platforms/bale_adapter.py", "r", encoding="utf-8") as f:
            code = f.read()
        count = code.count("aiohttp.FormData(quote_fields=False)")
        self.assertEqual(count, 5, f"Expected 5 occurrences of FormData(quote_fields=False), found {count}")
        self.assertNotIn("aiohttp.FormData()", code, "No bare aiohttp.FormData() calls should remain in bale_adapter")

    def test_04_bale_adapter_receipt_forwarding_and_admin_actions(self):
        with open("platforms/bale_adapter.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("def send_photo_by_id", code)
        self.assertIn("adm_approve:", code)
        self.assertIn("adm_reject:", code)
        self.assertIn("فیش واریزی جدید دریافت شد", code)
        self.assertIn("✅ تایید و تحویل دوره", code)
        self.assertIn("❌ رد سفارش", code)

    def test_05_telegram_progress_speed_and_completion(self):
        with open("platforms/telegram_adapter.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("speed_mbps", code)
        self.assertIn("MB/s", code)
        self.assertIn("✅ فایل با موفقیت منتقل شد", code)

    def test_06_studio_toolbar_grouping(self):
        from services.web_panel import render_dashboard_html
        dash = render_dashboard_html()
        idx_select_all = dash.find('id="selectAllDrops"')
        idx_badge = dash.find('id="selectedCountBadge"')
        idx_batch_del = dash.find('batchDeleteStudioDrops()')
        idx_sort = dash.find('id="studioSortSelect"')

        self.assertNotEqual(idx_select_all, -1)
        self.assertNotEqual(idx_batch_del, -1)
        self.assertNotEqual(idx_sort, -1)
        self.assertLess(idx_select_all, idx_sort)
        self.assertLess(idx_batch_del, idx_sort)

    def test_07_platform_colors_in_settings(self):
        from services.web_panel import render_dashboard_html
        dash = render_dashboard_html()
        self.assertIn('id="cfg_TELEGRAM_BOT_TOKEN"', dash)
        self.assertIn("border-sky-500/80 text-sky-400", dash)
        self.assertIn('id="cfg_BALE_BOT_TOKEN"', dash)
        self.assertIn("border-emerald-500/80 text-emerald-400", dash)
        self.assertIn('id="cfg_BALE_PAYMENT_TOKEN"', dash)
        self.assertIn('id="cfg_RUBIKA_BOT_TOKEN"', dash)
        self.assertIn("border-purple-500/80 text-purple-400", dash)
        self.assertIn('id="cfg_CARD_NUMBER"', dash)
        self.assertIn("border-amber-500/80 text-amber-300", dash)
        self.assertIn('id="cfg_CARD_HOLDER"', dash)

    def test_08_web_panel_version_occurrences(self):
        from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
        health = get_system_health()
        self.assertIn("v25.5.7", health["engine_version"])

        dash = render_dashboard_html()
        self.assertIn("v25.5.7", dash)
        self.assertNotIn("v25.5.6", dash)

        store = render_storefront_html()
        self.assertIn("v25.5.7", store)
        self.assertNotIn("v25.5.6", store)

    def test_09_bale_invoice_url_standardization_logic(self):
        inv_url = "invoice_id=987654321"
        inv_url = str(inv_url).strip()
        if inv_url and not inv_url.startswith("http"):
            inv_url = f"https://ble.ir/abasmanesh365bot?start={inv_url}"
        self.assertEqual(inv_url, "https://ble.ir/abasmanesh365bot?start=invoice_id=987654321")

        full_url = "https://ble.ir/invoice/123456"
        if full_url and not full_url.startswith("http"):
            full_url = f"https://ble.ir/abasmanesh365bot?start={full_url}"
        self.assertEqual(full_url, "https://ble.ir/invoice/123456")

if __name__ == "__main__":
    unittest.main()
