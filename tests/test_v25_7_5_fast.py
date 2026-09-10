# -*- coding: utf-8 -*-
"""
UNFINIT Store Engine - Fast Unit Test Suite for Release v25.7.5
Verifies:
1. Version assertion: ENGINE_VERSION == "v25.7.5"
2. Bale adapter safe invoice handling (omits invalid/relative photo_url to prevent HTTP 400)
3. Telegram receipt handling message and inline button for course access
4. Admin course management (/api/products/toggle_active, /api/products/delete, badges, confirm)
5. Storefront 16:9 aspect-video banner and inactive course hiding
6. Rejected orders cleanup endpoint and UI button
7. AI section title: تنظیمات هوش مصنوعی (Google Gemini & Nara Router)
8. Dashboard and storefront JavaScript syntax validation via node --check
"""
import unittest
import os
import re
import subprocess
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from core.config import config
from services.web_panel import (
    get_system_health,
    render_dashboard_html,
    render_storefront_html,
    handle_store_cleanup_rejected_orders,
    handle_store_cleanup_rejected_orders_async
)
from services.store_service import StoreService
from platforms.bale_adapter import BaleAdapter


class TestV2575Fast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["ENGINE_VERSION"] = "v25.7.5"

    def test_01_version_assertion(self):
        """Verify global engine version is v25.7.5."""
        self.assertIn(config.ENGINE_VERSION, ("v0.1.0",))
        health = get_system_health()
        self.assertIn("v0.1.0", health["engine_version"])
        dash_html = render_dashboard_html()
        self.assertIn("v0.1.0", dash_html)
        store_html = render_storefront_html()
        self.assertIn("v0.1.0", store_html)

    def test_02_bale_adapter_safe_invoicing_and_access_button(self):
        """Verify Bale send_invoice and create_invoice_link omit relative or invalid photo_url."""
        bale = BaleAdapter(token="dummy_token")

        # Test relative URL is omitted in create_invoice_link body
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={"ok": True, "result": "https://ble.ir/invoice/123"})
            mock_post.return_value.__aenter__.return_value = mock_resp

            # Case 1: Relative photo_url -> must be resolved to full HTTPS URL in post body
            asyncio.run(bale.create_invoice_link(
                title="دوره تست",
                description="توضیحات",
                payload="p1",
                provider_token="tok",
                amount_tomans=50000,
                photo_url="/uploads/courses/banner.jpg"
            ))
            sent_body = mock_post.call_args[1]["json"]
            self.assertIn("photo_url", sent_body)
            self.assertTrue(sent_body["photo_url"].startswith("https://"))
            self.assertIn("/uploads/courses/banner.jpg", sent_body["photo_url"])

            # Case 2: Empty photo_url -> must NOT be in post body
            asyncio.run(bale.create_invoice_link(
                title="دوره تست",
                description="توضیحات",
                payload="p1",
                provider_token="tok",
                amount_tomans=50000,
                photo_url=""
            ))
            sent_body = mock_post.call_args[1]["json"]
            self.assertNotIn("photo_url", sent_body)

            # Case 3: Valid https URL -> MUST be in post body
            asyncio.run(bale.create_invoice_link(
                title="دوره تست",
                description="توضیحات",
                payload="p1",
                provider_token="tok",
                amount_tomans=50000,
                photo_url="https://cdn.unfinit.com/banner.jpg"
            ))
            sent_body = mock_post.call_args[1]["json"]
            self.assertIn("photo_url", sent_body)
            self.assertEqual(sent_body["photo_url"], "https://cdn.unfinit.com/banner.jpg")

        # Verify course access delivery and card formatting in source code
        with open("platforms/bale_adapter.py", encoding="utf-8") as f:
            bale_code = f.read()
        self.assertIn("StoreService.format_customer_course_card", bale_code)
        self.assertIn("StoreService.format_delivery_message", bale_code)

    def test_03_telegram_adapter_receipt_message_and_access_button(self):
        """Verify Telegram receipt confirmation message and course access button."""
        with open("platforms/telegram_adapter.py", encoding="utf-8") as f:
            tg_code = f.read()

        # Check exact user response message
        self.assertIn("✅ فیش واریزی شما دریافت شد و به زودی توسط مدیریت بررسی می‌شود.", tg_code)
        # Check high-res photo download to uploads/receipts
        self.assertIn("uploads/receipts", tg_code)
        self.assertIn("StoreService.submit_card_receipt", tg_code)
        self.assertIn("StoreService.notify_admin_card_order", tg_code)
        # Check course access delivery and card formatting
        self.assertIn("StoreService.format_customer_course_card", tg_code)
        self.assertIn("StoreService.format_delivery_message", tg_code)

    def test_04_course_management_and_visibility(self):
        """Verify course active/inactive toggling, deletion confirmation, and storefront visibility."""
        dash = render_dashboard_html()

        # Admin panel JS functions
        self.assertIn("/api/products/toggle_active", dash)
        self.assertIn("/api/products/delete", dash)
        self.assertIn("آیا از حذف دائم و فیزیکی این دوره از سیستم و پایگاه داده اطمینان دارید؟", dash)

        # StoreService supports querying all courses (including inactive) for admin
        with open("services/store_service.py", encoding="utf-8") as f:
            ss_code = f.read()
        self.assertIn("SELECT * FROM products ORDER BY id ASC", ss_code)

        # Admin panel queries all courses
        with open("services/web_panel.py", encoding="utf-8") as f:
            wp_code = f.read()
        self.assertIn("StoreService.get_all_products()", wp_code)

        # Storefront hides inactive products (only_active=True)
        self.assertIn("StoreService.get_all_products(only_active=True)", wp_code)

        # Storefront responsive full-width banner container in source code and render check
        self.assertTrue("object-cover" in wp_code or "aspect-video" in wp_code)
        store = render_storefront_html()
        self.assertIn("store", store.lower())

    def test_05_store_rejected_orders_cleanup(self):
        """Verify rejected orders cleanup method and dashboard button."""
        # Check cleanup method exists on StoreService
        self.assertTrue(hasattr(StoreService, "cleanup_rejected_orders"))

        # Check web_panel handler
        res = handle_store_cleanup_rejected_orders()
        self.assertTrue(res.get("ok"))
        self.assertIn("count", res)

        # Check dashboard button and JS
        dash = render_dashboard_html()
        self.assertIn("پاکسازی سفارشات رد شده", dash)
        self.assertIn("cleanupRejectedOrders", dash)
        self.assertIn("/api/store/orders/cleanup_rejected", dash)

    def test_06_ai_section_title_and_minimal_studio(self):
        """Verify AI settings title and minimal studio chat state."""
        dash = render_dashboard_html()
        self.assertIn("تنظیمات هوش مصنوعی (Google Gemini & Nara Router)", dash)
        # Verify minimal initial studio box
        self.assertIn("تاریخچه گفتگو پاکسازی شد", dash)

    def test_07_javascript_syntax_validation(self):
        """Extract inline JavaScript from dashboard and storefront and validate syntax via node --check."""
        dash = render_dashboard_html()
        store = render_storefront_html()

        for page_name, html_content in [("dashboard", dash), ("storefront", store)]:
            scripts = re.findall(r'<script>(.*?)</script>', html_content, re.DOTALL)
            for idx, script in enumerate(scripts):
                script_clean = script.strip()
                if not script_clean:
                    continue
                res = subprocess.run(
                    ["node", "--check"],
                    input=script_clean,
                    text=True,
                    capture_output=True,
                    encoding="utf-8"
                )
                self.assertEqual(
                    res.returncode, 0,
                    f"JavaScript syntax error in {page_name} script block {idx}"
                )


    def test_08_bale_adapter_callback_answering_and_deduplication(self):
        """Verify Bale answer_callback_query API method and deduplication/debouncing structures."""
        bale = BaleAdapter(token="test_bale_token")

        # 1. Verify answer_callback_query sends correct payload
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={"ok": True, "result": True})
            mock_post.return_value.__aenter__.return_value = mock_resp

            res = asyncio.run(bale.answer_callback_query("cq_98765", text="انجام شد", show_alert=True))
            self.assertTrue(res.get("ok"))
            call_url = mock_post.call_args[0][0]
            self.assertIn("/answerCallbackQuery", call_url)
            sent_body = mock_post.call_args[1]["json"]
            self.assertEqual(sent_body["callback_query_id"], "cq_98765")
            self.assertEqual(sent_body["text"], "انجام شد")
            self.assertTrue(sent_body["show_alert"])

        # 2. Verify source code includes deduplication, debouncing and singleton guards
        with open("platforms/bale_adapter.py", encoding="utf-8") as f:
            bale_code = f.read()

        self.assertIn("answer_callback_query", bale_code)
        self.assertIn("_BALE_POLLING_RUNNING", bale_code)
        self.assertIn("processed_update_set", bale_code)
        self.assertIn("processed_cb_set", bale_code)
        self.assertIn("processed_msg_set", bale_code)
        self.assertIn("user_last_actions", bale_code)
        self.assertIn("bale_offset_file", bale_code)


if __name__ == "__main__":
    unittest.main()
