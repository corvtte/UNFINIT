# -*- coding: utf-8 -*-
"""
آزمون‌های اعتبارسنجی نگارش v0.4.1 موتور UNFINIT Store Engine:
۱. همگام‌سازی سراسری شماره نسخه v0.4.1 (کانفیگ، وضعیت سلامت، داشبورد و استورفرانت)
۲. عملکرد ماژول فرکانس فراوانی و متد update_item جهت ویرایش عبارات
۳. مودال ویرایش فرکانس (#modalEditFrequency) و توابع جاوااسکریپت آن در وب‌پنل
۴. تثبیت قطعی و همیشگی جایگاه تب داشبورد در ایندکس ۰ سایدبار
۵. اتصال استایل‌های رنگ متن صلب به متغیرهای CSS تم و تصحیح فونت کارت سلامت
۶. کلیدهای انتقال فایل به سروش‌پلاس در تلگرام، بله و وب‌پنل و صف محلی soroush_queue
۷. رعایت قانون مستندسازی و داک‌استرینگ‌های فارسی در ماژول‌ها طبق بند ۵.۵ در AGENTS.md
"""

import json
import os
import unittest
import asyncio
from pathlib import Path

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from core.config import config
from services.web_panel import get_system_health, render_dashboard_html, render_storefront_html
from core.frequency_service import FrequencyService
from platforms.bale_adapter import build_bale_media_keyboard
from platforms.soroush_worker import soroush_worker


class TestVersion041Features(unittest.TestCase):
    def setUp(self):
        self.freq_file = Path("data/frequencies.json")

    def test_01_version_v041_sync(self):
        """اعتبارسنجی نسخه v0.4.1 و بالاتر در تمام بخش‌های اصلی سیستم."""
        self.assertTrue(str(config.ENGINE_VERSION) >= "v0.4.1")
        health = get_system_health()
        self.assertTrue("v0.4." in health["engine_version"])

        dash_html = render_dashboard_html()
        self.assertTrue("v0.4." in dash_html)

        store_html = render_storefront_html()
        self.assertTrue("v0.4." in store_html)

    def test_02_frequency_service_update_item(self):
        """اعتبارسنجی متد update_item در FrequencyService جهت ویرایش عبارات."""
        items = FrequencyService.get_all()
        self.assertTrue(len(items) > 0)
        target = items[0]
        original_title = target.get("title", "")
        original_text = target.get("text", "")
        original_cat = target.get("category", "MORNING")

        # آزمون ویرایش
        updated = FrequencyService.update_item(
            item_id=target["id"],
            title=original_title + " [تست]",
            text=original_text + " [آزمون ویرایش]",
            category="NIGHT" if original_cat == "MORNING" else "MORNING"
        )
        self.assertIsNotNone(updated)
        self.assertIn("[تست]", updated["title"])

        # بازگردانی به حالت اولیه
        restored = FrequencyService.update_item(
            item_id=target["id"],
            title=original_title,
            text=original_text,
            category=original_cat
        )
        self.assertEqual(restored["title"], original_title)

    def test_03_frequency_edit_modal_in_web_panel(self):
        """اعتبارسنجی وجود مودال ویرایش فرکانس و توابع کلاینت در وب‌پنل."""
        html = render_dashboard_html()
        self.assertIn('id="modalEditFrequency"', html)
        self.assertIn('id="freqEditId"', html)
        self.assertIn('id="freqEditCategory"', html)
        self.assertIn('id="freqEditTitle"', html)
        self.assertIn('id="freqEditText"', html)
        self.assertIn('openEditFrequencyModal', html)
        self.assertIn('closeEditFrequencyModal', html)
        self.assertIn('submitEditFrequency', html)
        self.assertIn('window.openEditFrequencyModal', html)

    def test_04_dashboard_tab_pinned_at_index_zero(self):
        """اعتبارسنجی قفل ماندن تب داشبورد در ایندکس صفر سایدبار."""
        html = render_dashboard_html()
        # بررسی منطق جاوااسکریپت برای چیدمان تب‌ها در وب‌پنل
        self.assertIn("['dashboard', ...currentOrder.filter(t => t !== 'dashboard')]", html)
        self.assertIn("['dashboard', ...savedOrder.filter(t => t !== 'dashboard')]", html)

    def test_05_text_color_css_overrides_and_health_card(self):
        """اعتبارسنجی بازنویسی رنگ‌های متن با متغیرهای تم و اصلاح فونت کارت سلامت."""
        html = render_dashboard_html()
        self.assertIn('var(--text-muted', html)
        self.assertIn('var(--text-main', html)
        self.assertIn('.metric-val-health', html)
        self.assertIn("font-family: 'Vazirmatn'", html)

    def test_06_soroush_dispatch_buttons_and_queue(self):
        """اعتبارسنجی دکمه‌های ارسال به سروش‌پلاس در بله، تلگرام و وب‌پنل."""
        # بررسی کیبورد بله
        bale_kb = build_bale_media_keyboard("test_drop_123", {"media_type": "audio"})
        bale_kb_text = json.dumps(bale_kb, ensure_ascii=False)
        self.assertIn("bmeta:send_splus:test_drop_123", bale_kb_text)
        self.assertIn("انتقال به سروش‌پلاس", bale_kb_text)

        # بررسی در وب‌پنل سورس کد
        with open("services/web_panel.py", "r", encoding="utf-8") as f:
            wp_code = f.read()
        self.assertIn("dispatchDrop('{d['drop_id']}', 'soroush')", wp_code)
        self.assertIn("soroush: 'سروش‌پلاس'", wp_code)
        self.assertIn('elif target in ("soroush", "splus"):', wp_code)

        # بررسی در تلگرام سورس کد
        with open("platforms/telegram_adapter.py", "r", encoding="utf-8") as f:
            tg_code = f.read()
        self.assertIn("smeta:send_splus:{drop_id}", tg_code)
        self.assertIn('elif action == "send_splus":', tg_code)

        # بررسی وجود دایرکتوری صف باینری امن در صورت بروز خطای ۴۰۴
        queue_dir = Path("data/soroush_queue")
        self.assertTrue(queue_dir.exists())

    def test_07_persian_docstrings_presence(self):
        """اعتبارسنجی رعایت قانون بند ۵.۵ در AGENTS.md برای مستندسازی فارسی."""
        with open("core/frequency_service.py", "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("ویرایش و به‌روزرسانی کامل یک کارت فرکانس فراوانی در دیتابیس JSON.", content)

        with open("platforms/soroush_worker.py", "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("ارسال امن فایل رسانه‌ای به بخش پیام‌های ذخیره‌شده (Saved Messages) حساب سروش‌پلاس.", content)


if __name__ == "__main__":
    unittest.main()
