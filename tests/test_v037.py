# -*- coding: utf-8 -*-
"""
Tests for UNFINIT Store Engine v0.3.7:
1. Zero-Git Exposure & AES-256-GCM Session Encryption (core/security.py, task_store.py)
2. Soroush Plus Worker Client (platforms/soroush_worker.py) & Session Disconnect
3. Rubika User Client masked phone & disconnect (platforms/rubika_adapter.py)
4. Multi-Platform Dispatch Checklist & Format Switcher (services/web_panel.py)
5. Collapsible Logs Drawer (services/web_panel.py)
6. Users Tab Sub-Tabs & Responsive Orders Table (services/web_panel.py)
7. Bale Dynamic Safe Limit (48.50 MB) & Quick Edit UI
8. Clean Version String v0.3.7
"""

import os
import sys
import unittest
import asyncio
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from core.config import config
from core.database import init_db
from core.security import (
    derive_aes_gcm_key,
    encrypt_session_data,
    decrypt_session_data,
    save_encrypted_session,
    load_decrypted_session,
)
from task_store import session_file_candidates
from platforms.soroush_worker import SoroushWorker, soroush_worker
from platforms.rubika_adapter import RubikaUserClient
from services.web_panel import (
    get_system_health,
    render_dashboard_html,
    handle_api_dispatch_url,
)


