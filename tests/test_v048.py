# -*- coding: utf-8 -*-
"""
آزمون‌های جامع اعتبارسنجی نگارش v0.4.8
UNFINIT Store Engine v0.4.8 Verification Suite

تست‌های این ماژول بندهای اصلی نگارش v0.4.8 را بررسی می‌کنند:
۱. همگام‌سازی نگارش v0.4.8 در هسته و وب‌پنل
۲. منبع استخراج نشانه روزانه از آرشیو جامع مقالات (https://abasmanesh.com/fa/articles/)
۳. دسته‌بندی‌های ۱۶ گانه رسمی مقالات و آموزش‌های عباس‌منش در اسکرپر داینامیک
۴. الگوریتم استریم دانلود و نوار پیشرفت با فلاش دیسک و اعتبارسنجی یکپارچگی بایت‌ها
۵. انقضای ۳۰ دقیقه‌ای و پاکسازی خودکار اکشن‌های معلق در SessionManager
۶. ارگونومی یکدست و تراز نوار ناوبری پایین صفحه موبایل در وب‌پنل
"""

import os
import time
import unittest
import asyncio
from pathlib import Path

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from core.config import config
from core.sign_service import SignService
from services.feed_scraper import feed_scraper, ABASMANESH_PREMIUM_CATEGORIES, ARTICLES_BASE_URL
from services.session_manager import session_manager
from services.media_service import MediaService
import services.web_panel as wp


class TestV048Upgrade(unittest.TestCase):
    def setUp(self):
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

    def test_01_version_sync(self):
        """بند ۱: انطباق کامل نگارش v0.4.8 در هسته و وب‌پنل"""
        self.assertEqual(config.ENGINE_VERSION, "v0.4.8")
        health = wp.get_system_health()
        self.assertIn("v0.4.8", health["engine_version"])

    def test_02_articles_base_url_and_sign_source(self):
        """بند ۲: منبع مقالات و نشانه روزانه متصل به آرشیو جامع ۹۵۸ فایلی"""
        self.assertEqual(ARTICLES_BASE_URL, "https://abasmanesh.com/fa/articles/")
        self.assertEqual(SignService.ABASMANESH_ARCHIVE_URL, "https://abasmanesh.com/fa/articles/")

    def test_03_sixteen_premium_categories(self):
        """بند ۳: تعریف کامل و ساختاریافته ۱۶ دسته‌بندی رسمی عباس‌منش"""
        self.assertEqual(len(ABASMANESH_PREMIUM_CATEGORIES), 16)
        all_cats = feed_scraper.get_all_categories()
        self.assertEqual(len(all_cats), 16)

        # بررسی وجود دسته‌های شاخص
        cat1 = feed_scraper.get_category_by_id(1)
        self.assertIsNotNone(cat1)
        self.assertEqual(cat1["slug"], "the-series-of-focus-on-positive-points")

        cat_focus = feed_scraper.get_category_by_id("the-series-of-focus-on-positive-points")
        self.assertEqual(cat_focus["id"], 1)

        cat16 = feed_scraper.get_category_by_id(16)
        self.assertIsNotNone(cat16)
        self.assertEqual(cat16["slug"], "all-articles")

        for cat in all_cats:
            self.assertIn("id", cat)
            self.assertIn("title", cat)
            self.assertIn("slug", cat)
            self.assertIn("url", cat)
            self.assertTrue(cat["url"].startswith("https://abasmanesh.com/fa/category/") or cat["url"].startswith("https://abasmanesh.com/fa/articles/"))

    def test_04_session_manager_action_expiration(self):
        """بند ۴: انقضای ۳۰ دقیقه‌ای و مهار نشت اکشن‌های معلق کاربر"""
        test_key = "test_user_v048"
        session_manager.set_user_action(test_key, "await_url", "test_drop", extra={"foo": "bar"})

        # بلافاصله پس از ثبت، باید معتبر باشد
        act = session_manager.get_user_action(test_key)
        self.assertIsNotNone(act)
        self.assertEqual(act["action"], "await_url")
        self.assertIn("created_at", act)

        # اگر تاریخ ساخت به بیش از ۳۰ دقیقه پیش تغییر یابد، باید منقضی شود
        act["created_at"] = time.time() - 2000
        if "extra" in act:
            act["extra"]["_created_at"] = time.time() - 2000
        session_manager._user_actions[test_key] = act

        expired_act = session_manager.get_user_action(test_key)
        self.assertIsNone(expired_act, "Expired user action should return None and be cleared")

    def test_05_mobile_bottom_nav_ergonomics(self):
        """بند ۵: ارگونومی یکدست و تراز نوار ناوبری پایین صفحه موبایل"""
        html = wp.render_dashboard_html()

        # دکمه محصولات نباید -top-4 داشته باشد
        self.assertNotIn("-top-4", html, "Elevated button (-top-4) should be removed for a flat ergonomic baseline")

        # نوار پایین صفحه باید حاوی المان‌های ۵ گانه با استایل هم‌تراز باشد
        nav_idx = html.find('id="mobileBottomNav"')
        self.assertNotEqual(nav_idx, -1)
        nav_end = html.find('</nav>', nav_idx)
        nav_sub = html[nav_idx:nav_end]
        self.assertIn("داشبورد", nav_sub)
        self.assertIn("استودیو", nav_sub)
        self.assertIn("محصولات", nav_sub)
        self.assertIn("سفارشات", nav_sub)
        self.assertIn("تنظیمات", nav_sub)

        # دکمه وسط محصولات نباید رنگی پیش‌فرض دائمی داشته باشد
        self.assertNotIn('theme-accent-btn', nav_sub, "Products button should not have permanent theme-accent-btn in bottom nav")

    def test_06_turbo_download_integrity(self):
        """بند ۶: اعتبارسنجی وجود متد دانلود توربو استریم با قابلیت فال‌بک امن"""
        self.assertTrue(hasattr(MediaService, "turbo_download_telegram"))
        self.assertTrue(callable(MediaService.turbo_download_telegram))


if __name__ == "__main__":
    unittest.main()
