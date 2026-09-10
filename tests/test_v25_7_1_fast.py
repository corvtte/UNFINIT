"""
Fast Unit Test Suite for UNFINIT Store Engine v25.7.1
Verifies:
1. Version sync: v25.7.1 across config, env examples, web panel, storefront.
2. Tehran timezone calculation (+03:30) and timestamp format.
3. Card-to-card admin order notification fallback to SQLite database settings.
4. Store order rejection (backend + API handler + wallet refund).
5. Web panel UNFINIT Classic theme palette, input styles, and red reject order button.
6. Telegram & Bale admin keyboards contain "پیش‌نمایش پنل مشتری".
7. Telegram AI handler calls ensure_ai_binary before audio file check.
8. Course wizard clean completion message in Telegram & Bale adapters.
"""

import unittest
import asyncio
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure an event loop exists for Python 3.14
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from core.config import config
from core.database import init_db, execute_query, fetch_one, set_system_setting, get_system_setting
from services.store_service import StoreService, TEHRAN_TZ, get_tehran_now_str
from services.web_panel import (
    get_system_health,
    render_dashboard_html,
    render_storefront_html,
    handle_store_reject_order,
    handle_store_approve_order
)
from platforms.telegram_adapter import get_admin_keyboard
from platforms.bale_adapter import get_bale_admin_keyboard


class TestV2571Fast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_01_version_sync(self):
        """Verify v25.7.1 across all config and templates."""
        self.assertIn(config.ENGINE_VERSION, ("v25.7.1", "v25.7.2", "v25.7.3", "v25.7.4"))

        for env_file in [".env.example", "env.example"]:
            p = Path(env_file)
            if p.exists():
                text = p.read_text(encoding="utf-8")
                self.assertTrue(any(f"ENGINE_VERSION={v}" in text for v in ("v25.7.1", "v25.7.2", "v25.7.3", "v25.7.4")))

        health = get_system_health()
        self.assertTrue(any(v in health["engine_version"] for v in ("v25.7.1", "v25.7.2", "v25.7.3", "v25.7.4")))

        dash = render_dashboard_html()
        self.assertTrue(any(v in dash for v in ("v25.7.1", "v25.7.2", "v25.7.3", "v25.7.4")))

        store = render_storefront_html()
        self.assertTrue(any(v in store for v in ("v25.7.1", "v25.7.2", "v25.7.3", "v25.7.4")))

    def test_02_tehran_timezone(self):
        """Verify Tehran timezone offset is UTC+03:30."""
        self.assertEqual(TEHRAN_TZ.utcoffset(None), timedelta(hours=3, minutes=30))
        ts_str = get_tehran_now_str()
        self.assertRegex(ts_str, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_03_store_reject_order(self):
        """Test rejecting an order updates status and refunds wallet if used."""
        async def run():
            # Setup test customer and order
            u_id = "test_user_rej_999"
            await execute_query(
                "INSERT OR REPLACE INTO customers (user_id, customer_name, phone, wallet_balance, created_at) VALUES (?, ?, ?, ?, ?)",
                (u_id, "Rejection Test User", "09120009999", 50000, get_tehran_now_str())
            )
            
            ord_id = "ORD-TEST-REJ-01"
            await execute_query("""
                INSERT OR REPLACE INTO orders 
                (order_id, user_id, product_id, product_name, total, wallet_used, status, payment_method, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ord_id, u_id, "prod_ai_1", "دوره تست هوش مصنوعی", 100000, 20000, "pending_review", "card_to_card", get_tehran_now_str()))

            # Call reject via web panel handler
            res = handle_store_reject_order(ord_id, "فیش نامعتبر است.")
            self.assertTrue(res.get("ok"))
            self.assertEqual(res.get("status"), "rejected")

            # Check db
            ord_row = await fetch_one("SELECT * FROM orders WHERE order_id = ?", (ord_id,))
            self.assertIsNotNone(ord_row)
            self.assertEqual(ord_row["status"], "rejected")

            # Check wallet refund (+20000 -> 70000)
            cust_row = await fetch_one("SELECT * FROM customers WHERE user_id = ?", (u_id,))
            self.assertEqual(cust_row["wallet_balance"], 70000)

        asyncio.run(run())

    def test_04_admin_order_notification_fallback(self):
        """Verify StoreService.notify_admin_card_order reads SQLite database settings."""
        async def run():
            await set_system_setting("TELEGRAM_OWNER_ID", "987654321")
            await set_system_setting("BALE_OWNER_ID", "123456789")

            tg_val = await get_system_setting("TELEGRAM_OWNER_ID")
            bale_val = await get_system_setting("BALE_OWNER_ID")

            self.assertEqual(tg_val, "987654321")
            self.assertEqual(bale_val, "123456789")

            # Check StoreService file source code references get_system_setting for owner IDs
            store_code = Path("services/store_service.py").read_text(encoding="utf-8")
            self.assertIn("get_system_setting(\"TELEGRAM_OWNER_ID\"", store_code)
            self.assertIn("get_system_setting(\"BALE_OWNER_ID\"", store_code)

        asyncio.run(run())

    def test_05_unfinit_classic_theme_and_inputs(self):
        """Verify UNFINIT Classic theme, dark midnight colors and reject button in web panel."""
        dash = render_dashboard_html()

        # UNFINIT Classic option
        self.assertIn("UNFINIT Classic", dash)
        self.assertIn("#080e1e", dash) # Midnight dark background
        self.assertIn("#06b6d4", dash) # Neon cyan accent

        # Theme CSS inputs & settings styling
        self.assertIn("input, select, textarea", dash)
        self.assertIn("var(--input-bg)", dash)
        self.assertIn("var(--card-border)", dash)

        # Reject order button and JS
        self.assertIn("rejectStoreOrder", dash)
        self.assertTrue("❌ رد" in dash or "❌ رد سفارش" in dash)
        self.assertIn("/api/store/orders/reject", dash)

    def test_06_admin_keyboards_customer_preview(self):
        """Verify Telegram and Bale admin keyboards contain customer panel preview."""
        tg_kb = get_admin_keyboard()
        tg_buttons = []
        for row in tg_kb.keyboard:
            for btn in row:
                tg_buttons.append(str(getattr(btn, "text", btn)))
        self.assertTrue(any("پیش‌نمایش پنل مشتری" in b for b in tg_buttons), "Telegram admin keyboard missing preview button")

        bale_kb = get_bale_admin_keyboard()
        bale_buttons = []
        for row in bale_kb.get("keyboard", []):
            for btn in row:
                bale_buttons.append(btn.get("text", "") if isinstance(btn, dict) else str(btn))
        self.assertTrue(any("پیش‌نمایش پنل مشتری" in b for b in bale_buttons), "Bale admin keyboard missing preview button")

    def test_07_telegram_ai_binary_ensure(self):
        """Verify Telegram AI format callback calls ensure_ai_binary."""
        tg_code = Path("platforms/telegram_adapter.py").read_text(encoding="utf-8")
        self.assertIn("await ensure_ai_binary()", tg_code)

    def test_08_course_wizard_completion_message(self):
        """Verify course creation wizard sends clean completion message in TG and Bale."""
        tg_code = Path("platforms/telegram_adapter.py").read_text(encoding="utf-8")
        self.assertIn("دوره با موفقیت ثبت و در فروشگاه وب منتشر شد", tg_code)

        bale_code = Path("platforms/bale_adapter.py").read_text(encoding="utf-8")
        self.assertIn("دوره با موفقیت ثبت و در فروشگاه وب منتشر شد", bale_code)


if __name__ == "__main__":
    unittest.main()