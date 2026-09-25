# -*- coding: utf-8 -*-
"""
آزمون‌های جامع اعتبارسنجی نگارش v0.6.0 موتور UNFINIT
تست‌های مربوط به:
۱. تطابق نگارش موتور با v0.6.0
۲. وجود متد fileno و محاسبه دقیق Content-Length در aiohttp.FormData با ProgressFileReader
۳. پیش‌فرض بافر ۶۴KB در ProgressFileReader
۴. پشتیبانی متدهای send_video، send_document و send_audio از progress_callback در BaleAdapter
۵. اعتبارسنجی ثبت رویدادهای پیشرفت در کال‌بک آپلود
"""

import sys
import inspect
import asyncio
import unittest
from pathlib import Path

# Ensure an active event loop for Python 3.14 / pyrogram
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aiohttp
from core.config import config
from platforms.bale_adapter import ProgressFileReader, BaleAdapter
from platforms.telegram_adapter import TelegramAdapter


class TestVersion060(unittest.TestCase):
    def test_engine_version_is_v060(self):
        """بررسی اینکه نگارش موتور در کانفیگ دقیقاً v0.6.0 است"""
        self.assertEqual(str(config.ENGINE_VERSION), "v0.6.0")
        self.assertTrue(config.ENGINE_VERSION.startswith("v0.6.0"))

    def test_progress_file_reader_has_fileno_and_default_chunk_size(self):
        """بررسی وجود متد fileno و بافر ۶۴KB در ProgressFileReader"""
        test_file = Path(__file__).resolve()
        reader = ProgressFileReader(test_file)
        self.assertEqual(reader.chunk_size, 64 * 1024)
        self.assertTrue(hasattr(reader, "fileno"))
        self.assertIsInstance(reader.fileno(), int)
        reader.close()

    def test_form_data_content_length_is_calculated_for_progress_file_reader(self):
        """تضمین محاسبه ۱۰۰٪ خودکار Content-Length بدون ارسال Chunked Transfer Encoding"""
        test_file = Path(__file__).resolve()
        reader = ProgressFileReader(test_file)
        form = aiohttp.FormData()
        form.add_field("document", reader, filename="test.py", content_type="text/plain")
        body = form()
        self.assertIsNotNone(body.size, "body.size should not be None; must provide exact Content-Length!")
        self.assertGreater(body.size, test_file.stat().st_size)
        reader.close()

    def test_bale_adapter_methods_support_progress_callback(self):
        """بررسی پذیرش progress_callback در کلیه متدهای آپلود بله"""
        bale = BaleAdapter(token="dummy_token")
        sig_vid = inspect.signature(bale.send_video)
        self.assertIn("progress_callback", sig_vid.parameters)

        sig_doc = inspect.signature(bale.send_document)
        self.assertIn("progress_callback", sig_doc.parameters)

        sig_aud = inspect.signature(bale.send_audio)
        self.assertIn("progress_callback", sig_aud.parameters)

    def test_telegram_adapter_pipelined_method(self):
        """بررسی سازگاری متد split_and_transfer_video_to_bale در تلگرام"""
        self.assertTrue(hasattr(TelegramAdapter, "split_and_transfer_video_to_bale"))
        self.assertTrue(inspect.iscoroutinefunction(TelegramAdapter.split_and_transfer_video_to_bale))


if __name__ == "__main__":
    unittest.main()
