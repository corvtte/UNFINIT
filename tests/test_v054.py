# -*- coding: utf-8 -*-
import unittest
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pathlib import Path
from bs4 import BeautifulSoup

from core.config import config
from services.web_panel import render_dashboard_html
from platforms.bale_adapter import get_bale_customer_keyboard
from platforms.telegram_adapter import get_customer_keyboard
from media.compressor import SmartVideoCompressor
from core.sign_service import SignService
from services.feed_scraper import _extract_articles_from_html

class TestV054(unittest.TestCase):
    def test_version_bump(self):
        self.assertEqual(str(config.ENGINE_VERSION), "v0.5.4")

    def test_web_panel_tabs_hierarchy(self):
        html = render_dashboard_html()
        soup = BeautifulSoup(html, "html.parser")
        main_el = soup.find("main")
        self.assertIsNotNone(main_el, "main element not found")

        tab_ids = [
            "tab-dashboard", "tab-studio", "tab-courses", "tab-orders",
            "tab-downloads", "tab-users", "tab-tokens", "tab-settings", "tab-frequencies"
        ]
        for tid in tab_ids:
            el = soup.find(id=tid)
            self.assertIsNotNone(el, f"Tab {tid} not found in DOM")
            self.assertEqual(el.parent.name, "main", f"Tab {tid} is not a direct child of <main>!")

    def test_bale_and_telegram_customer_keyboard_layout(self):
        # Bale keyboard
        bale_kb = get_bale_customer_keyboard()
        b_rows = bale_kb.get("keyboard", [])
        self.assertEqual(len(b_rows), 3, "Bale customer keyboard must have 3 rows")
        self.assertEqual(b_rows[0][0]["text"], "🛍 محصولات آموزشی")
        self.assertEqual(b_rows[1][0]["text"], "🔮 نشانه امروز من")
        self.assertEqual(b_rows[1][1]["text"], "💎 اشتراک پریمیوم")
        self.assertIn("دانلودها", str(b_rows[2][0]["text"]))
        self.assertEqual(b_rows[2][1]["text"], "👤 حساب کاربری")

        # Telegram keyboard
        tg_kb = get_customer_keyboard()
        t_rows = tg_kb.keyboard
        self.assertEqual(len(t_rows), 3, "Telegram customer keyboard must have 3 rows")
        self.assertEqual(t_rows[0][0], "🛍 محصولات آموزشی")
        self.assertEqual(t_rows[1][0], "🔮 نشانه امروز من")
        self.assertEqual(t_rows[1][1], "💎 اشتراک پریمیوم")
        self.assertIn("دانلودها", str(t_rows[2][0]))
        self.assertEqual(t_rows[2][1], "👤 حساب کاربری")

    def test_video_under_45mb_precalculate(self):
        # Create a dummy small file under 45MB
        dummy_file = Path("data/dummy_test_video.mp4")
        dummy_file.write_bytes(b"\x00" * (1024 * 1024 * 5)) # 5MB
        try:
            res = SmartVideoCompressor.precalculate_video_quality(dummy_file, target_max_mb=45.0)
            self.assertFalse(res.get("severe_quality_drop"), "Files under 45MB must not drop quality")
            self.assertEqual(res.get("recommended_parts"), 1)
        finally:
            if dummy_file.exists():
                dummy_file.unlink()

    def test_sign_service_buttons(self):
        sign_mock = {
            "title": "درس توحید و آرامش",
            "audio_url": "https://cdn.example.com/audio.mp3",
            "video_url": "https://cdn.example.com/video.mp4",
            "page_url": "https://abasmanesh.com/fa/lesson-1"
        }
        bale_btns = SignService.build_sign_buttons(sign_mock, platform="bale")
        self.assertIn("inline_keyboard", bale_btns)
        texts = [b["text"] for row in bale_btns["inline_keyboard"] for b in row]
        self.assertTrue(any("صوت" in t for t in texts))
        self.assertTrue(any("ویدیو" in t for t in texts))
        self.assertTrue(any("سایت" in t for t in texts))
        self.assertTrue(any("پریمیوم" in t for t in texts))

    def test_extract_articles_background_image(self):
        sample_html = """
        <div class="article-grid">
            <div class="card">
                <a class="card__media-link" href="/fa/articles/test-article-bg/"></a>
                <div class="card__media" style="background-image: url('https://abasmanesh.com/uploads/bg-cover.webp');"></div>
                <div class="card__body">
                    <a href="/fa/articles/test-article-bg/">مقاله تستی با تصویر پس‌زمینه</a>
                </div>
            </div>
        </div>
        """
        articles = _extract_articles_from_html(sample_html)
        self.assertTrue(len(articles) > 0)
        found = False
        for url, title, cover, tag in articles:
            if "bg-cover.webp" in cover:
                found = True
                break
        self.assertTrue(found, "background-image was not extracted from card style")

if __name__ == "__main__":
    unittest.main()
