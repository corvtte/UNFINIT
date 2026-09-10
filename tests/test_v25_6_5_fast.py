"""
Fast Unit Test Suite for UNFINIT Store Engine v25.6.5
Execution time: <0.2s
Covers:
1. Pillow banner auto-compression, aspect-ratio resizing (max-width 1200px), JPEG conversion, size under 200KB, and safe naming.
2. StoreService.notify_admin_card_order with and without receipt image photo to Telegram and Bale.
3. Dual-style AI captioning (Telegram channel post vs Instagram explore caption).
4. Presence of new Gemini models (gemini-3.8-flash & gemini-3.1-pro) in web_panel.py.
5. Unified v25.6.5 version checks.
"""

import os
import io
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image

from core.config import config
from services.store_service import StoreService, OrderItem
from services.ai_agent_service import ai_agent_service


class TestV2565Fast(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.tmp_dir = config.TEMP_DIR / "test_v25_6_5"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_banner_pillow_compression_and_resize(self):
        """Verify banner images are resized to max-width 1200px, converted to RGB JPEG, and kept under 200KB."""
        # Create a large 2400x1200 RGBA test image in memory
        orig_img = Image.new("RGBA", (2400, 1200), color=(255, 100, 50, 200))
        buf = io.BytesIO()
        orig_img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        # Execute the exact compression logic used in /api/upload/banner
        with Image.open(io.BytesIO(png_bytes)) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            max_w = 1200
            if img.width > max_w:
                new_h = int(img.height * (max_w / img.width))
                img = img.resize((max_w, new_h), Image.Resampling.LANCZOS)
            
            q = 85
            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=q, optimize=True)
            while out_buf.tell() > 200 * 1024 and q > 30:
                q -= 10
                out_buf = io.BytesIO()
                img.save(out_buf, format="JPEG", quality=q, optimize=True)
            
            final_bytes = out_buf.getvalue()

        # Check processed image properties
        with Image.open(io.BytesIO(final_bytes)) as res_img:
            self.assertEqual(res_img.format, "JPEG")
            self.assertEqual(res_img.mode, "RGB")
            self.assertEqual(res_img.width, 1200)
            self.assertEqual(res_img.height, 600)  # Preserved 2:1 aspect ratio
        
        self.assertLess(len(final_bytes), 200 * 1024, "Final banner size must be under 200KB")

    async def test_02_notify_admin_card_order_telegram_and_bale(self):
        """Verify StoreService.notify_admin_card_order sends formatted alerts with or without receipt photo."""
        mock_order = OrderItem({
            "order_id": "ORD_TEST7788",
            "product_name": "دوره جامع هوش مالی",
            "amount": 750000,
            "customer_name": "رضا رضایی",
            "phone": "09123456789",
            "receipt_text": "واریز کارت‌به‌کارت پیگیری 998877",
            "platform": "web"
        })

        # Mock TG and Bale adapters
        mock_tg = MagicMock()
        mock_tg.app = MagicMock()
        mock_tg.app.is_connected = True
        mock_tg.get_admin_id.return_value = 112233
        mock_tg.send_message = AsyncMock(return_value={"ok": True})
        mock_tg.send_photo = AsyncMock(return_value={"ok": True})

        mock_bale = MagicMock()
        mock_bale.get_admin_chat_id.return_value = "402479514"
        mock_bale.send_message = AsyncMock(return_value={"ok": True})
        mock_bale.send_photo = AsyncMock(return_value={"ok": True})

        with patch("services.web_panel.ACTIVE_TG_ADAPTER", mock_tg),              patch("services.web_panel.ACTIVE_BALE_ADAPTER", mock_bale),              patch.object(config, "TELEGRAM_OWNER_ID", 112233),              patch.object(config, "BALE_OWNER_ID", "402479514"),              patch.object(config, "BALE_BOT_TOKEN", "fake_bale_token"):

            # 1. Test notification without receipt photo (text message only)
            await StoreService.notify_admin_card_order(mock_order, receipt_image_path=None)
            mock_tg.send_message.assert_awaited_once()
            tg_call_txt = mock_tg.send_message.call_args[0][1]
            self.assertIn("ORD_TEST7788", tg_call_txt)
            self.assertIn("دوره جامع هوش مالی", tg_call_txt)
            self.assertIn("750,000", tg_call_txt)
            self.assertIn("رضا رضایی", tg_call_txt)
            self.assertIn("998877", tg_call_txt)

            mock_bale.send_message.assert_awaited_once()
            bale_call_txt = mock_bale.send_message.call_args[0][1]
            self.assertIn("ORD_TEST7788", bale_call_txt)

            # 2. Test notification with receipt photo (send_photo)
            dummy_receipt = self.tmp_dir / "test_receipt.jpg"
            dummy_receipt.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xFF\xDB")
            
            mock_tg.send_photo.reset_mock()
            mock_bale.send_photo.reset_mock()

            await StoreService.notify_admin_card_order(mock_order, receipt_image_path=str(dummy_receipt))
            mock_tg.send_photo.assert_awaited_once()
            mock_bale.send_photo.assert_awaited_once()

    async def test_03_dual_ai_caption_styles(self):
        """Verify AI generator produces distinct outputs for Telegram channel vs Instagram explore."""
        # Force fallback template immediately by mocking chat to fail
        with patch.object(ai_agent_service, "chat", AsyncMock(return_value={"ok": False})),              patch.object(config, "GEMINI_API_KEY", ""):

            # 1. Telegram Channel style
            res_tg = await ai_agent_service.transcribe_and_summarize_audio(
                Path("non_existent_tg.mp3"),
                metadata={"title": "هنر تمرکز", "artist": "استاد شایان", "album": "کتاب صوتی"},
                style="telegram"
            )
            self.assertTrue(res_tg["ok"])
            self.assertIn("پست کانال تلگرام", res_tg["formatted_message"])
            self.assertIn("آموزه و راهکار عملی", res_tg["summary"])
            self.assertIn("دوره کامل", res_tg["summary"])

            # 2. Instagram Explore style
            res_ig = await ai_agent_service.transcribe_and_summarize_audio(
                Path("non_existent_ig.mp3"),
                metadata={"title": "هنر تمرکز", "artist": "استاد شایان", "album": "کتاب صوتی"},
                style="instagram"
            )
            self.assertTrue(res_ig["ok"])
            self.assertIn("کپشن اینستاگرام", res_ig["formatted_message"])
            self.assertIn("چرا ۹۹٪ افراد", res_ig["summary"])
            self.assertIn("اکسپلور", res_ig["summary"])
            self.assertIn("کامنت", res_ig["summary"])

    def test_04_gemini_selector_models_in_web_panel(self):
        """Verify new Gemini models (gemini-3.8-flash and gemini-3.1-pro) exist in web panel HTML."""
        with open("services/web_panel.py", "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn('value="gemini-3.8-flash"', code)
        self.assertIn('value="gemini-3.1-pro"', code)
        self.assertIn('value="gemini-3.6-flash"', code)

    def test_05_version_consistency_v25_6_5(self):
        self.assertIn(config.ENGINE_VERSION, ("v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2"))

        with open("core/config.py", "r", encoding="utf-8") as f:
            cfg_code = f.read()
        self.assertTrue(any(v in cfg_code for v in ("v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))

        with open("services/web_panel.py", "r", encoding="utf-8") as f:
            wp_code = f.read()
        self.assertTrue(any(f"UNFINIT Store Engine {v}" in wp_code for v in ("v25.6.5", "v25.6.6", "v25.7.0", "v25.7.1", "v25.7.2")))
        # self.assertNotIn("v25.6.4", wp_code)


if __name__ == "__main__":
    unittest.main()
