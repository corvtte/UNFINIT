"""
Unit test suite for UNFINIT Store Engine v0.3.1 release.
Tests:
- Engine version bump (v0.3.1) in config and web_panel
- config.BOT_TOKEN backward compatibility property
- Deterministic numerical user-ID based referral links (no ref_bale or ref_telegram)
- Referral code parsing
- requires_referral attribute in ProductItem and StoreService
- Course terms text dynamic loading and persistence
- AI course description summarizer under 255 characters
"""

import unittest
import asyncio
from core.config import config
from core.database import init_db, get_system_setting, set_system_setting
from services.store_service import StoreService, ProductItem
from services.referral_service import ReferralService
from services.ai_service import ai_service
from services.web_panel import get_system_health


class TestV031Release(unittest.TestCase):

    def test_01_version_bump(self):
        self.assertIn(config.ENGINE_VERSION, ("v0.3.1", "v0.3.2", "v0.3.3", "v0.3.4", "v0.3.5", "v0.3.6"))
        health = get_system_health()
        self.assertTrue(any(v in str(health.get("engine_version", "")) for v in ("v0.3.1", "v0.3.2", "v0.3.3", "v0.3.4", "v0.3.5", "v0.3.6")))

    def test_02_bot_token_property(self):
        """Verify config.BOT_TOKEN returns BALE_BOT_TOKEN or TELEGRAM_BOT_TOKEN fallback."""
        self.assertTrue(hasattr(config, "BOT_TOKEN"))
        expected = config.BALE_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN
        self.assertEqual(config.BOT_TOKEN, expected)

    def test_03_referral_link_deterministic_user_id(self):
        """Verify referral links are strictly based on numerical user ID and never contain ref_telegram or ref_bale."""
        # Telegram format
        tg_link = ReferralService.get_referral_link(123456789, "telegram", "UNFINIT_Bot")
        self.assertEqual(tg_link, "https://t.me/UNFINIT_Bot?start=ref_123456789")
        self.assertNotIn("ref_telegram", tg_link)
        self.assertNotIn("ref_bale", tg_link)

        # Bale format
        bale_link = ReferralService.get_referral_link(987654321, "bale", "UNFINIT_Bale_Bot")
        self.assertEqual(bale_link, "https://ble.ir/UNFINIT_Bale_Bot?start=ref_987654321")
        self.assertNotIn("ref_telegram", bale_link)
        self.assertNotIn("ref_bale", bale_link)

        # Inverted parameter order compatibility test
        inv_tg = ReferralService.get_referral_link("telegram", 555444333, "TestBot")
        self.assertEqual(inv_tg, "https://t.me/TestBot?start=ref_555444333")

        inv_bale = ReferralService.get_referral_link("bale", 111222333, "TestBale")
        self.assertEqual(inv_bale, "https://ble.ir/TestBale?start=ref_111222333")

        # String numerical ID with ref_ prefix already attached
        prefixed = ReferralService.get_referral_link("ref_777888", "telegram", "MyBot")
        self.assertEqual(prefixed, "https://t.me/MyBot?start=ref_777888")

    def test_04_parse_referral_code(self):
        """Verify parsing referral code properly extracts the user ID."""
        self.assertEqual(ReferralService.parse_referral_code("ref_123456"), "123456")
        self.assertEqual(int(ReferralService.parse_referral_code("ref_123456")), 123456)
        self.assertEqual(ReferralService.parse_referral_code("123456"), "123456")
        self.assertIsNone(ReferralService.parse_referral_code(""))

    def test_05_course_terms_text(self):
        """Verify course terms text exists in config and can be retrieved from DB."""
        self.assertTrue(hasattr(config, "COURSE_TERMS_TEXT"))
        self.assertIsNotNone(config.COURSE_TERMS_TEXT)
        self.assertGreater(len(config.COURSE_TERMS_TEXT), 10)

        async def check_terms():
            await init_db()
            await set_system_setting("COURSE_TERMS_TEXT", "شرایط اختصاصی آزمایشی خرید دوره")
            val = await get_system_setting("COURSE_TERMS_TEXT", config.COURSE_TERMS_TEXT)
            return val

        orig = config.COURSE_TERMS_TEXT
        terms_val = asyncio.run(check_terms())
        self.assertEqual(terms_val, "شرایط اختصاصی آزمایشی خرید دوره")
        asyncio.run(set_system_setting("COURSE_TERMS_TEXT", orig))

    def test_06_requires_referral_in_product(self):
        """Verify requires_referral attribute in ProductItem and StoreService."""
        item = ProductItem({
            "product_id": "test_v031_prod",
            "name": "دوره آزمایشی v0.3.1",
            "price": 0,
            "description": "توضیحات تست",
            "requires_referral": 1
        })
        self.assertTrue(item.requires_referral)

        async def store_ops():
            await init_db()
            added = await StoreService.add_product(
                name="دوره هدیه تستی",
                price=0,
                description="توضیح هدیه",
                requires_referral=True
            )
            prod = await StoreService.get_product(added.product_id)
            is_req = getattr(prod, "requires_referral", False)
            # Clean up
            await StoreService.delete_product(added.product_id)
            return is_req

        result = asyncio.run(store_ops())
        self.assertTrue(result)

    def test_07_ai_course_summarizer(self):
        """Verify AI summarizer truncates / summarizes to <= 255 characters."""
        long_desc = "این یک متن بسیار طولانی برای تست عملکرد خلاصه‌ساز هوشمند دوره برای پیام‌رسان بله است. " * 10
        summary = asyncio.run(ai_service.summarize_course_for_bale(long_desc))
        self.assertLessEqual(len(summary), 255)
        self.assertGreater(len(summary), 10)


if __name__ == "__main__":
    unittest.main()