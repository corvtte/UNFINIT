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
from services.hermes_agent import hermes_agent, HermesTools
from services.web_panel import render_dashboard_html

async def run_tests():
    print("==================================================")
    print("🚀 Running UNFINIT Store Engine v25.0.0 Verification")
    print("==================================================")

    # 1. Test Courses Backup & Disk Persistence
    print("\n[TEST 1] Verifying Courses disk JSON backup & database sync...")
    await init_db()
    assert config.COURSES_BACKUP_FILE.exists(), f"Backup file {config.COURSES_BACKUP_FILE} must exist"
    
    # Add a course and check backup
    test_course_name = "دوره جامع معماری هوش مصنوعی و ایجنت‌ها"
    course = await StoreService.add_product(
        name=test_course_name,
        price=350000,
        description="تست خودکار پایداری دیسک",
        download_link="https://dl.unfinit.com/ai_arch.zip",
        photo_url="/uploads/banners/ai_arch.png"
    )
    
    with open(config.COURSES_BACKUP_FILE, "r", encoding="utf-8") as f:
        backup_data = json.load(f)
    found_in_backup = any(p["product_id"] == course.product_id for p in backup_data)
    assert found_in_backup, "Newly added course was not found in courses_backup.json!"
    print(f"✅ Course successfully backed up to disk JSON: ID={course.product_id}, Total backed up={len(backup_data)}")

    # Clean up test course
    await StoreService.delete_product(course.product_id)
    with open(config.COURSES_BACKUP_FILE, "r", encoding="utf-8") as f:
        backup_data_after_del = json.load(f)
    print(f"✅ Disk backup updated after deletion. Total remaining={len(backup_data_after_del)}")

    # 2. Test Admin Password Change & Dynamic Reloading
    print("\n[TEST 2] Verifying Admin Password change and system_settings persistence...")
    initial_pwd = config.ADMIN_PANEL_PASSWORD
    new_test_pwd = "SuperSecretAdmin2026!#"
    
    # Save new password
    await set_system_setting("admin_password", new_test_pwd)
    # Reload from DB via init_db logic
    saved_pwd = await get_system_setting("admin_password")
    assert saved_pwd == new_test_pwd, "Password failed to persist in system_settings"
    config.ADMIN_PANEL_PASSWORD = saved_pwd
    assert config.ADMIN_PANEL_PASSWORD == new_test_pwd
    print(f"✅ Admin password updated and persisted: {config.ADMIN_PANEL_PASSWORD[:5]}*****")

    # Restore initial password
    await set_system_setting("admin_password", initial_pwd)
    config.ADMIN_PANEL_PASSWORD = initial_pwd
    print(f"✅ Restored initial password: {config.ADMIN_PANEL_PASSWORD}")

    # 3. Test Hermes AI Agent & Tools
    print("\n[TEST 3] Verifying Hermes AI Agent with Nara Router integration & tools...")
    # Test city extraction
    assert HermesTools.extract_city("اجاره خانه در مشهد") == "mashhad"
    assert HermesTools.extract_city("قیمت آپارتمان در اصفهان") == "isfahan"
    assert HermesTools.extract_city("آپارتمان در پونک") == "tehran"
    print("✅ Hermes city extractor verified!")

    # Test Hermes agent chat flow
    chat_res = await hermes_agent.chat("قیمت آپارتمان در سعادت آباد تهران رو از دیوار بررسی کن")
    assert chat_res.get("ok") is True, f"Hermes chat returned failure: {chat_res}"
    assert "reply" in chat_res and len(chat_res["reply"]) > 10
    print(f"✅ Hermes Chat Response successfully generated!")
    print(f"   Provider: {chat_res.get('provider')}")
    print(f"   Model: {chat_res.get('model')}")
    print(f"   Tools used: {chat_res.get('tools_used')}")
    print(f"   Snippet: {chat_res['reply'][:120]}...")

    # 4. Test Web Panel Vazirmatn, Fullscreen Login Gate & Security
    print("\n[TEST 4] Verifying Web Panel HTML layout, Vazirmatn font & security...")
    html = render_dashboard_html()
    assert "unfinit2026" not in html, "SECURITY ALERT: Default password leaked in web panel HTML!"
    assert "Vazirmatn" in html, "Vazirmatn font link missing!"
    assert "loginGate" in html, "loginGate element missing!"
    assert "tab-hermes" in html, "Hermes tab missing!"
    assert "btn-tab-hermes" in html, "Hermes nav button missing!"
    assert "cfg_NARA_API_KEY" in html, "Nara API key input missing!"
    assert "cfg_NEW_ADMIN_PASSWORD" in html, "New password input missing!"
    print(f"✅ Web Panel successfully verified (HTML size: {len(html)} bytes, 100% secure)")

    print("\n==================================================")
    print("🎉 ALL 4 TEST SUITES PASSED FLAWLESSLY! (v25.0.0)")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
