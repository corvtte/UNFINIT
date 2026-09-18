import unittest
import json
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from core.config import config
from core.database import init_db, get_system_setting, set_system_setting
from services.web_panel import render_dashboard_html, get_system_health
from services.store_service import StoreService, ProductItem
from services.referral_service import ReferralService

class TestV036Features(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(init_db())
        loop.close()

    def test_01_version_and_health(self):
        """Rule 1.1 / v0.3.6: Verify clean ENGINE_VERSION and system health."""
        self.assertEqual(str(config.ENGINE_VERSION), "v0.3.6")
        self.assertEqual(config.ENGINE_VERSION.clean, "v0.3.6")
        health = get_system_health()
        self.assertIn("v0.3.6", str(health.get("engine_version", "")))

    def test_02_collapsible_right_sidebar_and_wrapper(self):
        """Web Panel: Collapsible right sidebar layout and header toggle button."""
        dash = render_dashboard_html()
        self.assertIn('id="mainSidebar"', dash)
        self.assertIn('right-0', dash)
        self.assertIn('border-l', dash)
        self.assertIn('id="contentWrapper"', dash)
        self.assertIn('md:mr-64', dash)
        self.assertIn('id="btnToggleSidebar"', dash)
        self.assertIn('toggleSidebar', dash)
        self.assertIn('unfinit_sidebar_collapsed', dash)

    def test_03_theme_cloud_sync_and_persistence(self):
        """Theme Sync: Server-side injection and CSS classes."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(set_system_setting("THEME", "synthwave"))
        loop.close()
        dash = render_dashboard_html()
        self.assertIn('id="themeSwitcherSelect"', dash)
        self.assertIn('--table-head-bg', dash)
        self.assertIn('--table-row-hover', dash)
        self.assertIn('/api/settings/theme', dash)

    def test_04_sidebar_drag_drop_reorder(self):
        """Sidebar: Drag and drop ordering and 500ms long-press logic."""
        dash = render_dashboard_html()
        self.assertIn('id="sidebarNavList"', dash)
        self.assertIn('unfinit_nav_order', dash)
        self.assertIn('unfinit_tabs_order', dash)
        self.assertIn('touchTimer', dash)
        self.assertIn('500', dash)

    def test_05_media_studio_accordions(self):
        """Media Studio: Accordion collapse tools."""
        dash = render_dashboard_html()
        self.assertIn('details class="settings-accordion', dash)
        self.assertIn('handleDispatch', dash)
        self.assertIn('svgConvertForm', dash)
        self.assertIn('studioDropzone', dash)

    def test_06_multi_file_course_delivery_engine(self):
        """Store and Course Delivery: delivery_type and files_package fields."""
        pkg_files = [
            {"title": "جلسه ۱ - معرفی", "file_name": "lesson1.mp3", "duration": 600},
            {"title": "جلسه ۲ - مبانی", "file_name": "lesson2.mp3", "duration": 1200}
        ]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            prod = loop.run_until_complete(StoreService.add_product(
                name="دوره تستی پکیج چندفایله",
                price=0,
                delivery_type="files_package",
                files_package=pkg_files
            ))
            self.assertIsNotNone(prod)
            self.assertEqual(prod.delivery_type, "files_package")
            self.assertIsInstance(prod.files_package, list)
            self.assertEqual(len(prod.files_package), 2)
            self.assertEqual(prod.files_package[0]["title"], "جلسه ۱ - معرفی")

            mock_adapter = MagicMock()
            mock_adapter.send_audio = AsyncMock(return_value={"message_id": 1, "audio": {"file_id": "tg_f1"}})
            with patch("services.web_panel.ACTIVE_TG_ADAPTER", mock_adapter):
                res = loop.run_until_complete(StoreService.deliver_course_package(prod, 123456, "telegram"))
                self.assertIn("sent_count", res)
            if prod:
                loop.run_until_complete(StoreService.delete_product(prod.product_id))
        finally:
            loop.close()

    def test_07_course_modals_contain_package_inputs(self):
        """Web Panel: Add and Edit course forms contain delivery_type and files_package."""
        dash = render_dashboard_html()
        self.assertIn('id="newCDeliveryType"', dash)
        self.assertIn('id="newCFilesPackage"', dash)
        self.assertIn('id="editDeliveryType"', dash)
        self.assertIn('id="editFilesPackage"', dash)
        self.assertIn('togglePackageInput', dash)

if __name__ == "__main__":
    unittest.main()
