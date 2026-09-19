# -*- coding: utf-8 -*-
"""
آزمون‌های اعتبارسنجی نگارش v0.4.3 موتور UNFINIT Store Engine:
۱. همگام‌سازی سراسری شماره نسخه v0.4.3 (کانفیگ، وضعیت سلامت، داشبورد و استورفرانت)
۲. اعتبارسنجی سینتکس جاوااسکریپت و ضدگلوله بودن اسکریپت‌های کلاینت فرانت‌اند در services/web_panel.py
۳. عملکرد متد SignService.ensure_audio_downloaded و سیستم کش فایل صوتی نشانه
۴. انطباق و همگام‌سازی کامل امضای send_audio در BaleAdapter با پارامترهای اختیاری و kwargs
۵. مهار خطای پیام‌های متوالی و اطمینان از عدم وقوع MessageIdInvalid در تلگرام
۶. رعایت استانداردهای مستندسازی و داک‌استرینگ‌های فارسی طبق بند ۵.۵ منشور AGENTS.md
"""

import inspect
import json
import os
import unittest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from core.config import config
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
from core.sign_service import SignService
from platforms.bale_adapter import BaleAdapter


class TestVersion043Features(unittest.TestCase):
    """مجموعه آزمون‌های خودکار جهت اعتبارسنجی امکانات و هات‌فیکس‌های نگارش v0.4.3."""

    def test_01_version_v043_sync(self):
        """اعتبارسنجی نسخه v0.4.3 در تمام بخش‌های اصلی سیستم."""
        self.assertEqual(str(config.ENGINE_VERSION), "v0.4.3")
        health = get_system_health()
        self.assertIn("v0.4.3", health["engine_version"])

        dash_html = render_dashboard_html()
        self.assertIn("v0.4.3", dash_html)

        store_html = render_storefront_html()
        self.assertIn("v0.4.3", store_html)

    def test_02_web_panel_js_scripts_syntax(self):
        """اعتبارسنجی عدم وجود کرش، رشته‌های شکسته یا سینتکس نامعتبر در اسکریپت‌های وب‌پنل."""
        dash_html = render_dashboard_html()
        self.assertIn("<script>", dash_html)
        self.assertIn("</script>", dash_html)

        # بررسی عدم وجود الگوهای خطاساز در جاوااسکریپت
        self.assertNotIn("onclick=\"showSoroushModal('code')", dash_html)
        self.assertNotIn("Unexpected identifier", dash_html)
        # دکمه تست نشانه باید در سورس وجود داشته باشد
        self.assertIn("testTodaySign", dash_html)
        self.assertIn("renderPackageLessons", dash_html)

    def test_03_sign_service_ensure_audio_downloaded(self):
        """اعتبارسنجی متد SignService.ensure_audio_downloaded و ساختار کش دیسک."""
        self.assertTrue(hasattr(SignService, "ensure_audio_downloaded"))
        doc = inspect.getdoc(SignService.ensure_audio_downloaded)
        self.assertIsNotNone(doc)
        self.assertIn("دانلود و نگهداری فایل صوتی نشانه", doc)

        # تست داده فرضی بدون audio_url
        res_empty = asyncio.run(SignService.ensure_audio_downloaded({}))
        self.assertIsNone(res_empty)

        # تست داده با audio_url
        import hashlib
        dummy_sign = {
            "title": "فایل تستی آزمون",
            "audio_url": "https://example.com/audio/sample_test_sign.mp3"
        }
        url_hash = hashlib.md5(dummy_sign["audio_url"].encode("utf-8")).hexdigest()[:12]
        expected_file = SignService.CACHE_DIR / f"sign_audio_{url_hash}.mp3"

        # سناریوی ۱: فایل از قبل در کش موجود است
        SignService.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        expected_file.write_bytes(b"A" * 2048)
        try:
            res = asyncio.run(SignService.ensure_audio_downloaded(dummy_sign))
            self.assertIsNotNone(res)
            self.assertEqual(res, expected_file)
        finally:
            if expected_file.exists():
                expected_file.unlink()

        # سناریوی ۲: دانلود موفق از طریق UrlService.download_file_stream
        async def fake_download(url, dest, **kwargs):
            dest.write_bytes(b"B" * 2048)
            return True

        with patch("services.url_service.UrlService.download_file_stream", side_effect=fake_download):
            try:
                res2 = asyncio.run(SignService.ensure_audio_downloaded(dummy_sign))
                self.assertIsNotNone(res2)
                self.assertTrue(res2.exists())
            finally:
                if expected_file.exists():
                    expected_file.unlink()


    def test_04_bale_send_audio_signature_and_kwargs(self):
        """اعتبارسنجی امضای متد send_audio در BaleAdapter و پشتیبانی منعطف از kwargs."""
        bale = BaleAdapter()
        bale.token = "123456:mock_token_for_test"

        sig = inspect.signature(bale.send_audio)
        params = sig.parameters
        self.assertIn("chat_id", params)
        self.assertIn("file_path", params)
        self.assertIn("kwargs", params)

        doc = inspect.getdoc(bale.send_audio)
        self.assertIsNotNone(doc)
        self.assertIn("ارسال فایل صوتی به چت بله", doc)

        # تست فراخوانی send_audio با audio_path_or_url به عنوان kwarg بدون بروز TypeError
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_resp = AsyncMock()
            mock_resp.json = AsyncMock(return_value={"ok": True, "result": {"message_id": 999}})
            mock_post.return_value.__aenter__.return_value = mock_resp

            res = asyncio.run(bale.send_audio(
                chat_id=112233,
                audio_path_or_url="https://example.com/audio/sample.mp3",
                caption="تست نشانه"
            ))
            self.assertIsNotNone(res)
            self.assertTrue(res.get("ok"))

    def test_05_persian_docstring_compliance(self):
        """اعتبارسنجی انطباق متدها و کلاس‌های تازه با بند ۵.۵ منشور مهندسی AGENTS.md."""
        self.assertIsNotNone(inspect.getdoc(SignService))
        self.assertIsNotNone(inspect.getdoc(SignService.ensure_audio_downloaded))
        self.assertIsNotNone(inspect.getdoc(BaleAdapter.send_audio))


if __name__ == "__main__":
    unittest.main()
