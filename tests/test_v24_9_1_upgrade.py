import asyncio
import os
os.environ["TESTING"] = "true"
import sys
import json
import base64
import urllib.parse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import config
from core.database import (
    init_db,
    get_system_setting,
    set_system_setting,
    db_get_media_session,
    db_save_media_session
)
from services.session_manager import session_manager
from services.store_service import StoreService

async def run_tests():
    print("==================================================")
    print("🚀 Running UNFINIT Store Engine v24.9.1 Verification")
    print("==================================================")

    # 1. Test SQLite Session Persistence across simulated restarts
    print("\n[TEST 1] Verifying SQLite session persistence & cache reload...")
    await init_db()
    test_drop_id = "drop_test_v24_9_1_persist"
    dummy_session_data = {
        "audio_filename": "lesson_persisted.mp3",
        "working_path": str(config.TEMP_DIR / "lesson_persisted.mp3"),
        "media_type": "audio",
        "file_size": 1024,
        "is_downloaded_locally": True
    }
    # Create session
    session_manager.create_session(test_drop_id, dummy_session_data)
    
    # Simulate server crash/restart by wiping in-memory dictionary
    session_manager._sessions.clear()
    assert test_drop_id not in session_manager._sessions, "Memory cache should be empty"

    # Fetch through session_manager (should read-through from SQLite)
    restored_session = session_manager.get_session(test_drop_id)
    assert restored_session is not None, "Failed to restore session from SQLite!"
    assert restored_session["audio_filename"] == "lesson_persisted.mp3"
    print(f"✅ Session successfully restored from SQLite disk: {restored_session['audio_filename']}")

    # Test update and disk reload
    session_manager.update_session(test_drop_id, {"status": "transcoded"})
    session_manager._sessions.clear()
    restored_after_update = session_manager.get_session(test_drop_id)
    assert restored_after_update["status"] == "transcoded"
    print("✅ Session updates successfully persisted to SQLite disk!")

    # 2. Test System Settings Storage
    print("\n[TEST 2] Verifying System Settings persistence...")
    orig_token = await get_system_setting("bale_payment_token")
    orig_card = await get_system_setting("CARD_NUMBER")
    orig_channel = await get_system_setting("tg_fjoin_channel")

    test_token = "bale_pay_token_test_isolation_val"
    test_card = "5022291099998888"
    test_channel = "@test_isolation_channel"

    try:
        await set_system_setting("bale_payment_token", test_token)
        await set_system_setting("CARD_NUMBER", test_card)
        await set_system_setting("tg_fjoin_channel", test_channel)

        read_token = await get_system_setting("bale_payment_token")
        read_card = await get_system_setting("CARD_NUMBER")
        read_channel = await get_system_setting("tg_fjoin_channel")

        assert read_token == test_token
        assert read_card == test_card
        assert read_channel == test_channel
        print(f"✅ System settings successfully verified in database: Card={read_card}, Token={read_token[:12]}...")
    finally:
        await set_system_setting("bale_payment_token", orig_token)
        await set_system_setting("CARD_NUMBER", orig_card)
        await set_system_setting("tg_fjoin_channel", orig_channel)

    # 3. Test Banner Upload & Course Creation with Payment Checkboxes
    print("\n[TEST 3] Verifying Banner Upload & Course Payment Flags...")
    # Tiny 1x1 transparent PNG image (68 bytes)
    tiny_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    raw_img = base64.b64decode(tiny_png_b64)
    banner_fname = "test_banner_v24_9_1.png"
    banner_path = config.BANNERS_DIR / banner_fname
    with open(banner_path, "wb") as f:
        f.write(raw_img)
    assert banner_path.exists()
    assert banner_path.stat().st_size == len(raw_img)
    print(f"✅ Banner image saved to uploads/banners: {banner_path.name} ({len(raw_img)} bytes)")

    # Course creation
    banner_url = f"/uploads/banners/{banner_fname}"
    course = await StoreService.add_product(
        name="دوره تخصصی هوش مصنوعی و رباتیک",
        price=250000,
        description="توضیحات کامل دوره آموزشی",
        download_link="https://dl.unfinit.com/ai_robotics.zip",
        photo_url=banner_url,
        allow_card=True,
        allow_bale=True
    )
    assert course.allow_card is True
    assert course.allow_bale is True
    assert course.photo_url == banner_url

    # Update course payment flags
    await StoreService.update_product_field(course.product_id, "allow_bale", 0)
    updated_course = await StoreService.get_product(course.product_id)
    assert updated_course.allow_bale is False
    assert updated_course.allow_card is True
    print(f"✅ Course created & payment flags verified: ID={course.product_id}, AllowCard={updated_course.allow_card}, AllowBale={updated_course.allow_bale}")

    # 4. Test Direct Download Logic (/dl/<drop_id>)
    print("\n[TEST 4] Verifying Direct Browser Download (/dl/<drop_id>) logic...")
    dl_test_file = config.TEMP_DIR / "test_download_media.mp3"
    test_content = b"ID3\x03\x00\x00\x00\x00\x00#DUMMY_MP3_PAYLOAD_FOR_BROWSER_DOWNLOAD_TEST#"
    with open(dl_test_file, "wb") as f:
        f.write(test_content)

    dl_drop_id = "drop_dl_direct_test"
    session_manager.create_session(dl_drop_id, {
        "audio_filename": "final_song.mp3",
        "working_path": str(dl_test_file),
        "media_type": "audio",
        "file_size": len(test_content),
        "is_downloaded_locally": True
    })

    # Retrieve and verify file path
    sess = session_manager.get_session(dl_drop_id)
    assert sess is not None
    f_path = Path(sess["working_path"])
    assert f_path.exists()
    with open(f_path, "rb") as f:
        read_bytes = f.read()
    assert read_bytes == test_content
    print(f"✅ Direct download session verified: File={sess['audio_filename']}, Bytes={len(read_bytes)}")

    # Cleanup temporary test files
    try:
        session_manager.remove_session(test_drop_id)
        session_manager.remove_session(dl_drop_id)
        if banner_path.exists(): banner_path.unlink()
        if dl_test_file.exists(): dl_test_file.unlink()
        await StoreService.delete_product(course.product_id)
    except Exception:
        pass

    print("\n==================================================")
    print("🎉 ALL 4 TEST SUITES PASSED FLAWLESSLY! (v24.9.1)")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
