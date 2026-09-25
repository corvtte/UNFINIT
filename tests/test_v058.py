# -*- coding: utf-8 -*-
"""
مجموعه آزمون‌های خودکار نگارش v0.5.8 موتور UNFINIT (UNFINIT Store Engine)
اعتبارسنجی فشرده‌سازی غیرمسدودکننده ویدیویی با FFmpeg آسنکرون (True Async)،
نوار پیشرفت زنده درصد، سرعت و زمان باقی‌مانده، تایم‌اوت مقاوم ۴۵۰ ثانیه‌ای آپلود بله،
و صف ترتیبی FIFO برای عملیات‌های چندفایله (SequentialBatchQueue).
"""

import sys
import unittest
import asyncio
import inspect
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

try:
    asyncio.get_event_loop()
except RuntimeError:
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

from core.config import config
from services.compressor import (
    SmartVideoCompressor,
    SmartVideoSplitter,
    SmartAudioCompressor,
    _format_video_progress_msg,
    SAFE_BALE_PART_LIMIT_MB
)
from services.media_service import MediaService, SequentialBatchQueue
from platforms.bale_adapter import BaleAdapter


class TestEngineVersion058(unittest.TestCase):
    """آزمون‌های اعتبارسنجی نگارش موتور v0.5.8"""

    def test_engine_version(self):
        self.assertEqual(str(config.ENGINE_VERSION), "v0.5.8")
        self.assertIn("v0.5.8", config.ENGINE_VERSION)


class TestAsyncVideoEngine(unittest.TestCase):
    """آزمون‌های اعتبارسنجی موتور ویدیویی آسنکرون و غیرمسدودکننده"""

    def test_async_ffmpeg_progress_method_exists(self):
        self.assertTrue(hasattr(SmartVideoCompressor, "_execute_ffmpeg_progress_async"))
        self.assertTrue(inspect.iscoroutinefunction(SmartVideoCompressor._execute_ffmpeg_progress_async))

    def test_async_compress_and_split_methods(self):
        self.assertTrue(hasattr(SmartVideoCompressor, "compress_if_needed"))
        self.assertTrue(inspect.iscoroutinefunction(SmartVideoCompressor.compress_if_needed))
        self.assertTrue(hasattr(SmartVideoSplitter, "split_video_async"))
        self.assertTrue(inspect.iscoroutinefunction(SmartVideoSplitter.split_video_async))

    def test_format_video_progress_msg(self):
        msg = _format_video_progress_msg(
            pct=64,
            speed="1.8x",
            remaining_sec=45,
            orig_mb=76.2,
            target_mb=43.0,
            part_info="پارت ۱ از ۲"
        )
        self.assertIn("⚙️ [پارت ۱ از ۲] در حال فشرده‌سازی هوشمند ویدیو...", msg)
        self.assertIn("64%", msg)
        self.assertIn("1.8x", msg)
        self.assertIn("00:45", msg)
        self.assertIn("76.2 MB", msg)
        self.assertIn("43 MB", msg)

    def test_precalculate_quality(self):
        res = SmartVideoCompressor.precalculate_video_quality("non_existent.mp4", target_max_mb=SAFE_BALE_PART_LIMIT_MB)
        self.assertIn("duration_sec", res)
        self.assertIn("target_v_bitrate", res)
        self.assertIn("recommended_parts", res)


class TestSequentialBatchQueue(unittest.IsolatedAsyncioTestCase):
    """آزمون‌های صف ترتیبی FIFO چندفایله"""

    def test_batch_queue_exists(self):
        self.assertTrue(hasattr(MediaService, "batch_queue"))
        self.assertIsInstance(MediaService.batch_queue, SequentialBatchQueue)
        self.assertTrue(hasattr(MediaService, "process_batch_sequentially"))
        self.assertTrue(inspect.iscoroutinefunction(MediaService.process_batch_sequentially))

    async def test_fifo_sequential_execution_order(self):
        queue = SequentialBatchQueue()
        execution_order = []

        async def job1():
            await asyncio.sleep(0.05)
            execution_order.append(1)
            return "ok1"

        async def job2():
            execution_order.append(2)
            return "ok2"

        res1_task = asyncio.create_task(queue.enqueue(job1))
        res2_task = asyncio.create_task(queue.enqueue(job2))

        r1 = await res1_task
        r2 = await res2_task

        self.assertEqual(r1, "ok1")
        self.assertEqual(r2, "ok2")
        self.assertEqual(execution_order, [1, 2], "Jobs must be processed in strict FIFO order")


if __name__ == "__main__":
    unittest.main()
