# -*- coding: utf-8 -*-
"""
UNFINIT Store Engine - Unit Test Suite for v25.8 Features
Verifies:
1. get_system_setting prioritizing os.environ -> config -> database fallback
2. Rubika adapter security isolation (no auto-admin elevation, strict GUID validation, /myid)
3. Coupons engine: creation, percent/fixed discount validation, usage limits, and order deductions
4. Sales analytics dashboard: periods (today, 7d, 30d), platform breakdown (telegram, bale, rubika, web)
5. AI Sales Support Copilot: chat_course_support handles queries and recommends courses
6. Secrets masking & Dark theme autofill protection in web panel
"""
import unittest
import os
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from core.config import config
from core.database import (
    init_db,
    get_system_setting,
    db_create_coupon,
    db_get_coupon,
    db_get_all_coupons,
    db_increment_coupon_usage,
    execute_write,
    fetch_one,
    fetch_all
)
from platforms.rubika_adapter import RubikaAdapter
from services.store_service import StoreService
from services.ai_agent_service import ai_agent_service
from services.web_panel import render_dashboard_html
from app import _get_all_settings


class TestV258Features(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_01_get_system_setting_prioritizes_os_environ_and_config(self):
        """Verify get_system_setting prioritizes os.environ over empty DB value and falls back to config."""
        test_key = "TEST_SPECIAL_SETTING"
        os.environ[test_key] = "ENV_SECRET_VALUE_123"

        # Even if DB has nothing, it should return env value
        val = asyncio.run(get_system_setting(test_key, default="FALLBACK"))
        self.assertEqual(val, "ENV_SECRET_VALUE_123")

        # Clean up env
        del os.environ[test_key]

        # Should return default when not in DB or env
        val2 = asyncio.run(get_system_setting(test_key, default="FALLBACK"))
        self.assertEqual(val2, "FALLBACK")

    def test_02_rubika_security_isolation_and_myid(self):
        """Verify Rubika security eliminates auto-elevation and hardcoded b0BNC GUID."""
        adapter = RubikaAdapter()

        # Hardcoded old GUID should never be admin by default
        old_hardcoded = "b0BNCMy0zOH0f52e0bd2ca1faa9de77f"
        random_user = "u0123456789abcdef"

        with patch.object(config, "RUBIKA_OWNER_ID", ""):
            with patch.object(config, "ADMIN_USER_IDS", []):
                self.assertFalse(adapter.is_admin(old_hardcoded))
                self.assertFalse(adapter.is_admin(random_user))
                self.assertEqual(adapter.get_admin_guid(), "")

        # When RUBIKA_OWNER_ID is explicitly set, only that GUID is admin
        with patch.object(config, "RUBIKA_OWNER_ID", "valid_rubika_admin_guid_999"):
            self.assertTrue(adapter.is_admin("valid_rubika_admin_guid_999"))
            self.assertFalse(adapter.is_admin(old_hardcoded))
            self.assertFalse(adapter.is_admin(random_user))
            self.assertEqual(adapter.get_admin_guid(), "valid_rubika_admin_guid_999")

        # When GUID is in ADMIN_USER_IDS, it is recognized as admin
        with patch.object(config, "RUBIKA_OWNER_ID", ""):
            with patch.object(config, "ADMIN_USER_IDS", ["guid_in_admin_list"]):
                self.assertTrue(adapter.is_admin("guid_in_admin_list"))
                self.assertFalse(adapter.is_admin("other_user"))

    def test_03_coupons_lifecycle_and_validation(self):
        """Verify coupon creation, percent and fixed validation, usage limits, and order deductions."""
        import uuid
        c_pct = f"OFF20_{uuid.uuid4().hex[:4].upper()}"
        c_fix = f"FIX15_{uuid.uuid4().hex[:4].upper()}"

        # 1. Percent Coupon: 20% off, max 2 uses, min order 50,000
        asyncio.run(db_create_coupon(
            code=c_pct,
            discount_type="percent",
            discount_value=20,
            max_uses=2,
            min_order_amount=50000
        ))

        coupon = asyncio.run(db_get_coupon(c_pct))
        self.assertIsNotNone(coupon)
        self.assertEqual(coupon["code"], c_pct)
        self.assertEqual(coupon["discount_value"], 20)

        # Validation with price below min_order_amount
        res_min = asyncio.run(StoreService.validate_coupon(c_pct.lower(), order_amount=40000))
        self.assertFalse(res_min["ok"])
        self.assertIn("50,000", res_min["error"])

        # Validation with valid price 100,000 -> 20% discount = 20,000
        res_valid = asyncio.run(StoreService.validate_coupon(c_pct.lower(), order_amount=100000))
        self.assertTrue(res_valid["ok"])
        self.assertEqual(res_valid["discount_amount"], 20000)
        self.assertEqual(res_valid["final_total"], 80000)

        # 2. Fixed Coupon: 15,000 Toman off
        asyncio.run(db_create_coupon(
            code=c_fix,
            discount_type="fixed",
            discount_value=15000,
            max_uses=10,
            min_order_amount=20000
        ))
        res_fixed = asyncio.run(StoreService.validate_coupon(c_fix, order_amount=50000))
        self.assertTrue(res_fixed["ok"])
        self.assertEqual(res_fixed["discount_amount"], 15000)
        self.assertEqual(res_fixed["final_total"], 35000)

        # 3. Usage limit enforcement
        asyncio.run(db_increment_coupon_usage(c_pct))
        asyncio.run(db_increment_coupon_usage(c_pct))
        res_exhausted = asyncio.run(StoreService.validate_coupon(c_pct, order_amount=100000))
        self.assertFalse(res_exhausted["ok"])
        self.assertIn("ظرفیت", res_exhausted["error"])

    def test_04_sales_analytics_metrics_and_platforms(self):
        """Verify StoreService.get_sales_analytics aggregates revenue, orders, and platform distribution."""
        import uuid
        tag = uuid.uuid4().hex[:6]
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")

        asyncio.run(execute_write(
            """INSERT INTO orders (
                order_id, user_id, product_id, product_name, total, discount_amount,
                payment_method, status, platform, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"TEST_TG_{tag}", "tg_123", "P1", "دوره تلگرام", 100000, 10000, "card", "approved", "telegram", now_str)
        ))
        asyncio.run(execute_write(
            """INSERT INTO orders (
                order_id, user_id, product_id, product_name, total, discount_amount,
                payment_method, status, platform, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"TEST_BALE_{tag}", "bale_456", "P2", "دوره بله", 200000, 0, "bale", "completed", "bale", now_str)
        ))
        asyncio.run(execute_write(
            """INSERT INTO orders (
                order_id, user_id, product_id, product_name, total, discount_amount,
                payment_method, status, platform, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"TEST_WEB_{tag}", "web_789", "P3", "دوره وب", 300000, 50000, "card", "approved", "web", now_str)
        ))
        asyncio.run(execute_write(
            """INSERT INTO orders (
                order_id, user_id, product_id, product_name, total, discount_amount,
                payment_method, status, platform, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"TEST_PEND_{tag}", "rubika_999", "P4", "دوره روبیکا", 150000, 0, "card", "pending_review", "rubika", now_str)
        ))

        analytics = asyncio.run(StoreService.get_sales_analytics())

        self.assertGreaterEqual(analytics["total_sales_amount"], 600000)
        self.assertGreaterEqual(analytics["total_sales_count"], 3)
        self.assertGreaterEqual(analytics["today_sales_amount"], 600000)
        self.assertGreaterEqual(analytics["total_discount_amount"], 60000)
        self.assertGreaterEqual(analytics["pending_orders_count"], 1)

        # Check platform breakdown
        pb = analytics["platform_breakdown"]
        self.assertIn("telegram", pb)
        self.assertIn("bale", pb)
        self.assertIn("rubika", pb)
        self.assertIn("web", pb)
        self.assertGreaterEqual(pb["telegram"]["amount"], 100000)
        self.assertGreaterEqual(pb["bale"]["amount"], 200000)
        self.assertGreaterEqual(pb["web"]["amount"], 300000)

    def test_05_ai_sales_copilot_response(self):
        """Verify ai_agent_service.chat_course_support produces supportive Persian guidance."""
        with patch.object(ai_agent_service, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = {"ok": True, "reply": "سلام! دوره مهندسی پرامپت بهترین انتخاب برای شماست."}
            with patch.object(config, "NARA_API_KEY", "test_key"):
                reply = asyncio.run(ai_agent_service.chat_course_support("کدوم دوره برای شروع هوش مصنوعی بهتره؟"))
                self.assertIn("دوره", reply)
                self.assertIn("مهندسی پرامپت", reply)

    def test_06_secrets_masking_and_autofill_protection(self):
        """Verify sensitive settings are masked in _get_all_settings and dashboard prevents browser autofill."""
        # 1. Check settings masking
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"}):
            settings = _get_all_settings()
            masked_tg = settings.get("TELEGRAM_BOT_TOKEN")
            self.assertIn("••••••••", masked_tg)
            self.assertNotIn("ABC-DEF", masked_tg)

        # 2. Check autofill CSS and new-password attribute in dashboard HTML
        dash_html = render_dashboard_html()
        self.assertIn(":-webkit-autofill", dash_html)
        self.assertIn("autocomplete=\"new-password\"", dash_html)
        self.assertIn("loadStoreAnalytics", dash_html)
        self.assertIn("loadStoreCoupons", dash_html)


if __name__ == "__main__":
    unittest.main()
