import unittest
import asyncio
import os
os.environ["TESTING"] = "true"
import json
from pathlib import Path

from core.config import config
from core.database import init_db, get_db_connection
from services.store_service import StoreService, ProductItem, OrderItem
from services.web_panel import (
    render_storefront_html,
    render_dashboard_html,
    handle_store_buy_bale,
    handle_store_buy_card,
    handle_store_get_orders,
    handle_store_approve_order,
    handle_store_get_order_status
)
from platforms.bale_adapter import BaleAdapter

class TestV255StorefrontAndPayments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_01_render_storefront_html(self):
        html = render_storefront_html()
        self.assertIsInstance(html, str)
        self.assertIn("UNFINIT STORE", html)
        self.assertIn("v0.1.0", html)
        self.assertIn("baleBuyModal", html)
        self.assertIn("cardBuyModal", html)
        self.assertIn("trackOrderModal", html)
        self.assertIn("handleBalePaymentSubmit", html)
        self.assertIn("handleCardPaymentSubmit", html)
        self.assertIn("handleTrackSubmit", html)

    def test_02_render_dashboard_courses_and_orders(self):
        html = render_dashboard_html()
        self.assertIsInstance(html, str)
        self.assertIn("/store", html)
        self.assertIn("مشاهده ویترین فروشگاه (/store)", html)
        self.assertIn("ordersCard", html)
        self.assertIn("storeOrdersTableBody", html)
        self.assertIn("loadStoreOrders", html)
        self.assertIn("approveStoreOrder", html)

    def test_03_bale_adapter_create_invoice_link_structure(self):
        adapter = BaleAdapter(token="123456:fake_token")
        self.assertTrue(hasattr(adapter, "create_invoice_link"))
        self.assertTrue(callable(adapter.create_invoice_link))

    def test_04_create_and_query_web_orders(self):
        async def _test():
            # Add a test course
            prod = await StoreService.add_product(
                name="دوره تست پرداخت",
                price=50000,
                description="توضیحات دوره آزمایشی",
                download_link="https://example.com/download/test.zip",
                allow_card=True,
                allow_bale=True
            )
            self.assertIsNotNone(prod)

            # Test Card-to-Card order creation
            card_order = await StoreService.create_web_order(
                course_id=prod.product_id,
                customer_name="کاربر تست کارت",
                phone="09120000001",
                payment_method="card_to_card",
                receipt_info="فیش شماره 987654"
            )
            self.assertIsNotNone(card_order)
            self.assertTrue(card_order.order_id.startswith("ORD_"))
            self.assertEqual(card_order.payment_method, "card_to_card")
            self.assertEqual(card_order.receipt_text, "فیش شماره 987654")
            self.assertEqual(card_order.status, "pending_review")

            # Check customer order status before approval
            status_before = await StoreService.get_order_status_for_customer(card_order.order_id)
            self.assertIsNotNone(status_before)
            self.assertEqual(status_before["status"], "pending_review")
            self.assertEqual(status_before["download_link"], "")

            # Approve order
            app_res = await StoreService.approve_order(card_order.order_id)
            self.assertIsNotNone(app_res)
            self.assertEqual(app_res["status"], "approved")

            # Check customer order status after approval
            status_after = await StoreService.get_order_status_for_customer(card_order.order_id)
            self.assertIsNotNone(status_after)
            self.assertEqual(status_after["status"], "approved")
            self.assertEqual(status_after["download_link"], "https://example.com/download/test.zip")

            # Cleanup
            await StoreService.delete_product(prod.product_id)

        asyncio.run(_test())

    def test_05_store_handlers_flow(self):
        # 1. Add course for handlers test
        async def _add():
            return await StoreService.add_product(
                name="دوره وب‌پنل",
                price=100000,
                description="دوره تستی هندلرها",
                download_link="https://example.com/dl/course.zip",
                allow_card=True,
                allow_bale=True
            )
        prod = asyncio.run(_add())

        # 2. Buy Card Handler
        card_res = handle_store_buy_card({
            "course_id": prod.product_id,
            "customer_name": "خریدار تستی",
            "phone": "09121111111",
            "receipt_info": "واریز شده با شماره پیگیری 12345"
        })
        self.assertTrue(card_res.get("ok"))
        self.assertIn("order_id", card_res)
        order_id = card_res["order_id"]

        # 3. Get Orders Handler
        orders_res = handle_store_get_orders()
        self.assertTrue(orders_res.get("ok"))
        orders = orders_res.get("orders", [])
        self.assertTrue(any(o["order_id"] == order_id for o in orders))

        # 4. Check Status (Pending)
        st_res = handle_store_get_order_status(order_id)
        self.assertTrue(st_res.get("ok"))
        self.assertEqual(st_res["orders"][0]["status"], "pending_review")
        self.assertEqual(st_res["orders"][0]["download_link"], "")

        # 5. Approve Order
        app_res = handle_store_approve_order(order_id)
        self.assertTrue(app_res.get("ok"))

        # 6. Check Status (Approved & Download Link Available)
        st_res_after = handle_store_get_order_status(order_id)
        self.assertTrue(st_res_after.get("ok"))
        self.assertEqual(st_res_after["orders"][0]["status"], "approved")
        self.assertEqual(st_res_after["orders"][0]["download_link"], "https://example.com/dl/course.zip")

        # 7. Query by Phone
        st_phone_res = handle_store_get_order_status("09121111111")
        self.assertTrue(st_phone_res.get("ok"))
        self.assertTrue(len(st_phone_res["orders"]) >= 1)

        # Cleanup
        asyncio.run(StoreService.delete_product(prod.product_id))

    def test_06_free_course_auto_approval(self):
        async def _test():
            free_prod = await StoreService.add_product(
                name="دوره رایگان هدیه",
                price=0,
                description="دوره کاملا رایگان",
                download_link="https://example.com/free.zip",
                allow_card=True,
                allow_bale=True
            )
            return free_prod

        free_prod = asyncio.run(_test())

        # When buy_bale is called on free course, it should auto-approve immediately
        res = handle_store_buy_bale({
            "course_id": free_prod.product_id,
            "customer_name": "کاربر رایگان",
            "phone": "09999999999"
        })
        self.assertTrue(res.get("ok"))
        self.assertTrue(res.get("is_free"))
        self.assertEqual(res.get("download_link"), "https://example.com/free.zip")

        # Cleanup
        asyncio.run(StoreService.delete_product(free_prod.product_id))

    def test_07_login_gate_no_form_ajax(self):
        html = render_dashboard_html()
        self.assertNotIn('<form id="mainLoginForm"', html)
        self.assertIn('id="mainLoginContainer"', html)
        self.assertIn('id="adminPasswordInput"', html)
        self.assertIn('id="loginBtn"', html)
        self.assertIn('handleLoginSubmit', html)

    def test_08_storefront_dark_mode_and_buttons(self):
        html = render_storefront_html()
        self.assertIn('#0b1120', html)
        self.assertIn('#1e293b', html)
        self.assertIn('#f8fafc', html)
        self.assertIn('#334155', html)
        self.assertIn('data-id=', html)
        self.assertIn('baleCopyInvoiceBtn', html)
        self.assertIn('copyBaleInvoiceLink', html)

    def test_09_purge_windows_sessions_in_init_db(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO media_sessions (drop_id, data_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    ("win_ghost_test", '{"filepath": "C:\\\\Users\\\\Sajjad\\\\Downloads\\\\audio.mp3"}', "2026-09-04", "2026-09-04"))
        conn.commit()
        conn.close()

        # Run init_db which should purge this session
        asyncio.run(init_db())

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT drop_id FROM media_sessions WHERE drop_id = 'win_ghost_test'")
        row = cur.fetchone()
        conn.close()
        self.assertIsNone(row, "Ghost Windows session was not purged by init_db")

    def test_10_canonical_courses_integrity(self):
        with open(config.COURSES_JSON_FILE, "r", encoding="utf-8") as f:
            courses = json.load(f)
        pids = [c["product_id"] for c in courses]
        self.assertIn("prod_01", pids)
        self.assertIn("prod_02", pids)
        self.assertIn("prod_03", pids)
        self.assertEqual(len(pids), 3)
        for pid in pids:
            self.assertIn(pid, ["prod_01", "prod_02", "prod_03"])

    @classmethod
    def tearDownClass(cls):
        # Cleanup temporary products added during tests
        conn = get_db_connection()
        cur = conn.cursor()
        canonical = ('prod_01', 'prod_02', 'prod_03')
        cur.execute("DELETE FROM products WHERE product_id NOT IN (?, ?, ?)", canonical)
        conn.commit()
        conn.close()
        asyncio.run(StoreService.backup_products_to_disk())

if __name__ == "__main__":
    unittest.main()
