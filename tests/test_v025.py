import unittest
import asyncio
import os
import re
from pathlib import Path

try:
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from core.config import config
from services.web_panel import render_dashboard_html, get_system_health
from services.url_service import UrlService
from platforms.telegram_adapter import TelegramAdapter

class TestV025Features(unittest.TestCase):
    def test_01_version_v025(self):
        health = get_system_health()
        self.assertTrue('v0.2.5' in str(health['engine_version']) or 'v0.2.6' in str(health['engine_version']))
        self.assertIn(config.ENGINE_VERSION, ('v0.2.5', 'v0.2.6'))

    def test_02_probe_url_error_and_user_agent(self):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        probe_res = loop.run_until_complete(UrlService.probe_url('https://invalid-non-existent-domain-12345.xyz/audio.mp3'))
        self.assertFalse(probe_res['is_valid'])
        self.assertIn('سرور مبدا اجازه دسترسی به این فایل را نداد یا لینک نامعتبر است', probe_res['error'])

    def test_03_universal_scrollbar_css_and_instant_theming(self):
        dash_html = render_dashboard_html()
        self.assertIn('scrollbar-color: var(--accent-color, #a855f7) transparent !important;', dash_html)
        self.assertIn('::-webkit-scrollbar { width: 8px !important; height: 8px !important; }', dash_html)
        self.assertIn('::-webkit-scrollbar-thumb { background: var(--accent-color, #a855f7) !important; border-radius: 9999px !important; }', dash_html)
        self.assertIn("document.documentElement.style.setProperty('--accent-color', currentThemeAccent);", dash_html)
        self.assertIn('window.changeTheme = applyAntigravityTheme;', dash_html)

    def test_04_zarinpal_purged_from_settings(self):
        dash_html = render_dashboard_html()
        self.assertNotIn('cfg_ZARINPAL_MERCHANT_ID', dash_html)
        self.assertNotIn('cfg_ZARINPAL_SANDBOX', dash_html)

    def test_05_admin_ids_consolidated_in_secrets_tab(self):
        dash_html = render_dashboard_html()
        self.assertIn('id="cfg_TELEGRAM_OWNER_ID"', dash_html)
        self.assertIn('id="cfg_BALE_OWNER_ID"', dash_html)
        self.assertIn('id="cfg_RUBIKA_OWNER_ID"', dash_html)
        self.assertIn('id="cfg_TELEGRAM_FORUM_GROUP_ID"', dash_html)
        self.assertIn('id="cfg_ADMIN_USER_IDS"', dash_html)

    def test_06_custom_logo_uploader(self):
        dash_html = render_dashboard_html()
        self.assertIn('id="panelLogoPreview"', dash_html)
        self.assertIn('id="logoFileInput"', dash_html)
        self.assertIn('id="btnUploadLogo"', dash_html)
        self.assertIn('uploadCustomLogo', dash_html)
        self.assertIn('/static/logo.png?t=', dash_html)
        self.assertTrue(config.ASSETS_DIR.exists())

if __name__ == '__main__':
    unittest.main()
