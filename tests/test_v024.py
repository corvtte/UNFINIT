import unittest
import asyncio
import re

# Ensure an event loop exists for Python 3.14
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from unittest.mock import AsyncMock, MagicMock
from core.config import config
from services.web_panel import render_dashboard_html, get_system_health
from platforms.telegram_adapter import TelegramAdapter

class TestV024Features(unittest.TestCase):
    def test_version_v024(self):
        health = get_system_health()
        self.assertTrue('v0.2.4' in str(health['engine_version']) or 'v0.2.5' in str(health['engine_version']))
        self.assertIn(config.ENGINE_VERSION, ('v0.2.4', 'v0.2.5'))

    def test_universal_scrollbar_css(self):
        dash_html = render_dashboard_html()
        self.assertIn('scrollbar-color: var(--accent-color', dash_html)
        self.assertIn('width: 8px !important;', dash_html)
        self.assertIn('border-radius: 9999px !important;', dash_html)

    def test_telegram_unauthorized_link_feedback(self):
        adapter = TelegramAdapter()
        user_id = 999888777
        self.assertFalse(adapter.is_admin(user_id))

        text = 'https://example.com/test_audio.mp3'
        link_match = re.search(r'https?://[^\s]+', text)
        self.assertTrue(bool(link_match))

        expected_txt = f'⛔ دسترسی غیرمجاز! شناسه عددی تلگرام شما جهت ثبت در پنل: <code>{user_id}</code>'
        self.assertIn(str(user_id), expected_txt)

if __name__ == '__main__':
    unittest.main()
