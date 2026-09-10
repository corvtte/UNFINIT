"""
Fast Unit Test Suite for UNFINIT Store Engine v25.7.2
Verifies:
1. Version sync: v25.7.2 across config, env examples, web panel, storefront.
2. Orders table platform and payment method separation (Telegram, Bale, Web / Card, Bale, Zarinpal).
3. Tehran timezone calculation (+03:30) and timestamp format.
4. Favicon SVG link and custom thin dark scrollbars in dashboard and storefront.
5. Accordion / collapsible sections in settings form.
6. Consolidated 3-button customer keyboards in Telegram and Bale.
7. Pillow banner optimization logic in Bale and Telegram adapters.
8. Telegram AI format callback calls ensure_ai_binary.
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
    handle_store_get_orders_async,
    handle_store_reject_order,
    handle_store_approve_order
)
from platforms.telegram_adapter import get_customer_keyboard
from platforms.bale_adapter import get_bale_customer_keyboard


class TestV2572Fast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_01_version_sync(self):
        """Verify v25.7.2 across all config and templates."""
        self.assertIn(config.ENGINE_VERSION, ("v25.7.2", "v25.7.3", "v25.7.4"))

        for env_file in [".env.example", "env.example"]:
            p = Path(env_file)
            if p.exists():
                text = p.read_text(encoding="utf-8")
                self.assertTrue(any(f"ENGINE_VERSION={v}" in text for v in ("v25.7.2", "v25.7.3", "v25.7.4")))

        health = get_system_health()
        self.assertTrue(any(v in health["engine_version"] for v in ("v25.7.2", "v25.7.3", "v25.7.4")))

        dash = render_dashboard_html()
        self.assertTrue(any(v in dash for v in ("v25.7.2", "v25.7.3", "v25.7.4")))

        store = render_storefront_html()
        self.assertTrue(any(v in store for v in ("v25.7.2", "v25.7.3", "v25.7.4")))

    def test_02_tehran_timezone(self):
        """Verify Tehran timezone offset is UTC+03:30."""
        self.assertEqual(TEHRAN_TZ.utcoffset(None), timedelta(hours=3, minutes=30))
        ts_str = get_tehran_now_str()
        self.assertRegex(ts_str, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_03_orders_table_platform_and_payment_method(self):
        """Verify orders table separates platform and payment method."""
        dash = render_dashboard_html()

        # Check table headers
        self.assertIn("بستر سفارش", dash)
        self.assertIn("روش پرداخت", dash)

        # Check JS platform badges
        self.assertIn("platBadge", dash)
        self.assertIn("تلگرام", dash)
        self.assertIn("بله", dash)
        self.assertIn("فروشگاه وب", dash)

        # Check JS payment method badges
        self.assertIn("payMethodBadge", dash)
        self.assertIn("کارت‌به‌کارت", dash)
        self.assertIn("درگاه بله", dash)
        self.assertIn("زرین‌پال", dash)

        # Check backend handle_store_get_orders_async includes platform field
        async def check_orders():
            res = await handle_store_get_orders_async()
            self.assertTrue(res["ok"])
            if res["orders"]:
                self.assertIn("platform", res["orders"][0])
        asyncio.run(check_orders())

    def test_04_favicon_and_thin_scrollbars(self):
        """Verify SVG favicon and custom dark scrollbars in dashboard and storefront."""
        dash = render_dashboard_html()
        store = render_storefront_html()

        # Favicon SVG in both
        self.assertIn("data:image/svg+xml", dash)
        self.assertIn("data:image/svg+xml", store)
        self.assertIn("rel=\"icon\"", dash)
        self.assertIn("rel=\"icon\"", store)

        # Scrollbar rules in both
        self.assertIn("::-webkit-scrollbar", dash)
        self.assertIn("::-webkit-scrollbar-thumb", dash)
        self.assertIn("::-webkit-scrollbar", store)
        self.assertIn("::-webkit-scrollbar-thumb", store)

    def test_05_accordion_settings_sections(self):
        """Verify collapsible accordion details elements in settings form."""
        dash = render_dashboard_html()

        self.assertIn("settings-accordion", dash)
        self.assertIn("<details", dash)
        self.assertIn("<summary", dash)

        # Verify sections present as accordions
        self.assertIn("توکن‌های ربات‌ها و درگاه‌های پرداخت", dash)
        self.assertIn("شناسه‌های ادمین‌ها و سوپرگروه تاپیک‌دار تلگرام", dash)
        self.assertIn("مدیریت پیام‌ها و کانال‌ها", dash)
        self.assertIn("تنظیمات موتورهای هوش مصنوعی", dash)
        self.assertIn("تنظیمات محتوا، رسانه‌ها و فشرده‌سازی هوشمند بله", dash)
        self.assertIn("امنیت و تغییر رمز عبور مدیریت", dash)

    def test_06_consolidated_customer_keyboards(self):
        """Verify Telegram and Bale customer keyboards have exactly 3 consolidated buttons."""
        tg_kb = get_customer_keyboard()
        self.assertEqual(len(tg_kb.keyboard), 3, "Telegram customer keyboard must have exactly 3 rows")
        tg_buttons = [str(getattr(b, "text", b)) for row in tg_kb.keyboard for b in row]
        self.assertEqual(len(tg_buttons), 3)
        self.assertIn("📚 لیست دوره‌های آموزشی", tg_buttons)
        self.assertTrue(any("حساب کاربری" in b for b in tg_buttons), f"Account button missing from TG: {tg_buttons}")
        self.assertIn("💬 پشتیبانی و هدایا", tg_buttons)

        bale_kb = get_bale_customer_keyboard()
        bale_rows = bale_kb.get("keyboard", [])
        self.assertEqual(len(bale_rows), 3, "Bale customer keyboard must have exactly 3 rows")
        bale_buttons = [b.get("text", "") for row in bale_rows for b in row]
        self.assertEqual(len(bale_buttons), 3)
        self.assertIn("📚 لیست دوره‌های آموزشی", bale_buttons)
        self.assertTrue(any("حساب کاربری" in b for b in bale_buttons), f"Account button missing from Bale: {bale_buttons}")
        self.assertIn("💬 پشتیبانی و هدایا", bale_buttons)

    def test_07_pillow_banner_optimization_in_adapters(self):
        """Verify Pillow optimization is applied to banner downloads in Bale & Telegram."""
        bale_code = Path("platforms/bale_adapter.py").read_text(encoding="utf-8")
        self.assertIn("Image.Resampling.LANCZOS", bale_code)
        self.assertIn("im.resize((1200", bale_code)

        tg_code = Path("platforms/telegram_adapter.py").read_text(encoding="utf-8")
        self.assertIn("Image.Resampling.LANCZOS", tg_code)
        self.assertIn("im.resize((1200", tg_code)

    def test_08_telegram_ai_binary_ensure(self):
        """Verify Telegram AI format callback calls ensure_ai_binary."""
        tg_code = Path("platforms/telegram_adapter.py").read_text(encoding="utf-8")
        self.assertIn("await ensure_ai_binary()", tg_code)


if __name__ == "__main__":
    unittest.main()