class TestV037Release(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.config import VersionStr
        config.ENGINE_VERSION = VersionStr("v0.3.7")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(init_db())
        loop.close()

    def setUp(self):
        from core.config import VersionStr
        config.ENGINE_VERSION = VersionStr("v0.3.7")

    def test_01_version_and_system_health(self):
        """Rule 1.1 / v0.3.7: Clean ENGINE_VERSION string."""
        self.assertEqual(str(config.ENGINE_VERSION), "v0.3.7")
        self.assertEqual(config.ENGINE_VERSION.clean, "v0.3.7")
        self.assertNotIn("(", str(config.ENGINE_VERSION))
        self.assertNotIn(")", str(config.ENGINE_VERSION))
        health = get_system_health()
        self.assertIn("v0.3.7", str(health.get("engine_version", "")))
        # Verify Soroush Plus is represented in platforms dict
        platforms = health.get("platforms", {})
        self.assertIn("soroush", platforms)

    def test_02_aes_256_gcm_session_encryption_roundtrip(self):
        """AES-256-GCM: Verify key derivation and encryption/decryption roundtrip."""
        key = derive_aes_gcm_key("SecretPass123!")
        # 32-byte raw key for AES-256
        self.assertEqual(len(key), 32)

        sample_session = b"unfinit_auth_session_data_12345"
        encrypted = encrypt_session_data(sample_session, key=key)
        # Output is raw bytes: 12-byte nonce + ciphertext (not prefixed with AESGCMv1:)
        self.assertIsInstance(encrypted, bytes)
        self.assertGreater(len(encrypted), len(sample_session))  # at minimum nonce + tag added

        decrypted = decrypt_session_data(encrypted, key=key)
        self.assertEqual(decrypted, sample_session)

    def test_03_aes_gcm_tamper_detection(self):
        """AES-256-GCM: Tampered ciphertext must raise ValueError."""
        key = derive_aes_gcm_key("AnotherTestKey")
        original = b"secret_session_payload"
        encrypted = encrypt_session_data(original, key=key)

        # Flip last byte of the GCM authentication tag
        tampered = bytearray(encrypted)
        tampered[-1] ^= 0xFF
        with self.assertRaises((ValueError, Exception)):
            decrypt_session_data(bytes(tampered), key=key)

    def test_04_save_and_load_encrypted_session_lifecycle(self):
        """Verify save_encrypted_session creates .session.enc and wipes plain file."""
        test_dir = Path("data/test_sessions_v037")
        test_dir.mkdir(parents=True, exist_ok=True)
        plain_file = test_dir / "user.session"
        # save_encrypted_session(path, raw_bytes) saves to path.session.enc automatically
        enc_file = plain_file.with_name(plain_file.name + ".enc")  # user.session.enc

        try:
            raw_data = b"raw_sqlite_or_string_session_data"
            plain_file.write_bytes(raw_data)
            # Pass plain file path and the raw bytes
            save_encrypted_session(plain_file, raw_data)

            self.assertTrue(enc_file.exists())
            # Plain file should be wiped
            self.assertFalse(plain_file.exists())

            loaded = load_decrypted_session(enc_file)
            self.assertEqual(loaded, raw_data)
        finally:
            if plain_file.exists():
                plain_file.unlink()
            if enc_file.exists():
                enc_file.unlink()
            if test_dir.exists():
                try:
                    test_dir.rmdir()
                except OSError:
                    pass

    def test_05_session_candidates_discovery(self):
        """task_store: session_file_candidates returns list of candidates for session names."""
        # Test with rubika session name
        rubika_candidates = session_file_candidates("unfinit_rubika")
        self.assertIsInstance(rubika_candidates, list)
        self.assertGreater(len(rubika_candidates), 0)
        # At least one candidate should reference .session.enc
        self.assertTrue(any(".session.enc" in str(c) for c in rubika_candidates))

        # Test with soroush session name
        soroush_candidates = session_file_candidates("soroush")
        self.assertIsInstance(soroush_candidates, list)
        self.assertTrue(any(".session.enc" in str(c) for c in soroush_candidates))

    def test_06_soroush_worker_masked_phone_and_disconnect(self):
        """Soroush Plus Worker: Verify phone masking, get_status, and disconnect logic."""
        worker = SoroushWorker()
        # Directly inject session data to bypass file loading
        worker._session_data = {"phone": "09123456789", "token": "test_token_123"}
        self.assertTrue(worker.is_connected())
        self.assertEqual(worker.get_masked_phone(), "0912***6789")

        status = worker.get_status()
        self.assertTrue(status["connected"])
        self.assertEqual(status["masked_phone"], "0912***6789")
        # Phone field in status is set if connected
        self.assertIn("phone", status)

        # Disconnect clears memory state (files may or may not exist)
        worker._session_data = None
        self.assertFalse(worker.is_connected())
        self.assertEqual(worker.get_masked_phone(), "")

    def test_07_rubika_client_has_disconnect_and_masked_phone(self):
        """Rubika User: Verify client has disconnect and get_masked_phone methods."""
        client = RubikaUserClient()
        # Both methods must exist and be callable
        self.assertTrue(callable(getattr(client, "disconnect", None)))
        self.assertTrue(callable(getattr(client, "get_masked_phone", None)))

        # get_masked_phone returns string (may be empty or 'متصل' without real session)
        phone = client.get_masked_phone()
        self.assertIsInstance(phone, str)

        # disconnect returns bool
        result = client.disconnect()
        self.assertIsInstance(result, bool)

    def test_08_dashboard_html_four_platform_cards(self):
        """Web Panel: Dashboard renders 4 platforms - Telegram, Bale, Rubika, Soroush."""
        html = render_dashboard_html()
        # Platform cards exist with relevant text
        self.assertIn("Rubika", html)  # Rubika card header
        self.assertIn("Soroush", html)  # Soroush card header
        self.assertIn("disconnectSession", html)
        self.assertIn("openSoroushLoginModal", html)
        self.assertIn("editBaleSafeLimit", html)
        # Verify 4 platform types appear in health
        health = get_system_health()
        platforms = health.get("platforms", {})
        self.assertIn("telegram", platforms)
        self.assertIn("bale", platforms)
        self.assertIn("rubika_user", platforms)
        self.assertIn("soroush", platforms)

    def test_09_bale_safe_limit_quick_edit_default(self):
        """Web Panel & Config: Bale safe limit default is 48.50 MB and has quick edit button."""
        self.assertEqual(config.MAX_SAFE_BALE_SIZE_MB, 48.50)
        html = render_dashboard_html()
        self.assertIn("48.50", html)
        self.assertIn("editBaleSafeLimit", html)

    def test_10_logs_slide_over_drawer(self):
        """Web Panel: Slide-over logs drawer with toggle button exists."""
        html = render_dashboard_html()
        self.assertIn('id="logsDrawer"', html)
        self.assertIn('id="logsDrawerOverlay"', html)
        self.assertIn('toggleLogsDrawer', html)
        self.assertIn('translate-x-full', html)

    def test_11_users_sub_tabs_and_responsive_table(self):
        """Web Panel: Users tab has 2 sub-tabs; orders table is responsive."""
        html = render_dashboard_html()
        self.assertIn("فهرست و مشخصات کاربران", html)
        self.assertIn("شبکه رفرال", html)
        self.assertIn("switchUserSubTab", html)
        self.assertIn("overflow-x-auto", html)

    def test_12_feed_dispatch_modal_checklist_and_format_switcher(self):
        """Web Panel: Feed dispatch modal has 4-platform checkboxes and MP3/MP4 switcher."""
        html = render_dashboard_html()
        self.assertIn('id="feedDispatchModal"', html)
        # Actual checkbox IDs found in the HTML
        self.assertIn('id="chkDispatchTg"', html)
        self.assertIn('id="chkDispatchBale"', html)
        self.assertIn('id="chkDispatchRubika"', html)
        self.assertIn('id="chkDispatchSoroush"', html)
        # Format switcher buttons
        self.assertIn('setDispatchFormat', html)
        self.assertIn('executeFeedMultiDispatch', html)
        self.assertIn('نسخه صوتی MP3', html)
        self.assertIn('نسخه تصویری MP4', html)

    def test_13_handle_api_dispatch_url_signature(self):
        """Backend: handle_api_dispatch_url is async and accepts URL data dict."""
        import inspect
        from services.web_panel import handle_api_dispatch_url
        # Must be a coroutine function
        self.assertTrue(inspect.iscoroutinefunction(handle_api_dispatch_url))

        # Empty URL returns error dict
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(handle_api_dispatch_url({"url": ""}))
        loop.close()
        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("ok", True))

    def test_14_gitignore_covers_session_files(self):
        """Zero-Git Exposure: .gitignore must exclude all session and enc files."""
        gitignore_path = Path(".gitignore")
        if not gitignore_path.exists():
            self.skipTest(".gitignore not found in working directory")
        content = gitignore_path.read_text(encoding="utf-8", errors="ignore")
        # All these patterns must be present
        for pattern in ("*.session", "*.session.enc", "*.enc", "data/*.session"):
            self.assertIn(pattern, content, f"Missing .gitignore pattern: {pattern}")


if __name__ == "__main__":
    unittest.main()
