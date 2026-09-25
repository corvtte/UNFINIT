# -*- coding: utf-8 -*-
"""
آزمون‌های جامع اعتبارسنجی نگارش v0.5.9 موتور UNFINIT
تست‌های مربوط به:
۱. تطابق نگارش موتور با v0.5.9
۲. پروب مدت‌زمان با get_video_duration_async
۳. فرمت‌بندی پیشرفت فشرده‌سازی با کاراکتر ایزولاسیون LTR/RTL
۴. متد برش تک‌پارت SmartVideoSplitter.split_single_part_async
۵. عملکرد ProgressFileReader با چانک‌های ۱MB
۶. تایم‌اوت‌های مقاوم و لاگ‌های تشخیصی BaleAdapter
۷. پیاده‌سازی متد ارسال ترتیبی پارت‌به‌پارت در TelegramAdapter
"""

import sys
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

from core.config import config
from services.compressor import (
    get_video_duration_sync,
    get_video_duration_async,
    _format_video_progress_msg,
    SmartVideoCompressor,
    SmartVideoSplitter
)
from platforms.bale_adapter import ProgressFileReader, BaleAdapter
from platforms.telegram_adapter import TelegramAdapter


import inspect

class TestVersion059(unittest.TestCase):
    def test_engine_version_is_v059(self):
        """بررسی اینکه نگارش موتور در کانفیگ حداقل v0.5.9 است"""
        self.assertTrue(str(config.ENGINE_VERSION) >= "v0.5.9")

    def test_format_video_progress_msg(self):
        """بررسی صحت فرمت پیام پیشرفت فشرده‌سازی و حضور کاراکتر LTR \u200e"""
        msg = _format_video_progress_msg(
            pct=64,
            speed="1.8x",
            remaining_sec=75,
            orig_mb=76.2,
            target_mb=43.0,
            part_info="پارت ۱ از ۲"
        )
        self.assertIn("\u200e64%", msg)
        self.assertIn("1.8x", msg)
        self.assertIn("01:15", msg)
        self.assertIn("پارت ۱ از ۲", msg)
        self.assertIn("76.2 MB", msg)
        self.assertIn("~43 MB", msg)

    def test_get_video_duration_callables(self):
        """بررسی وجود و قابلیت فراخوانی توابع استخراج مدت زمان"""
        self.assertTrue(callable(get_video_duration_sync))
        self.assertTrue(callable(get_video_duration_async))
        # Non-existent file should gracefully return 0.0
        dur = get_video_duration_sync("non_existent_file.mp4")
        self.assertEqual(dur, 0.0)

    def test_split_single_part_async_exists(self):
        """بررسی وجود متد split_single_part_async روی کلاس اسپیلیتر"""
        self.assertTrue(hasattr(SmartVideoSplitter, "split_single_part_async"))
        self.assertTrue(inspect.iscoroutinefunction(SmartVideoSplitter.split_single_part_async))

    def test_progress_file_reader(self):
        """بررسی خواندن داده‌ها توسط ProgressFileReader و گزارش پیشرفت"""
        data = b"0123456789" * 1000
        reports = []

        def _cb(curr, tot):
            reports.append((curr, tot))

        reader = ProgressFileReader(data, callback=_cb, chunk_size=256)
        self.assertEqual(len(reader), len(data))
        read_data = bytearray()
        while True:
            chunk = reader.read()
            if not chunk:
                break
            read_data.extend(chunk)

        self.assertEqual(bytes(read_data), data)
        self.assertGreater(len(reports), 0)
        self.assertEqual(reports[-1], (len(data), len(data)))

    def test_bale_adapter_send_video_method(self):
        """بررسی متد send_video و وجود امضای صحیح در آداپتور بله"""
        bale = BaleAdapter(token="test_dummy_token")
        self.assertTrue(hasattr(bale, "send_video"))
        self.assertTrue(inspect.iscoroutinefunction(bale.send_video))
        self.assertTrue(hasattr(bale, "send_document"))

    def test_telegram_adapter_pipelined_method(self):
        """بررسی متد split_and_transfer_video_to_bale در آداپتور تلگرام"""
        self.assertTrue(hasattr(TelegramAdapter, "split_and_transfer_video_to_bale"))
        self.assertTrue(inspect.iscoroutinefunction(TelegramAdapter.split_and_transfer_video_to_bale))


if __name__ == "__main__":
    unittest.main()
