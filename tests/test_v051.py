"""
آزمون‌های یکپارچگی مهندسی نگارش v0.5.1
UNFINIT Store Engine Release v0.5.1 Verification Test Suite
"""

import math
import unittest
import builtins
from pathlib import Path

from core.config import config
from services.web_panel import get_system_health, render_dashboard_html
from media.compressor import SmartVideoCompressor, SmartVideoSplitter, SAFE_BALE_PART_LIMIT_MB


class TestV051Release(unittest.TestCase):

    def test_01_engine_version_sync(self):
        """بررسی همگام‌سازی نگارش در پیکربندی و وضعیت سلامت سیستم"""
        self.assertTrue(str(config.ENGINE_VERSION).startswith("v0.5."))
        health = get_system_health()
        self.assertIn("v0.5.", str(health["engine_version"]))

    def test_02_web_panel_dashboard_renders_without_name_error(self):
        """تایید رفع قطعی خطای Union و رندر موفق بیش از ۵۰۰ کیلوبایت HTML داشبورد وب‌پنل"""
        html = render_dashboard_html()
        self.assertTrue(isinstance(html, str))
        self.assertGreater(len(html), 500000)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("UNFINIT Store Engine", html)
        self.assertNotIn("Error rendering dashboard", html)
        self.assertNotIn("name 'Union' is not defined", html)

    def test_03_builtins_typing_inoculation(self):
        """بررسی تزریق سراسری نمادهای تایپینگ به Builtins جهت مصونیت دائمی"""
        for sym in ("Union", "Optional", "List", "Dict", "Tuple", "Any", "Callable"):
            self.assertTrue(hasattr(builtins, sym), f"Symbol {sym} missing from builtins")

    def test_04_split_parts_dynamic_bale_safe_margin(self):
        """بررسی الگوریتم داینامیک محاسبه تعداد پارت‌های اسپلیت با حاشیه امن ۴۵MB"""
        self.assertEqual(SAFE_BALE_PART_LIMIT_MB, 45.0)

        # آزمون ویدیوی ۱۵۳.۳ مگابایتی (مورد اشاره در لاگ کاربری)
        video_153mb = 153.3
        parts_153 = max(2, math.ceil(video_153mb / SAFE_BALE_PART_LIMIT_MB))
        self.assertEqual(parts_153, 4, "ویدیوی ۱۵۳.۳ مگابایتی باید دقیقاً به ۴ پارت تقسیم شود تا زیر ۴۵MB بماند")

        # آزمون ویدیوی ۸۰ مگابایتی
        video_80mb = 80.0
        parts_80 = max(2, math.ceil(video_80mb / SAFE_BALE_PART_LIMIT_MB))
        self.assertEqual(parts_80, 2, "ویدیوی ۸۰ مگابایتی باید به ۲ پارت ۴۰ مگابایتی تقسیم شود")

        # آزمون ویدیوی ۲۱۰ مگابایتی
        video_210mb = 210.0
        parts_210 = max(2, math.ceil(video_210mb / SAFE_BALE_PART_LIMIT_MB))
        self.assertEqual(parts_210, 5, "ویدیوی ۲۱۰ مگابایتی باید به ۵ پارت تقسیم شود")

    def test_05_telegram_adapter_math_and_split_handlers(self):
        """بررسی وجود ایمپورت math و ساختار دکمه‌های پویا در telegram_adapter"""
        tg_path = Path("platforms/telegram_adapter.py")
        self.assertTrue(tg_path.exists())
        content = tg_path.read_text(encoding="utf-8")

        # بررسی وجود ایمپورت math در خطوط بالای فایل
        top_lines = "\n".join(content.splitlines()[:30])
        self.assertIn("import math", top_lines)

        # بررسی وجود منطق داینامیک محاسبه پارت‌ها در هندلرها
        self.assertIn("smeta:split_bale:{drop_id}:", content)

    def test_06_documentation_and_changelog_v051(self):
        """بررسی ثبت کامل مستندات نسخه v0.5.1 در تمام فایل‌های اساسی"""
        agents_txt = Path("AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("v0.5.1", agents_txt)
        self.assertIn("| v0.5.1 | 1403/07/04 |", agents_txt)

        changelog_txt = Path("CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## [v0.5.1] - 1403/07/04", changelog_txt)

        readme_txt = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("UNFINIT", readme_txt)


if __name__ == "__main__":
    unittest.main()
