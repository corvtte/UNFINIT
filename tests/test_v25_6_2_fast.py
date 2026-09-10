import os
import sys
import unittest
import asyncio
from unittest.mock import patch, AsyncMock
from pathlib import Path

# Setup event loop for Python 3.14 + Pyrogram compatibility
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.config import config
from platforms.telegram_adapter import format_transfer_progress, TelegramAdapter
from services.ai_agent_service import ai_agent_service, STUDIO_SYSTEM_PROMPT

class TestV2562Fast(unittest.TestCase):
    def test_01_version_strings(self):
        self.assertIn(config.ENGINE_VERSION, ("v0.1.0",))
        
        with open("services/web_panel.py", encoding="utf-8") as f:
            wp_content = f.read()
        self.assertIn("v0.1.0", wp_content)
        self.assertIn("v0.1.0", wp_content)

    def test_02_format_transfer_progress(self):
        text = format_transfer_progress(
            current=25 * 1024 * 1024,
            total=100 * 1024 * 1024,
            elapsed_sec=5.0,
            stage_title="در حال انتقال فایل..."
        )
        self.assertIn("⏳ <b>در حال انتقال فایل...</b>", text)
        self.assertIn("25%", text)
        self.assertIn("25.00 MB", text)
        self.assertIn("100.00 MB", text)
        self.assertIn("5.00 MB/s", text)
        self.assertIn("<code>[", text)

    def test_03_telegram_keyboard_no_quick_send(self):
        fake_data = {"media_type": "audio", "working_path": "audio.mp3"}
        kb = TelegramAdapter.build_media_keyboard(None, "test1234", fake_data)
        serialized = str(kb)
        self.assertNotIn("quick_send", serialized)
        self.assertNotIn("اعمال سریع", serialized)
        self.assertIn("apply_changes", serialized)
        self.assertIn("اعمال تغییرات", serialized)

    def test_04_bale_smart_compression_monitor_message(self):
        with open("media/compressor.py", encoding="utf-8") as f:
            comp_content = f.read()
        self.assertIn("🎛 <b>در حال فشرده‌سازی هوشمند جهت رعایت سقف بله...</b>", comp_content)
        self.assertIn("📊 حجم فعلی: <code>{orig_size_mb} MB</code> ➔ هدف: <code>زیر 49.9 MB</code>", comp_content)
        self.assertIn("⚙️ فرآیند بهینه‌سازی صدا و تصویر در حال اجراست، لطفاً شکیبا باشید...", comp_content)

        with open("platforms/bale_adapter.py", encoding="utf-8") as f:
            bale_content = f.read()
        self.assertIn("🎛 <b>در حال فشرده‌سازی هوشمند جهت رعایت سقف بله...</b>", bale_content)
        self.assertIn("هدف: <code>زیر 49.9 MB</code>", bale_content)

    def test_05_ai_prompt_senior_copywriting_and_no_cliches(self):
        self.assertIn("تحلیلگر ارشد محتوا", STUDIO_SYSTEM_PROMPT)
        self.assertIn("قلاب جذاب (Hook)", STUDIO_SYSTEM_PROMPT)

        with open("services/ai_agent_service.py", encoding="utf-8") as f:
            ai_code = f.read()
        self.assertIn("تیتر و قلاب جذاب (Hook)", ai_code)
        self.assertIn("پیام و بینش بنیادین فایل", ai_code)
        self.assertIn("۳ آموزه و راهکار عملی", ai_code)
        self.assertIn("کپشن اختصاصی کانال", ai_code)
        self.assertIn("پرهیز", ai_code)

        # 1. Test local fallback execution (offline mode, fast <0.1s)
        with patch.object(ai_agent_service, "analyze_audio_with_gemini", new_callable=AsyncMock) as mock_gem, \
             patch.object(ai_agent_service, "chat", new_callable=AsyncMock) as mock_chat:
            mock_gem.return_value = None
            mock_chat.return_value = {"ok": False}
            
            res = loop.run_until_complete(ai_agent_service.transcribe_and_summarize_audio(
                audio_path=Path("non_existent.mp3"),
                metadata={"title": "هنر تمرکز عمیق", "artist": "استاد شایان", "album": "بهره‌وری فردی"}
            ))
            self.assertTrue(res["ok"])
            summary = res["summary"]
            self.assertNotIn("بررسی سرفصل‌ها", summary)
            self.assertNotIn("هزار بار خریداری شود", summary)
            self.assertIn("تیتر و قلاب جذاب (Hook)", summary)
            self.assertIn("پیام و بینش بنیادین فایل", summary)
            self.assertIn("۳ آموزه و راهکار عملی", summary)
            self.assertIn("کپشن اختصاصی کانال", summary)

        # 2. Test successful AI response formatting
        with patch.object(ai_agent_service, "analyze_audio_with_gemini", new_callable=AsyncMock) as mock_gem, \
             patch.object(ai_agent_service, "chat", new_callable=AsyncMock) as mock_chat:
            mock_gem.return_value = None
            mock_chat.return_value = {
                "ok": True,
                "reply": "۱. <b>تیتر و قلاب جذاب (Hook):</b> هنر تمرکز\n۲. <b>پیام و بینش بنیادین فایل:</b> رشد فردی\n۳. <b>۳ آموزه و راهکار عملی:</b> ۱- عمل ۲- صبر ۳- استمرار\n۴. <b>کپشن اختصاصی کانال:</b> دوره آموزشی"
            }
            res_ai = loop.run_until_complete(ai_agent_service.transcribe_and_summarize_audio(
                audio_path=Path("non_existent.mp3"),
                metadata={"title": "هنر تمرکز عمیق", "artist": "استاد شایان", "album": "بهره‌وری فردی"}
            ))
            self.assertTrue(res_ai["ok"])
            self.assertIn("هنر تمرکز", res_ai["summary"])
            self.assertIn("دستیار هوش مصنوعی و تحلیلگر صوت UNFINIT", res_ai["formatted_message"])

if __name__ == "__main__":
    unittest.main()
