import asyncio
import os
import sys
import wave
import struct
import math
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import config
from core.database import init_db
from services.store_service import StoreService
from media.compressor import SmartAudioCompressor, SmartVideoCompressor, convert_audio_to_mp3_if_needed
from services.media_service import MediaService
from services.session_manager import session_manager
from platforms.bale_adapter import BaleAdapter

async def run_tests():
    print("==================================================")
    print("Starting UNFINIT Store Engine v24.9 Verification")
    print("==================================================")

    # 1. Test Config Settings
    print("\n[TEST 1] Verifying 49.99 MB safe limit...")
    assert config.MAX_SAFE_BALE_SIZE_MB == 49.99, f"Expected 49.99, got {config.MAX_SAFE_BALE_SIZE_MB}"
    expected_bytes = int(49.99 * 1024 * 1024)
    assert config.MAX_SAFE_BALE_SIZE_BYTES == expected_bytes, f"Expected {expected_bytes}, got {config.MAX_SAFE_BALE_SIZE_BYTES}"
    print(f"OK Config verified: MAX_SAFE_BALE_SIZE_MB = {config.MAX_SAFE_BALE_SIZE_MB} ({config.MAX_SAFE_BALE_SIZE_BYTES} bytes)")

    # 2. Test Database and StoreService
    print("\n[TEST 2] Verifying Database schema and StoreService...")
    await init_db()
    test_prod = await StoreService.add_product(
        name="AI Course v24.9",
        price=180000,
        description="Comprehensive AI Course Test",
        download_link="https://dl.unfinit.com/ai_course.zip",
        photo_url="https://unfinit.com/banner.jpg",
        allow_card=True,
        allow_bale=True
    )
    assert test_prod is not None
    assert test_prod.download_link == "https://dl.unfinit.com/ai_course.zip"
    assert test_prod.allow_card is True
    assert test_prod.allow_bale is True
    assert test_prod.price == 180000
    print(f"OK Created course: ID={test_prod.product_id}, Name={test_prod.name}, Link={test_prod.download_link}")

    # Test update and toggle
    await StoreService.update_product_field(test_prod.product_id, "price", 195000)
    updated_prod = await StoreService.get_product(test_prod.product_id)
    assert updated_prod.price == 195000
    print(f"OK Updated course price to: {updated_prod.price:,} Tomans")

    # Test Order creation & get_order
    order = await StoreService.create_order(
        user_id="test_bale_user",
        username="test_user",
        customer_name="Ali Test",
        phone="09120000000",
        product=updated_prod,
        platform="bale"
    )
    assert order is not None
    fetched_order = await StoreService.get_order(order.order_id)
    assert fetched_order is not None
    assert fetched_order.order_id == order.order_id
    res_app = await StoreService.approve_order(order.order_id)
    assert res_app is not None
    print(f"OK Order workflow verified: OrderID={order.order_id}, Status approved!")

    # 3. Test Audio Transcoding (Lightweight < 50KB WAV generation)
    print("\n[TEST 3] Generating lightweight test audio (< 50 KB) & testing MP3 converter...")
    test_wav_path = config.TEMP_DIR / "synthetic_test.wav"
    sample_rate = 44100
    duration_sec = 0.5  # Half second
    n_samples = int(sample_rate * duration_sec)
    
    with wave.open(str(test_wav_path), "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        raw_frames = bytearray()
        for i in range(n_samples):
            val = int(32767.0 * 0.3 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            raw_frames.extend(struct.pack("<h", val))
        wav_file.writeframes(raw_frames)

    wav_size = test_wav_path.stat().st_size
    print(f"   Created synthetic test WAV: {test_wav_path.name} ({wav_size} bytes)")
    assert wav_size < 100 * 1024, "Test file must be under 100 KB"

    # Test conversion to MP3
    mp3_res, was_conv = convert_audio_to_mp3_if_needed(test_wav_path)
    assert was_conv is True
    assert mp3_res.exists()
    assert mp3_res.suffix.lower() == ".mp3"
    print(f"OK Transcoded non-MP3 audio to MP3: {mp3_res.name} ({mp3_res.stat().st_size} bytes)")

    # 4. Test Video & Audio Target Bitrate Calculations
    print("\n[TEST 4] Verifying Smart Compression bitrate formulas...")
    dur_60m = 3600.0  # 1 hour video
    v_bitrate = SmartVideoCompressor.calculate_target_video_bitrate(
        duration_sec=dur_60m,
        target_max_bytes=config.MAX_SAFE_BALE_SIZE_BYTES,
        audio_bitrate_kbps=64
    )
    print(f"   Calculated 1-hour video target bitrate: {v_bitrate} kbps")
    assert v_bitrate >= 64, "Bitrate must not be less than 64 kbps"

    dur_5m = 300.0  # 5 minutes video
    v_bitrate_5m = SmartVideoCompressor.calculate_target_video_bitrate(
        duration_sec=dur_5m,
        target_max_bytes=config.MAX_SAFE_BALE_SIZE_BYTES,
        audio_bitrate_kbps=96
    )
    print(f"   Calculated 5-minute video target bitrate: {v_bitrate_5m} kbps")
    assert v_bitrate_5m > 500, f"Expected > 500 kbps for 5-min video, got {v_bitrate_5m}"
    print("OK SmartVideoCompressor bitrate targeting verified!")

    # 5. Test MediaService prepare_for_transfer with Rubika
    print("\n[TEST 5] Verifying MediaService Rubika non-MP3 auto-conversion integration...")
    drop_id = "test_drop_v24_9"
    session_manager.create_session(drop_id, {
        "audio_filename": "speech_lesson.wav",
        "working_path": str(test_wav_path),
        "media_type": "audio",
        "file_size": wav_size,
        "is_downloaded_locally": True
    })
    prep_p, prep_name, prep_info = MediaService.prepare_for_transfer(drop_id, "rubika")
    assert prep_p.suffix.lower() == ".mp3"
    assert prep_name.endswith(".mp3")
    print(f"OK MediaService automatically converted WAV to {prep_p.name} for Rubika target!")

    # 6. Test BaleAdapter send_invoice interface
    print("\n[TEST 6] Verifying BaleAdapter invoice methods interface...")
    bale = BaleAdapter(token="test_mock_token")
    assert hasattr(bale, "send_invoice")
    assert hasattr(bale, "answer_pre_checkout_query")
    print("OK BaleAdapter send_invoice and answer_pre_checkout_query exist and are bound.")

    # Cleanup temporary test files
    try:
        if test_wav_path.exists(): test_wav_path.unlink()
        if mp3_res.exists(): mp3_res.unlink()
    except Exception:
        pass

    print("\n==================================================")
    print("ALL 6 TEST SUITES PASSED FLAWLESSLY! (v24.9.0)")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
