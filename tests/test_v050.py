"""
آزمون‌های یکپارچگی مهندسی نگارش v0.5.0
UNFINIT Store Engine Final Stabilization Test Suite
"""

import unittest
from pathlib import Path

from core.config import config
from services.web_panel import get_system_health, render_dashboard_html
from media.compressor import SmartVideoCompressor, SmartVideoSplitter, SmartAudioCompressor


class TestV050Release(unittest.TestCase):

    def test_01_engine_version_sync(self):
        """بررسی همگام‌سازی نگارش v0.5.0 در پیکربندی و وضعیت سلامت"""
        self.assertEqual(str(config.ENGINE_VERSION), "v0.5.0")
        health = get_system_health()
        self.assertIn("v0.5.0", str(health["engine_version"]))

    def test_02_web_panel_dashboard_renders_without_name_error(self):
        """تایید رفع خطای Union و رندر موفق HTML داشبورد وب‌پنل"""
        html = render_dashboard_html()
        self.assertTrue(isinstance(html, str))
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("UNFINIT Store Engine", html)
        self.assertNotIn("Error rendering dashboard", html)

    def test_03_telegram_no_local_shadow_imports(self):
        """بررسی عدم وجود ایمپورت‌های محلی SmartVideoCompressor در متدهای telegram_adapter"""
        tg_path = Path("platforms/telegram_adapter.py")
        self.assertTrue(tg_path.exists())
        content = tg_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        # خط ۴۱ باید ایمپورت گلوبال باشد
        self.assertIn("from media.compressor import SmartVideoCompressor", content)

        # هیچ خط دیگری نباید ایمپورت محلی از SmartVideoCompressor یا SmartAudioCompressor داشته باشد
        for idx, line in enumerate(lines[50:], start=51):
            if "import SmartVideoCompressor" in line or "import SmartAudioCompressor" in line:
                self.fail(f"Found local shadow import at line {idx}: {line}")

    def test_04_compressor_classes_callable(self):
        """بررسی در دسترس بودن متدهای SmartVideoCompressor"""
        self.assertTrue(hasattr(SmartVideoCompressor, "precalculate_video_quality"))
        self.assertTrue(hasattr(SmartVideoCompressor, "compress_if_needed"))
        self.assertTrue(hasattr(SmartVideoSplitter, "split_video"))

    def test_05_agents_and_changelog_v050(self):
        """بررسی مستندات نگارش v0.5.0 و قوانین جدید منشور مهندسی"""
        agents_txt = Path("AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("v0.5.0", agents_txt)
        self.assertIn("قانون ممنوعیت مطلق ایمپورت‌های محلی و سایه‌انداز", agents_txt)
        self.assertIn("python -m py_compile", agents_txt)

        changelog_txt = Path("CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## [v0.5.0]", changelog_txt)


if __name__ == "__main__":
    unittest.main()
