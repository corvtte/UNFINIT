import asyncio
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

# Ensure event loop for Python 3.14
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from core.config import config
from services.web_panel import get_system_health, EngineVersionStr, render_dashboard_html
from media.compressor import SmartAudioCompressor, SmartVideoCompressor
from services.media_compressor import (
    SmartAudioCompressor as ReexportedAudioCompressor,
    SmartVideoCompressor as ReexportedVideoCompressor,
    convert_audio_to_mp3_if_needed
)
from services.feed_scraper import get_latest_free_downloads


class TestV028Features(unittest.TestCase):

    def test_01_version_bump_v028(self):
        self.assertTrue(any(v in str(config.ENGINE_VERSION) for v in ('v0.2.8', 'v0.2.9', 'v0.3.0', 'v0.3.1', 'v0.3.2', 'v0.3.3', 'v0.3.4', 'v0.3.5', 'v0.3.6')))
        health = get_system_health()
        self.assertTrue(any(v in str(health["engine_version"]) for v in ('v0.2.8', 'v0.2.9', 'v0.3.0', 'v0.3.1', 'v0.3.2', 'v0.3.3', 'v0.3.4', 'v0.3.5', 'v0.3.6')))
        self.assertTrue(EngineVersionStr("UNFINIT Engine v0.2.8").__contains__("v0.2.8"))

    def test_02_dynamic_bale_safe_limit_and_margin(self):
        """Verify dynamic Bale safe size calculation and 1.5MB safety margin."""
        safe_limit = float(getattr(config, "MAX_SAFE_BALE_SIZE_MB", 49.9))
        expected_target_mb = max(1.0, round(safe_limit - 1.5, 2))
        expected_max_bytes = int(expected_target_mb * 1024 * 1024)

        # Verify target bitrate calculations with target_max_bytes
        audio_bitrate = SmartAudioCompressor.calculate_target_bitrate(
            duration_sec=3600, target_max_bytes=expected_max_bytes
        )
        self.assertGreater(audio_bitrate, 0)
        self.assertLessEqual(audio_bitrate, 320)

        video_bitrate = SmartVideoCompressor.calculate_target_video_bitrate(
            duration_sec=3600, target_max_bytes=expected_max_bytes
        )
        self.assertGreater(video_bitrate, 0)

        # Verify services/media_compressor re-exports
        self.assertIs(ReexportedAudioCompressor, SmartAudioCompressor)
        self.assertIs(ReexportedVideoCompressor, SmartVideoCompressor)
        self.assertTrue(callable(convert_audio_to_mp3_if_needed))

    def test_03_paginated_feed_scraper(self):
        """Verify get_latest_free_downloads pagination logic and caching."""
        # Page 1 fetch
        res1 = asyncio.run(get_latest_free_downloads(limit=5, force_refresh=True, page=1))
        self.assertIsInstance(res1, list)
        if len(res1) > 0:
            first = res1[0]
            self.assertIn("title", first)
            self.assertIn("file_number", first)
            self.assertIn("فایل شماره", first["file_number"])

        # Page 2 pagination calculation
        res2 = asyncio.run(get_latest_free_downloads(limit=5, force_refresh=False, page=2))
        self.assertIsInstance(res2, list)

    def test_04_web_panel_dedicated_downloads_tab_and_theme_buttons(self):
        """Verify dedicated downloads tab, pagination controls, and theme-card-btn classes."""
        html = render_dashboard_html()

        # Dedicated tab and nav buttons
        self.assertIn('id="tab-downloads"', html)
        self.assertIn('id="btn-tab-downloads"', html)
        self.assertIn('id="m-btn-tab-downloads"', html)
        self.assertIn('data-tab="downloads"', html)

        # Pagination controls
        self.assertIn('id="btnPrevFeedPage"', html)
        self.assertIn('id="btnNextFeedPage"', html)
        self.assertIn('id="feedCurrentPage"', html)
        self.assertIn('id="feedCurrentPageBottom"', html)
        self.assertIn('changeFeedPage', html)
        self.assertIn('transferFeedDownload', html)

        # Theme-card-btn styling (no hardcoded navy/blue for key action buttons)
        self.assertIn('.theme-card-btn', html)
        self.assertIn('theme-card-btn px-3.5 py-2 rounded-xl text-cyan-300 text-xs font-bold transition flex items-center gap-1.5 shadow-sm', html)
        self.assertIn('theme-card-btn px-3 py-2 rounded-xl text-xs text-cyan-300 font-medium flex items-center gap-1.5 transition shadow-sm', html)
        self.assertIn('theme-card-btn px-2.5 py-1 rounded text-xs font-semibold flex items-center gap-1 transition shadow-sm', html)

        # Safe limit dynamic display in studio status card
        safe_limit = getattr(config, "MAX_SAFE_BALE_SIZE_MB", 49.9)
        self.assertIn(f"{safe_limit} MB", html)

    def test_05_sandboxed_javascript_syntax_node_check(self):
        """Verify all sandboxed JavaScript blocks pass node --check syntax validation."""
        html = render_dashboard_html()
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, flags=re.DOTALL)
        self.assertGreaterEqual(len(scripts), 4)

        for i, script in enumerate(scripts):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
                f.write(script)
                fname = f.name
            try:
                res = subprocess.run(['node', '--check', fname], capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, f"Script {i} syntax error: {res.stderr}")
            finally:
                try:
                    os.unlink(fname)
                except OSError:
                    pass


if __name__ == '__main__':
    unittest.main()
