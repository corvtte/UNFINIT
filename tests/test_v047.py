# -*- coding: utf-8 -*-
"""
آزمون‌های جامع اعتبارسنجی نگارش v0.4.7
UNFINIT Store Engine v0.4.7 Verification Suite

تست‌های این ماژول ۹ بند اصلی نسخه v0.4.7 را بررسی می‌کنند:
۱. دستیار هوشمند کمپرس یا اسپلیت ویدیو (Pre-calculation & Splitter)
۲. دانلود توربو تلگرام با استریم پیوسته
۳. مدیریت متادیتا و تگ‌ها (سوییچ‌های خواننده و تغییر نام فایل)
۴. ساماندهی استودیو رسانه و یوآی آکاردئونی تاشو
۵. احیای پایدار درگ‌وان‌دراپ سایدبار بدون مسدودسازی کلیک
۶. نوار ناوبری پایین صفحه موبایل با دکمه مرکزی محصولات
۷. سیستم ارسال دسته‌جمعی رسانه‌ها (Batch Forwarding Manager)
۸. پیام وضعیت متمرکز و مهار خطای FFmpeg In-Place
۹. انطباق و همگام‌سازی نگارش v0.4.7 در کل پروژه
"""

import os
import unittest
import asyncio

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from core.config import config
from media.compressor import SmartVideoCompressor, SmartVideoSplitter
from services.media_service import MediaService
from platforms.telegram_adapter import TelegramAdapter
import services.web_panel as wp

class TestV047Upgrade(unittest.TestCase):
    def setUp(self):
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

    def test_01_version_sync(self):
        """بند ۹: انطباق کامل نگارش v0.4.7 در هسته و وب‌پنل"""
        self.assertEqual(config.ENGINE_VERSION, "v0.4.7")
        health = wp.get_system_health()
        self.assertIn("v0.4.7", health["engine_version"])

    def test_02_video_quality_precalculation_and_splitter(self):
        """بند ۱: دستیار هوشمند محاسبه پیش از پردازش و کلاس اسپلیتر"""
        calc_short = SmartVideoCompressor.precalculate_video_quality("dummy.mp4", target_max_mb=49.99)
        self.assertIn("severe_quality_drop", calc_short)
        self.assertIn("recommended_parts", calc_short)
        self.assertIn("estimated_resolution", calc_short)

        # Verify SmartVideoSplitter exists and has split_video method
        self.assertTrue(hasattr(SmartVideoSplitter, "split_video"))

    def test_03_turbo_download_streaming(self):
        """بند ۲: وجود متد دانلود توربو با استریم چندچانکی"""
        self.assertTrue(hasattr(MediaService, "turbo_download_telegram"))
        self.assertTrue(callable(MediaService.turbo_download_telegram))

    def test_04_metadata_switches_defaults(self):
        """بند ۳: سوییچ‌های متادیتا باید به صورت پیش‌فرض خاموش (False) باشند"""
        self.assertFalse(config.APPLY_DEFAULT_ARTIST_TAG)
        self.assertFalse(config.AUTO_RENAME_FILE_TO_TITLE)

    def test_05_studio_reorganization_and_collapsed_accordions(self):
        """بند ۴: ساماندهی استودیو رسانه و بسته بودن آکاردئون‌ها به صورت پیش‌فرض"""
        html = wp.render_dashboard_html()

        # Web Mp3tag Studio must appear before Cross-Platform URL Dispatcher in tab-studio
        mp3tag_pos = html.find("استودیوی پیشرفته متادیتا و رسانه (Web Mp3tag Studio)")
        disp_pos = html.find("دانلود استریم از لینک مستقیم و دیسپچ بین پلتفرم‌ها")
        svg_pos = html.find("استودیوی وکتور SVG (SVG Studio Suite)")

        self.assertNotEqual(mp3tag_pos, -1, "Web Mp3tag Studio should be present")
        self.assertNotEqual(disp_pos, -1, "URL Dispatcher should be present")
        self.assertNotEqual(svg_pos, -1, "SVG Studio should be present")

        # Order must be: Mp3tag Studio -> URL Dispatcher -> SVG Studio
        self.assertLess(mp3tag_pos, disp_pos, "Mp3tag Studio must appear before URL Dispatcher")
        self.assertLess(disp_pos, svg_pos, "SVG Studio must be moved after URL Dispatcher")

        # Fast Metadata Settings checkboxes must be present
        self.assertIn("cfg_studio_auto_artist", html)
        self.assertIn("cfg_studio_auto_title", html)

        # All details tags must NOT have 'open' attribute
        tab_studio_sub = html[html.find('id="tab-studio"'):html.find('id="tab-courses"')]
        self.assertNotIn('<details class="settings-accordion glass rounded-2xl overflow-hidden mb-4" open>', tab_studio_sub)

    def test_06_sidebar_drag_and_drop_unblocked(self):
        """بند ۵: احیای پایدار درگ‌وان‌دراپ سایدبار بدون تایمر ۴۰۰ میلی‌ثانیه‌ای مسدودکننده کلیک"""
        html = wp.render_dashboard_html()
        # Verify 400ms hold timer is removed from desktop mouse
        self.assertNotIn("mouseHoldTimer = setTimeout", html)
        self.assertIn("setupDragForContainer", html)
        self.assertIn("persistTabsOrder", html)

    def test_07_mobile_bottom_navigation(self):
        """بند ۶: نوار ناوبری پایین صفحه موبایل با دکمه برجسته مرکزی محصولات"""
        html = wp.render_dashboard_html()
        self.assertIn('id="mobileBottomNav"', html)
        self.assertIn("pb-24 md:pb-8", html)

        # Verify bottom nav contains courses button
        self.assertIn('data-tab="courses"', html)
        self.assertIn("محصولات", html)

    def test_08_batch_forwarding_manager(self):
        """بند ۷: ثبات و صف ارسال گروهی رسانه‌ها در تلگرام"""
        adapter = TelegramAdapter()
        self.assertTrue(hasattr(adapter, "_media_batch_queue"))
        self.assertTrue(hasattr(adapter, "_batch_registry"))

    def test_09_ffmpeg_in_place_prevention(self):
        """بند ۸: تفکیک مسیر فایل موقت در تبدیل ویدیو به صوت جهت مهار خطای FFmpeg In-Place"""
        with open("services/media_service.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("extract_{v_path.stem}_", code)
        self.assertIn("shutil.move(str(temp_extract), str(target_out))", code)

if __name__ == "__main__":
    unittest.main()
