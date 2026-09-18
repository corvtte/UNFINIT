# -*- coding: utf-8 -*-
"""
Tests for UNFINIT Store Engine v0.3.8:
1. Fix scoping bug for set_system_setting in app.py / web_panel.py & VyceAI defaults
2. AGENTS.md 4 immutable principles enforcement
3. Bale safe size quick edit endpoint & authentication
4. User management metadata without undefined, delete user & purge test users
5. Soroush Plus worker status REQUIRE_AUTH, luxury card titles & connected platform count
6. Feed scraper MP4 extraction & episode number regex parsing
7. Bale adapter forwarded media handling & media keyboard action buttons
8. SUPPORT_CENTER_TEXT and INVITE_FRIENDS_TEXT settings persistence and menu integration
9. Logs drawer minimal toolbar (search, auto-scroll, SVG copy)
10. Version string purity v0.3.8
"""

import unittest
import os
import re

from core.config import config, VersionStr
from core.database import init_db, get_system_setting, set_system_setting
from services.web_panel import get_system_health, render_dashboard_html
from services.user_service import UserService, UserModel
from services.store_service import StoreService
from services.feed_scraper import FALLBACK_ITEMS
from platforms.soroush_worker import SoroushWorker
from platforms.bale_adapter import build_bale_media_keyboard


