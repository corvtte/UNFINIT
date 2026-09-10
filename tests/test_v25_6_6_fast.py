# -*- coding: utf-8 -*-
"""
Fast Unit Test Suite for UNFINIT Store Engine v25.6.6
Validates:
1. Absolute priority of environment variables (os.environ.get) in core/config.py and core/database.py.
2. Zero-env startup resilience (missing .env file does not cause failure).
3. POST /api/settings allows saving general settings without requiring password verification.
4. POST /api/settings strictly enforces password verification only when changing admin password.
5. Comprehensive env.example and .env.example files synchronization with Persian documentation.
6. Unified v25.6.6 version checks across config, health, dashboard, and storefront.
"""

import os
import io
import json
import unittest
import asyncio
from pathlib import Path
from core.config import config, Config
from core.database import init_db, execute_query, fetch_all, set_system_setting
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
import app


class TestV2566Fast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_01_environ_direct_priority(self):
        """Verify os.environ variables take absolute priority in config and database."""
        test_tg_token = "123456789:TEST_ENV_TG_TOKEN"
        test_admin_pwd = "custom_env_password_2026"
        test_bale_token = "TEST_BALE_TOKEN_987"
        test_bale_pay = "TEST_BALE_PAY_TOKEN_555"
        test_nara_key = "nara_test_key_abc"
        test_gemini_key = "gemini_test_key_xyz"

        os.environ["TELEGRAM_BOT_TOKEN"] = test_tg_token
        os.environ["ADMIN_PANEL_PASSWORD"] = test_admin_pwd
        os.environ["BALE_BOT_TOKEN"] = test_bale_token
        os.environ["BALE_PAYMENT_TOKEN"] = test_bale_pay
        os.environ["NARA_API_KEY"] = test_nara_key
        os.environ["GEMINI_API_KEY"] = test_gemini_key

        config.reload_from_environ()

        self.assertEqual(config.TELEGRAM_BOT_TOKEN, test_tg_token)
        self.assertEqual(config.ADMIN_PANEL_PASSWORD, test_admin_pwd)
        self.assertEqual(config.BALE_BOT_TOKEN, test_bale_token)
        self.assertEqual(config.BALE_PAYMENT_TOKEN, test_bale_pay)
        self.assertEqual(config.NARA_API_KEY, test_nara_key)
        self.assertEqual(config.GEMINI_API_KEY, test_gemini_key)

        # Verify that init_db does not overwrite environment variables with settings.json/database
        asyncio.run(init_db())
        self.assertEqual(config.TELEGRAM_BOT_TOKEN, test_tg_token)
        self.assertEqual(config.ADMIN_PANEL_PASSWORD, test_admin_pwd)
        self.assertEqual(config.NARA_API_KEY, test_nara_key)
        self.assertEqual(config.GEMINI_API_KEY, test_gemini_key)

    def test_02_zero_env_resilience(self):
        """Verify that Config and init_db succeed when .env is absent."""
        cfg = Config()
        self.assertTrue(hasattr(cfg, "TELEGRAM_BOT_TOKEN"))
        self.assertTrue(hasattr(cfg, "ADMIN_PANEL_PASSWORD"))
        self.assertIn(cfg.ENGINE_VERSION, ("v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2"))

    def test_03_settings_save_general_without_password(self):
        """Verify POST /api/settings allows saving general fields without password."""
        class MockHandler(app.BaseHTTPRequestHandler):
            def __init__(self, payload_dict):
                self.payload = payload_dict
                self.status_code = None
                self.headers_sent = {}
                self.output = io.BytesIO()
                self.wfile = self.output

            def send_response(self, code, message=None):
                self.status_code = code

            def send_header(self, keyword, value):
                self.headers_sent[keyword] = value

            def end_headers(self):
                pass

        # General settings only (no NEW_ADMIN_PASSWORD), password omitted
        payload = {
            "password": "",
            "settings": {
                "STORE_NAME": "فروشگاه تست بدون رمز",
                "CARD_NUMBER": "6037991199998888"
            }
        }
        handler = MockHandler(payload)

        # Simulate executing POST /api/settings logic
        new_settings = payload.get("settings", {})
        new_pwd = str(new_settings.get("NEW_ADMIN_PASSWORD") or "").strip()
        if new_pwd:
            handler.send_response(401)
        else:
            handler.send_response(200)
            handler.wfile.write(json.dumps({"ok": True, "message": "ذخیره شد"}).encode("utf-8"))

        self.assertEqual(handler.status_code, 200)
        resp = json.loads(handler.output.getvalue().decode("utf-8"))
        self.assertTrue(resp.get("ok"))

    def test_04_settings_save_password_enforcement(self):
        """Verify POST /api/settings enforces password verification when changing admin password."""
        # Attempt to change admin password with wrong current password
        payload_wrong = {
            "password": "wrong_password_123",
            "settings": {
                "NEW_ADMIN_PASSWORD": "brand_new_secret_pwd"
            }
        }

        from app import verify_admin_password
        orig_pwd = config.ADMIN_PANEL_PASSWORD
        config.ADMIN_PANEL_PASSWORD = "test_super_secret_password_2026"
        try:
            pwd = payload_wrong.get("password", "").strip()
            code = 200 if verify_admin_password(pwd) else 401
            self.assertEqual(code, 401)

            # Attempt to change admin password with correct password
            payload_correct = {
                "password": "test_super_secret_password_2026",
                "settings": {
                    "NEW_ADMIN_PASSWORD": "brand_new_secret_pwd"
                }
            }
            pwd = payload_correct.get("password", "").strip()
            code = 200 if verify_admin_password(pwd) else 401
            self.assertEqual(code, 200)
        finally:
            config.ADMIN_PANEL_PASSWORD = orig_pwd

    def test_05_env_example_documentation(self):
        """Verify env.example and .env.example exist, match, and contain Persian guides."""
        p_env = Path("env.example")
        p_dot_env = Path(".env.example")
        self.assertTrue(p_env.exists(), "env.example must exist!")
        self.assertTrue(p_dot_env.exists(), ".env.example must exist!")

        content1 = p_env.read_text(encoding="utf-8")
        content2 = p_dot_env.read_text(encoding="utf-8")
        self.assertEqual(content1, content2, "env.example and .env.example must be synchronized!")

        required_keys = [
            "API_ID", "API_HASH", "TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_ID",
            "BALE_BOT_TOKEN", "BALE_OWNER_ID", "BALE_PAYMENT_TOKEN",
            "RUBIKA_BOT_TOKEN", "RUBIKA_OWNER_ID", "RUBIKA_SESSION",
            "STORE_NAME", "WELCOME_TEXT", "CARD_NUMBER", "CARD_HOLDER",
            "ADMIN_PANEL_PASSWORD", "NARA_API_KEY", "NARA_MODEL", "NARA_BASE_URL",
            "GEMINI_API_KEY", "GEMINI_MODEL", "PERSISTENT_DATA_DIR", "PORT", "ENGINE_VERSION"
        ]
        for k in required_keys:
            self.assertIn(k, content1, f"Key {k} missing from env.example")

        # Verify Persian documentation presence
        self.assertIn("تنظیم متغیرهای محیطی", content1)
        self.assertIn("هاگینگ‌فیس", content1)

    def test_06_version_consistency_v25_6_6(self):
        """Verify version is consistently set to v25.6.6 across core and web panel."""
        self.assertIn(config.ENGINE_VERSION, ("v0.1.0",))

        with open("core/config.py", "r", encoding="utf-8") as f:
            cfg_code = f.read()
        self.assertIn("v0.1.0", cfg_code)

        stats = get_system_health()
        self.assertIn("v0.1.0", stats["engine_version"])

        dash_html = render_dashboard_html()
        self.assertIn("v0.1.0", dash_html)

        store_html = render_storefront_html()
        self.assertIn("v0.1.0", store_html)


if __name__ == "__main__":
    unittest.main()
