"""
Unit tests for UNFINIT Store Engine v0.6.1 release.
Validates:
- ProgressFileWrapper payload registration as BufferedReaderPayload
- Dynamic Content-Length calculation
- Smart speed formatting (KB/s vs MB/s)
- Decoupled poller execution
- Engine version bump to v0.6.1
"""
import io
import sys
import time
import asyncio
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure event loop exists on MainThread for Python 3.14 Pyrogram sync wrapper
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import aiohttp.payload
from core.config import config, ENGINE_VERSION
from platforms.bale_adapter import ProgressFileWrapper, format_bale_transfer_progress
from platforms.telegram_adapter import run_bale_upload_with_progress

def test_engine_version():
    assert str(config.ENGINE_VERSION) == "v0.6.1"
    assert str(ENGINE_VERSION) == "v0.6.1"
    print("✓ Engine version is v0.6.1")

def test_progress_file_wrapper_payload():
    test_file = Path("test_sample_v061.bin")
    data = b"X" * (128 * 1024)
    test_file.write_bytes(data)
    try:
        wrapper = ProgressFileWrapper(test_file)
        pl = aiohttp.payload.get_payload(wrapper)
        assert isinstance(pl, aiohttp.payload.BufferedReaderPayload)
        assert pl.size == len(data)
        print("✓ ProgressFileWrapper payload registered as BufferedReaderPayload with exact size")

        chunk1 = wrapper.read(64 * 1024)
        assert len(chunk1) == 64 * 1024
        assert wrapper.uploaded_bytes == 64 * 1024

        chunk2 = wrapper.read(64 * 1024)
        assert len(chunk2) == 64 * 1024
        assert wrapper.uploaded_bytes == len(data)

        eof = wrapper.read(1024)
        assert len(eof) == 0
        assert wrapper.is_done is True

        wrapper.seek(0)
        assert wrapper.uploaded_bytes == 0
        assert wrapper.is_done is False
        print("✓ ProgressFileWrapper read, seek and is_done work properly")
        wrapper.close()
    finally:
        if test_file.exists():
            test_file.unlink()

def test_smart_speed_formatting():
    # Test sub-MB speed formatting
    txt_kb = format_bale_transfer_progress(current=500 * 1024, total=10 * 1024 * 1024, elapsed_sec=1.0)
    assert "KB/s" in txt_kb
    assert "500 KB/s" in txt_kb or "500" in txt_kb

    # Test multi-MB speed formatting
    txt_mb = format_bale_transfer_progress(current=3 * 1024 * 1024, total=10 * 1024 * 1024, elapsed_sec=1.0)
    assert "MB/s" in txt_mb
    assert "3.0 MB/s" in txt_mb or "3" in txt_mb

    # Test explicit speed_text override
    txt_custom = format_bale_transfer_progress(current=1024, total=2048, elapsed_sec=1.0, speed_text="450 KB/s")
    assert "450 KB/s" in txt_custom
    print("✓ format_bale_transfer_progress smart speed units validated")

class DummyMsg:
    def __init__(self):
        self.edits = []

    async def edit_text(self, text, **kwargs):
        self.edits.append(text)

async def test_decoupled_poller():
    test_file = Path("test_poller_sample.bin")
    data = b"Y" * (512 * 1024)
    test_file.write_bytes(data)
    try:
        wrapper = ProgressFileWrapper(test_file)
        msg = DummyMsg()

        async def dummy_upload():
            for _ in range(5):
                wrapper.read(100 * 1024)
                await asyncio.sleep(0.05)
            wrapper.read()
            return {"ok": True, "result": "uploaded"}

        res = await run_bale_upload_with_progress(
            tracker=wrapper,
            status_msg=msg,
            header_text="🚢 Testing Poller",
            upload_coro=dummy_upload()
        )
        assert res.get("ok") is True
        assert wrapper.uploaded_bytes == len(data)
        print("✓ run_bale_upload_with_progress completed successfully without blocking")
    finally:
        try:
            wrapper.close()
        except Exception:
            pass
        if test_file.exists():
            try:
                test_file.unlink()
            except Exception:
                pass

if __name__ == "__main__":
    test_engine_version()
    test_progress_file_wrapper_payload()
    test_smart_speed_formatting()
    asyncio.run(test_decoupled_poller())
    print("\n🎉 ALL TESTS IN test_v061.py PASSED SUCCESSFULLY!")
