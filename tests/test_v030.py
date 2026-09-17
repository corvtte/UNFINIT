import os
import io
import csv
import json
import asyncio
import unittest
from pathlib import Path

from core.config import config
from core.security import (
    derive_fernet_key,
    get_encryption_key,
    get_fernet_cipher,
    encrypt_data,
    decrypt_data,
    UNFINIT_DATA_SALT
)
from core.database import (
    init_db,
    db_get_cached_file_id,
    db_set_cached_file_id
)
from services.user_service import (
    UserService,
    UserModel,
    normalize_phone
)
from services.referral_service import (
    ReferralService,
    TOHID_AMALI_PACK_ID,
    TOHID_AMALI_EPISODES
)
from services.web_panel import get_system_health, render_dashboard_html


class TestV030EngineRelease(unittest.TestCase):
    _original_file_content = None

    @classmethod
    def setUpClass(cls):
        enc_file = config.USERS_ENC_FILE
        if enc_file.exists():
            cls._original_file_content = enc_file.read_bytes()
            enc_file.unlink()
        else:
            cls._original_file_content = None

    @classmethod
    def tearDownClass(cls):
        enc_file = config.USERS_ENC_FILE
        if cls._original_file_content is not None:
            enc_file.parent.mkdir(parents=True, exist_ok=True)
            enc_file.write_bytes(cls._original_file_content)
        elif enc_file.exists():
            enc_file.unlink()

    def setUp(self):
        enc_file = config.USERS_ENC_FILE
        if enc_file.exists():
            enc_file.unlink()
        UserService.clear_cache()

    def tearDown(self):
        enc_file = config.USERS_ENC_FILE
        if enc_file.exists():
            enc_file.unlink()
        UserService.clear_cache()

    def test_01_version_bump_v030(self):
        self.assertIn(config.ENGINE_VERSION, ("v0.3.0", "v0.3.1", "v0.3.2", "v0.3.3", "v0.3.4"))
        health = get_system_health()
        self.assertTrue(any(v in str(health["engine_version"]) for v in ("v0.3.0", "v0.3.1", "v0.3.2", "v0.3.3", "v0.3.4")))

    def test_02_security_fernet_key_derivation_and_encryption(self):
        """Verify PBKDF2 HMAC key derivation and AES-256 / Fernet roundtrip."""
        key1 = derive_fernet_key("admin12345")
        key2 = derive_fernet_key("admin12345")
        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 44)  # Base64 encoded 32-byte key

        raw_payload = b'{"users": {"09123456789": {"name": "Sajjad", "phone": "09123456789"}}}'
        encrypted = encrypt_data(raw_payload, key1)
        self.assertNotEqual(encrypted, raw_payload)

        decrypted = decrypt_data(encrypted, key1)
        self.assertEqual(decrypted, raw_payload.decode("utf-8"))

        # Tampered data should fail gracefully
        tampered = encrypted[:-5] + b"XXXXX"
        with self.assertRaises(Exception):
            decrypt_data(tampered, key1)

    def test_03_phone_normalization(self):
        """Verify Iranian phone numbers normalization into 09xxxxxxxxx format."""
        self.assertEqual(normalize_phone("09123456789"), "09123456789")
        self.assertEqual(normalize_phone("+989123456789"), "09123456789")
        self.assertEqual(normalize_phone("00989123456789"), "09123456789")
        self.assertEqual(normalize_phone("989123456789"), "09123456789")
        self.assertEqual(normalize_phone("9123456789"), "09123456789")
        self.assertEqual(normalize_phone("۰۹۱۲۳۴۵۶۷۸۹"), "09123456789")
        self.assertEqual(normalize_phone("  0912-345-6789  "), "09123456789")
        self.assertIsNone(normalize_phone("12345"))
        self.assertIsNone(normalize_phone(""))

    def test_04_cross_platform_user_identity_sync(self):
        """Verify cross-platform user linking between Telegram and Bale by phone."""
        # 1. User registers first via Telegram
        user_tg = UserService.link_platform_user(
            platform="telegram",
            platform_id=111222333,
            phone="09121112233",
            full_name="Ali Reza"
        )
        self.assertEqual(user_tg.phone, "09121112233")
        self.assertEqual(user_tg.telegram_id, "111222333")
        self.assertIsNone(user_tg.bale_id)
        self.assertTrue(bool(user_tg.referral_code))

        # Accept terms on Telegram
        UserService.accept_terms_by_platform("telegram", 111222333)
        self.assertTrue(UserService.get_user_by_phone("09121112233").terms_accepted)

        # 2. Same user connects later on Bale with same phone number
        user_bale = UserService.link_platform_user(
            platform="bale",
            platform_id="bale_user_999",
            phone="09121112233",
            full_name="Ali Reza (Bale)"
        )
        # Verify account was merged, not duplicated
        self.assertEqual(user_bale.phone, "09121112233")
        self.assertEqual(user_bale.telegram_id, "111222333")
        self.assertEqual(user_bale.bale_id, "bale_user_999")
        self.assertTrue(user_bale.terms_accepted)

        # 3. Querying by Bale platform ID returns unified account
        by_bale = UserService.get_user_by_platform_id("bale", "bale_user_999")
        self.assertIsNotNone(by_bale)
        self.assertEqual(by_bale.telegram_id, "111222333")

    def test_05_viral_referral_engine_and_tohid_amali_unlock(self):
        """Verify 1-referral condition unlocks Tohid Amali 11-part audio pack."""
        # Create inviter
        inviter = UserService.link_platform_user(
            platform="telegram",
            platform_id=5550001,
            phone="09125550001",
            full_name="Inviter User"
        )
        inviter_code = inviter.referral_code
        self.assertEqual(inviter.successful_invites, 0)
        self.assertNotIn(TOHID_AMALI_PACK_ID, inviter.unlocked_gifts)

        # Parse referral code helper
        parsed = ReferralService.parse_referral_code(f"ref_{inviter_code}")
        self.assertEqual(parsed, inviter_code)
        self.assertEqual(ReferralService.parse_referral_code(inviter_code), inviter_code)

        # Self referral should be rejected
        inv_phone, newly_unlocked = ReferralService.record_referral(
            inviter_code=inviter_code,
            invited_phone="09125550001",
            invited_platform="telegram",
            invited_platform_id=5550001
        )
        self.assertIsNone(inv_phone)
        self.assertFalse(newly_unlocked)

        # Invited user 1 joins
        inv_phone, newly_unlocked = ReferralService.record_referral(
            inviter_code=inviter_code,
            invited_phone="09128880002",
            invited_platform="bale",
            invited_platform_id="bale_friend_2"
        )
        self.assertEqual(inv_phone, "09125550001")
        self.assertTrue(newly_unlocked)

        # Verify inviter has 1 invite and gift unlocked
        refreshed_inviter = UserService.get_user_by_phone("09125550001")
        self.assertEqual(refreshed_inviter.successful_invites, 1)
        self.assertIn(TOHID_AMALI_PACK_ID, refreshed_inviter.unlocked_gifts)
        self.assertTrue(UserService.is_gift_unlocked_by_platform("telegram", 5550001, TOHID_AMALI_PACK_ID))

        # Check Tohid Amali pack episodes metadata
        self.assertEqual(len(TOHID_AMALI_EPISODES), 11)
        self.assertEqual(TOHID_AMALI_EPISODES[0]["part"], 1)
        self.assertEqual(TOHID_AMALI_EPISODES[10]["part"], 11)

    def test_06_database_file_cache_table(self):
        """Verify SQLite file_cache table for zero-bandwidth file_id delivery."""
        async def run_cache_test():
            await init_db()
            from core.database import execute_write
            await execute_write("DELETE FROM file_cache WHERE file_key = 'test_tohid_part_1'")

            # Cache miss
            fid = await db_get_cached_file_id("test_tohid_part_1", "telegram")
            self.assertIsNone(fid)

            # Store in cache
            await db_set_cached_file_id("test_tohid_part_1", "telegram", "CQACAgQAAxkBAAE...", "audio")
            cached = await db_get_cached_file_id("test_tohid_part_1", "telegram")
            self.assertEqual(cached, "CQACAgQAAxkBAAE...")

            # Store for bale
            await db_set_cached_file_id("test_tohid_part_1", "bale", "bale_fid_12345", "audio")
            cached_bale = await db_get_cached_file_id("test_tohid_part_1", "bale")
            self.assertEqual(cached_bale, "bale_fid_12345")

            # Check update
            await db_set_cached_file_id("test_tohid_part_1", "telegram", "NEW_TG_FILE_ID", "audio")
            updated = await db_get_cached_file_id("test_tohid_part_1", "telegram")
            self.assertEqual(updated, "NEW_TG_FILE_ID")

        asyncio.run(run_cache_test())

    def test_07_contacts_csv_export(self):
        """Verify in-memory CSV export format for CRM contacts."""
        UserService.link_platform_user("telegram", 9991, "09129990001", "User Alpha")
        UserService.link_platform_user("bale", 9992, "09129990002", "User Beta")

        csv_content = UserService.export_contacts_csv()
        self.assertTrue(isinstance(csv_content, str))
        self.assertIn("09129990001", csv_content)
        self.assertIn("09129990002", csv_content)
        self.assertIn("User Alpha", csv_content)
        self.assertIn("User Beta", csv_content)
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        self.assertGreaterEqual(len(rows), 3)  # Header + 2 users
        header = rows[0]
        self.assertTrue(any("موبایل" in col for col in header))
        self.assertTrue(any("نام" in col for col in header))

    def test_08_zero_git_and_hf_sync_rules(self):
        """Verify data/ and *.enc are excluded from git and HF sync."""
        gitignore_path = Path(".gitignore")
        self.assertTrue(gitignore_path.exists())
        gitignore_content = gitignore_path.read_text(encoding="utf-8")
        self.assertIn("data/", gitignore_content)
        self.assertIn("*.enc", gitignore_content)

        hf_manager_path = Path("scripts/hf_manager.py")
        self.assertTrue(hf_manager_path.exists())
        hf_content = hf_manager_path.read_text(encoding="utf-8")
        self.assertIn("DATA_ENCRYPTION_KEY", hf_content)
        self.assertIn("data/*", hf_content)
        self.assertIn("*.enc", hf_content)

    def test_09_web_panel_contacts_export_button(self):
        """Verify web panel contains the contacts CSV export button."""
        dash_html = render_dashboard_html()
        self.assertIn("/api/contacts/export_csv", dash_html)
        self.assertIn("handleExportContactsCSV", dash_html)


if __name__ == "__main__":
    unittest.main()