class TestUNFINITv038(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        os.environ["ENGINE_VERSION"] = "v0.3.8"
        config.ENGINE_VERSION = VersionStr("v0.3.8")

    async def asyncSetUp(self):
        os.environ["ENGINE_VERSION"] = "v0.3.8"
        config.ENGINE_VERSION = VersionStr("v0.3.8")
        await init_db()

    # --- 1. Scoping Bug & VyceAI Standard Defaults ---
    async def test_set_system_setting_available_and_vyceai_defaults(self):
        """Requirement 1: Verify set_system_setting works and VyceAI URL is https://vyceai.com/v1."""
        await set_system_setting("TEST_SCOPE_KEY", "test_scope_val")
        val = await get_system_setting("TEST_SCOPE_KEY")
        self.assertEqual(val, "test_scope_val")
        
        # Verify default VyceAI URL in config
        self.assertEqual(config.AI_BASE_URL, "https://vyceai.com/v1")
        self.assertEqual(config.AI_MODEL, "deepseek-v4.1")

    # --- 2. AGENTS.md 4 Principles ---
    def test_agents_md_rules_enforced(self):
        """Requirement 2: Verify AGENTS.md defines the 4 immutable engineering principles."""
        agents_path = os.path.join(os.path.dirname(__file__), "..", "AGENTS.md")
        with open(agents_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("ممنوعیت مطلق ایموجی در کنترل‌ها و دکمه‌ها", content)
        self.assertIn("ممنوعیت هاردکد رنگ‌های خانواده آبی/سرمه‌ای", content)
        self.assertIn("تایپوگرافی یکپارچه با فونت وزیرمتن", content)
        self.assertIn("شمارش واقعی پلتفرم‌های متصل", content)
        self.assertIn("v0.3.8", content)

    # --- 3. Bale Safe Size Quick Edit ---
    async def test_bale_safe_size_config(self):
        """Requirement 3: Verify MAX_SAFE_BALE_SIZE_MB setting can be read and updated."""
        orig = config.MAX_SAFE_BALE_SIZE_MB
        try:
            await set_system_setting("MAX_SAFE_BALE_SIZE_MB", "47.50")
            raw_val = await get_system_setting("MAX_SAFE_BALE_SIZE_MB", "48.50")
            val = float(raw_val)
            self.assertEqual(val, 47.50)
        finally:
            await set_system_setting("MAX_SAFE_BALE_SIZE_MB", str(orig))

    # --- 4. User Metadata & Operations ---
    def test_user_model_to_dict_and_purge(self):
        """Requirement 4: Verify UserModel.to_dict includes all metadata and purge_test_users works."""
        u = UserModel({
            "user_id": "test_user_123",
            "platform": "telegram",
            "username": "testuser",
            "full_name": "Test User",
            "phone": "09120000000",
            "referred_by": "direct",
            "wallet_balance": 50000,
            "commitment_signed": True
        })
        d = u.to_dict()
        self.assertEqual(d["user_id"], "test_user_123")
        self.assertEqual(d["platform"], "telegram")
        self.assertEqual(d["username"], "testuser")
        self.assertEqual(d["full_name"], "Test User")
        self.assertEqual(d["wallet_balance"], 50000)
        self.assertTrue(d["commitment_signed"])

        # Test delete user
        UserService._users["test_user_123"] = u
        self.assertIn("test_user_123", UserService._users)
        deleted = UserService.delete_user("test_user_123")
        self.assertTrue(deleted)
        self.assertNotIn("test_user_123", UserService._users)

        # Test purge test users
        fake_user = UserModel({"user_id": "fake_demo_999", "platform": "bale", "username": "fake_test_account"})
        UserService._users["fake_demo_999"] = fake_user
        purged = UserService.purge_test_users()
        self.assertGreaterEqual(purged, 1)
        self.assertNotIn("fake_demo_999", UserService._users)

    # --- 5. Soroush Plus Worker & Luxury Platform Titles ---
    def test_soroush_worker_status_and_platform_titles(self):
        """Requirement 5: Verify Soroush+ returns REQUIRE_AUTH when not connected, and luxury titles."""
        worker = SoroushWorker()
        st = worker.get_status()
        self.assertEqual(st["status"], "REQUIRE_AUTH")
        self.assertFalse(st["connected"])

        health = get_system_health()
        platforms_dict = health.get("platforms", {})
        p_names = [p["name"] for p in platforms_dict.values()]
        self.assertIn("تلگرام", p_names)
        self.assertIn("پیام‌رسان بله", p_names)
        self.assertIn("روبیکا کاربری", p_names)
        self.assertIn("سروش‌پلاس", p_names)

        # Verify connected count only counts platforms with connected == True
        conn_count = health.get("connected_platforms_count", 0)
        actual_conn = sum(1 for p in platforms_dict.values() if p.get("connected"))
        self.assertEqual(conn_count, actual_conn)

    # --- 6. Feed Scraper MP4 Extraction & Episode Number Parsing ---
    def test_feed_scraper_mp4_and_episode_parsing(self):
        """Requirement 6: Verify MP4 links are available and Persian episode numbers parsed."""
        # Check fallback items have MP4 video URLs
        self.assertTrue(len(FALLBACK_ITEMS) > 0)
        for fb in FALLBACK_ITEMS:
            self.assertTrue(fb.get("video_download_url") or fb.get("video_url") or ".mp4" in str(fb))

        # Test StoreService episode number auto-extraction
        ep_num = StoreService.extract_episode_number("توحید عملی | قسمت ۱۱", "audio11.mp3", 1)
        self.assertEqual(ep_num, 11)

        ep_num_en = StoreService.extract_episode_number("Course Part 05", "lesson5.mp3", 1)
        self.assertEqual(ep_num_en, 5)

        ep_num_mixed = StoreService.extract_episode_number("فایل آموزشی بخش ۳", "part3.mp4", 1)
        self.assertEqual(ep_num_mixed, 3)

    # --- 7. Bale Forwarded Media & Keyboard Actions ---
    def test_bale_media_keyboard_primary_actions(self):
        """Requirement 7: Verify [🎙 ویرایش تگ‌ها], [➕ افزودن به سرفصل‌های دوره], [⚡ فشرده‌سازی خودکار], [📊 مشخصات فنی]."""
        kb_audio = build_bale_media_keyboard("test1234", {"media_type": "audio"})
        cb_audio = [btn["callback_data"] for row in kb_audio["inline_keyboard"] for btn in row]
        self.assertIn("bmeta:tags_menu:test1234", cb_audio)
        self.assertIn("bmeta:add_to_course:test1234", cb_audio)
        self.assertIn("bmeta:compress:test1234", cb_audio)
        self.assertIn("bmeta:audio_specs:test1234", cb_audio)

        kb_video = build_bale_media_keyboard("test1234", {"media_type": "video"})
        cb_video = [btn["callback_data"] for row in kb_video["inline_keyboard"] for btn in row]
        self.assertIn("bmeta:tags_menu:test1234", cb_video)
        self.assertIn("bmeta:add_to_course:test1234", cb_video)
        self.assertIn("bmeta:compress:test1234", cb_video)
        self.assertIn("bmeta:audio_specs:test1234", cb_video)

    # --- 8. Configurable Support Center & Invite Friends Text ---
    async def test_support_center_and_invite_friends_settings(self):
        """Requirement 8: Verify SUPPORT_CENTER_TEXT and INVITE_FRIENDS_TEXT settings persistence."""
        await set_system_setting("SUPPORT_CENTER_TEXT", "پشتیبانی ۲۴ ساعته تلفنی و تیکت")
        await set_system_setting("INVITE_FRIENDS_TEXT", "با دعوت از دوستانتان ۲۰ درصد هدیه بگیرید")

        s_val = await get_system_setting("SUPPORT_CENTER_TEXT")
        i_val = await get_system_setting("INVITE_FRIENDS_TEXT")
        self.assertEqual(s_val, "پشتیبانی ۲۴ ساعته تلفنی و تیکت")
        self.assertEqual(i_val, "با دعوت از دوستانتان ۲۰ درصد هدیه بگیرید")

    # --- 9. Logs Drawer Minimal Toolbar ---
    def test_logs_drawer_minimal_toolbar(self):
        """Requirement 9: Verify #logsDrawer has minimal toolbar elements (search, auto-scroll, copy)."""
        html = render_dashboard_html()
        self.assertIn('id="logsDrawer"', html)
        self.assertIn('id="drawerLogSearch"', html)
        self.assertIn('id="drawerAutoScroll"', html)
        self.assertIn('id="drawerCopyBtn"', html)

    # --- 10. Version Purity v0.3.8 ---
    def test_version_string_purity(self):
        """Requirement 10: Clean pure v0.3.8 version string."""
        self.assertEqual(str(config.ENGINE_VERSION), "v0.3.8")
        self.assertEqual(config.ENGINE_VERSION.clean, "v0.3.8")
        self.assertNotIn("(", str(config.ENGINE_VERSION))
        self.assertNotIn(")", str(config.ENGINE_VERSION))

        health = get_system_health()
        self.assertIn("v0.3.8", str(health.get("engine_version", "")))


if __name__ == "__main__":
    unittest.main()
