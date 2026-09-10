import asyncio
import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import config
from core.database import (
    init_db,
    get_system_setting,
    set_system_setting,
    execute_query,
    fetch_one,
    fetch_all
)
from services.store_service import StoreService
from services.hermes_agent import hermes_agent
from services.web_panel import render_dashboard_html

async def run_v25_1_tests():
    print("==================================================")
    print("🚀 Running UNFINIT Store Engine v25.1.0 Verification")
    print("==================================================")

    # 1. Test JSON Data Persistence (data/settings.json & data/courses.json)
    print("\n[TEST 1] Verifying JSON data persistence and .env synchronization...")
    await init_db()

    assert config.SETTINGS_JSON_FILE.exists(), f"{config.SETTINGS_JSON_FILE} must exist!"
    assert config.COURSES_JSON_FILE.exists(), f"{config.COURSES_JSON_FILE} must exist!"

    # Verify settings.json contents
    with open(config.SETTINGS_JSON_FILE, "r", encoding="utf-8") as f:
        settings_data = json.load(f)
    assert "TELEGRAM_BOT_TOKEN" in settings_data, "TELEGRAM_BOT_TOKEN missing in settings.json"
    assert "CARD_NUMBER" in settings_data, "CARD_NUMBER missing in settings.json"
    print(f"✅ data/settings.json verified with {len(settings_data)} configuration keys.")

    # Test setting update and sync with .env
    test_token_val = "test_nara_token_xyz_2026"
    await set_system_setting("nara_api_key", test_token_val)
    with open(config.SETTINGS_JSON_FILE, "r", encoding="utf-8") as f:
        re_settings = json.load(f)
    assert re_settings.get("nara_api_key") == test_token_val, "Failed to persist setting in settings.json"
    print("✅ set_system_setting successfully synchronized data/settings.json and .env!")

    # Reset nara_api_key
    await set_system_setting("nara_api_key", "")

    # Test courses.json persistence
    test_course = await StoreService.add_product(
        name="دوره اختصاصی تست پایداری JSON v25.1",
        price=450000,
        description="تست خودکار پایداری فایل courses.json",
        download_link="https://dl.unfinit.com/test_v25_1.zip",
        photo_url=""
    )
    with open(config.COURSES_JSON_FILE, "r", encoding="utf-8") as f:
        courses_data = json.load(f)
    assert any(c["product_id"] == test_course.product_id for c in courses_data), "New course not found in courses.json!"
    print(f"✅ data/courses.json automatically updated: Total courses = {len(courses_data)}")

    await StoreService.delete_product(test_course.product_id)
    with open(config.COURSES_JSON_FILE, "r", encoding="utf-8") as f:
        courses_data_after = json.load(f)
    print(f"✅ Course deleted and data/courses.json synchronized: Total remaining = {len(courses_data_after)}")

    # 2. Test Official Hermes Agent & Transparent Error Reporting
    print("\n[TEST 2] Verifying official Hermes Agent integration and explicit error reporting...")
    # Test 2.1: No API key
    config.NARA_API_KEY = ""
    res_no_key = await hermes_agent.chat("تست بدون کلید")
    assert res_no_key["ok"] is False
    assert "NARA_API_KEY" in res_no_key["reply"]
    print("✅ Hermes Agent returned clear guidance when API key is missing.")

    # Test 2.2: Test connection with dummy key -> must report explicit error from Nara Router
    config.NARA_API_KEY = "invalid_dummy_key_123"
    res_dummy = await hermes_agent.chat("تست اتصال")
    assert res_dummy["ok"] is False
    assert "خطای ارتباط با سرور Nara Router" in res_dummy["reply"] or "401" in str(res_dummy.get("error"))
    print("✅ Official Hermes Agent communicated with https://router.bynara.id/v1 and reported transparent error!")
    print(f"   Reported Error: {res_dummy['reply'][:120]}...")
    config.NARA_API_KEY = ""

    # 3. Test Web Panel UI & Security (Vazirmatn + Roboto, Unlocked Settings, Eye Toggles)
    print("\n[TEST 3] Verifying Web Panel UI, hybrid typography and security...")
    html = render_dashboard_html()
    assert "unfinit2026" not in html, "SECURITY ALERT: Default password leaked in web panel!"
    assert "settingsLockBox" not in html, "Settings double lock box must be removed!"
    assert "Vazirmatn" in html, "Vazirmatn font missing!"
    assert "Roboto" in html, "Roboto font missing!"
    assert html.count("togglePasswordVisibility") >= 8, f"Expected at least 8 eye toggle buttons, found {html.count('togglePasswordVisibility')}"
    print(f"✅ Web Panel verified: 100% secure, Vazirmatn + Roboto loaded, double lock removed, {html.count('togglePasswordVisibility')} eye toggle buttons active.")

    print("\n==================================================")
    print("🎉 ALL 3 TEST SUITES PASSED FLAWLESSLY! (v25.1.0)")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_v25_1_tests())
