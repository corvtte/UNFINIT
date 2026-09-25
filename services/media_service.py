import re
import time
import uuid
import shutil
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Callable, Union
import math
from core.config import config
from core.logger import get_logger
from media.inspector import inspect_all_metadata, inspect_technical_metadata, inspect_audio_stream
from media.tagger import (
    modify_id3_tags,
    extract_cover_image,
    generate_video_thumbnail,
    strip_all_metadata,
    inspect_cover_details,
    copy_all_id3_tags
)
from media.compressor import SmartAudioCompressor, SmartVideoCompressor, convert_audio_to_mp3_if_needed
from services.compressor import SmartVideoSplitter, get_video_duration_async
from services.session_manager import session_manager

logger = get_logger("media_service")

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac", ".wma", ".opus", ".m4b"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v", ".ts"}


def clean_public_filename(
    raw_name: str,
    is_split_part: Union[bool, int] = False,
    part_idx: Optional[int] = None,
    total_parts: Optional[int] = None
) -> str:
    """
    پاکسازی قطعی نام فایل و حذف هش‌ها و پیشوندهای سیستمی (مانند compressed_، temp_ یا شناسه هش هگز).
    قالب‌بندی 'پارت X از Y' صرفاً و منحصراً زمانی اعمال می‌شود که فایل در عملیات اسپلیت تقسیم شده باشد (is_split_part=True).
    فایل‌های مستقل در ارسال‌های گروهی هرگز برچسب پارت دریافت نمی‌کنند.
    """
    if not raw_name:
        return "media_file"
    import urllib.parse
    name = urllib.parse.unquote(str(raw_name).strip())
    # Strip internal engine prefixes and hashes
    name = re.sub(r'^(compressed_|lazy_|temp_|raw_|trimmed_|[a-f0-9]{6,16}_)+', '', name, flags=re.IGNORECASE)
    p = Path(name)
    base = p.stem.strip()
    ext = p.suffix.strip()

    # Clean existing part tags if any
    base = re.sub(r'(_part\d+of\d+|\.part\d+|- پارت \d+ از \d+)', '', base, flags=re.IGNORECASE).strip()

    # Handle legacy positional calls if any: clean_public_filename(raw, 1, 2)
    if isinstance(is_split_part, int) and not isinstance(is_split_part, bool):
        total_parts = part_idx
        part_idx = is_split_part
        is_split_part = True

    # ONLY apply "پارت X از Y" if is_split_part is TRUE (explicitly a split chunk)
    if is_split_part and part_idx is not None and total_parts is not None and int(total_parts) > 1:
        return f"{base} - پارت {part_idx} از {total_parts}{ext}"

    # Independent files in batch dispatch must NEVER have part numbers in their name
    return f"{base}{ext}"


def clean_display_filename(filename: str) -> str:
    """
    Strips system prefixes such as drop_id, task_id, or compressed_ from filename
    and unquotes any URL-encoded Persian/Unicode characters.
    """
    return clean_public_filename(filename)


async def get_bale_compression_settings() -> Tuple[float, float, float]:
    """
    دریافت سقف پایه، درصد بافر امنیتی و حجم هدف مؤثر انکودر بله به صورت کاملاً پویا از دیتابیس و settings.json.
    خروجی: (سقف پایه به مگابایت، درصد بافر امنیتی، حجم هدف مؤثر انکودر به مگابایت)
    """
    from core.database import get_system_setting
    cap_val = await get_system_setting("bale_max_file_size_mb", None)
    if cap_val is None:
        cap_val = await get_system_setting("bale_safe_limit_mb", None)
    if cap_val is None:
        cap_val = await get_system_setting("MAX_SAFE_BALE_SIZE_MB", None)
    if cap_val is None:
        cap_val = getattr(config, "MAX_SAFE_BALE_SIZE_MB", 50.0)
    try:
        raw_cap_mb = float(str(cap_val).strip())
    except Exception:
        raw_cap_mb = 50.0

    buf_val = await get_system_setting("bale_safety_buffer_percent", 3.0)
    try:
        buffer_percent = float(str(buf_val).strip())
    except Exception:
        buffer_percent = 3.0

    buffer_percent = max(0.0, min(buffer_percent, 15.0))
    effective_target_mb = round(raw_cap_mb * (1.0 - (buffer_percent / 100.0)), 2)
    return raw_cap_mb, buffer_percent, effective_target_mb


async def get_bale_max_size_mb() -> float:
    """
    دریافت سقف مجاز فایل در بله به صورت کاملاً پویا از دیتابیس / تنظیمات وب‌پنل در settings.json.
    هیچ سقف ثابتی نباید هاردکد شود و اولویت با مقدار ورودی ادمین در پنل وب است.
    """
    raw_cap_mb, _, _ = await get_bale_compression_settings()
    return raw_cap_mb


async def compress_video_async(
    input_path: str,
    output_path: str,
    target_mb: Optional[float] = None,
    progress_callback: Optional[Callable] = None
) -> bool:
    """
    فشرده‌سازی غیرمسدودکننده ویدیو با استفاده از asyncio.create_subprocess_exec و فلگ -progress pipe:1
    جهت مهار فریز حلقه رویدادها و گزارش پیشرفت زنده هر ۳ ثانیه یک‌بار.
    """
    input_p = Path(input_path)
    output_p = Path(output_path)
    if not input_p.exists():
        return False
    orig_mb = input_p.stat().st_size / (1024 * 1024)

    raw_cap, buf_pct, effective_mb = await get_bale_compression_settings()
    if target_mb is None:
        target_mb = effective_mb

    # 1. Probe duration asynchronously via ffprobe
    duration = 0.0
    try:
        probe_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(input_p)
        ]
        proc_probe = await asyncio.create_subprocess_exec(
            *probe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc_probe.communicate()
        duration = float(stdout.decode().strip())
    except Exception:
        duration = 0.0

    # 2. Compute dynamic video bitrate
    audio_bitrate_kbps = 64
    if duration > 0:
        target_total_bitrate_kbps = (target_mb * 8192) / duration
        video_bitrate_kbps = max(int(target_total_bitrate_kbps - audio_bitrate_kbps), 150)
    else:
        video_bitrate_kbps = 350

    # 3. Non-blocking FFmpeg process with -progress pipe:1 and -threads 0
    cmd = [
        "ffmpeg", "-y", "-i", str(input_p),
        "-c:v", "libx264", "-b:v", f"{video_bitrate_kbps}k",
        "-preset", "veryfast", "-tune", "fastdecode", "-threads", "0",
        "-vf", "scale='min(1280,iw)':-2",
        "-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k",
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        str(output_p)
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )

    last_update = 0.0
    start_time = time.time()

    # Read progress asynchronously without blocking event loop
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        text = line.decode('utf-8', errors='ignore').strip()

        if text.startswith("out_time_us="):
            try:
                parts = text.split("=")
                if len(parts) > 1 and parts[1].isdigit():
                    out_us = int(parts[1])
                    out_sec = out_us / 1_000_000.0
                    if duration > 0:
                        percent = min((out_sec / duration) * 100.0, 99.0)
                        now = time.time()
                        elapsed = now - start_time
                        speed = (out_sec / elapsed) if elapsed > 0 else 1.0
                        remaining_sec = (duration - out_sec) / speed if speed > 0 else 0
                        eta_str = f"{int(remaining_sec // 60):02d}:{int(remaining_sec % 60):02d}"

                        if progress_callback and (now - last_update >= 3.0 or percent >= 98.0):
                            last_update = now
                            res = progress_callback(percent, speed, eta_str, orig_mb, raw_cap)
                            if asyncio.iscoroutine(res):
                                asyncio.create_task(res)
            except Exception:
                pass

    await proc.wait()
    success = output_p.exists() and output_p.stat().st_size > 0
    if success:
        final_size_mb = output_p.stat().st_size / (1024 * 1024)
        if final_size_mb > raw_cap:
            logger.warning(
                f"[CompressVideo] Output size {final_size_mb:.2f}MB exceeded base cap {raw_cap:.2f}MB (effective target was {target_mb:.2f}MB)"
            )
    return success


class SequentialBatchQueue:
    """
    صف ترتیبی FIFO برای مهار فشار همزمان پردازش و انتقال دسته‌جمعی رسانه‌ها (Batch Media Transfers).
    تنها یک دسته در هر لحظه پردازش می‌شود تا از اشباع پردازنده سرور و فریز شدن نوار پیشرفت جلوگیری شود.
    """
    def __init__(self):
        self._queue: Optional[asyncio.Queue] = None
        self._worker_task: Optional[asyncio.Task] = None

    def _ensure_queue(self):
        if self._queue is None:
            self._queue = asyncio.Queue()

    def _ensure_worker(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def enqueue(self, coroutine_fn: Callable[[], Any]) -> Any:
        self._ensure_queue()
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        await self._queue.put((coroutine_fn, fut))
        self._ensure_worker()
        return await fut

    async def _worker_loop(self):
        while True:
            try:
                coro_fn, fut = await self._queue.get()
                try:
                    res = await coro_fn()
                    if not fut.done():
                        fut.set_result(res)
                except Exception as ex:
                    if not fut.done():
                        fut.set_exception(ex)
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[SequentialBatchQueue] Unhandled loop error: {e}")


class MediaService:
    batch_queue: SequentialBatchQueue = SequentialBatchQueue()

    @staticmethod
    def register_incoming_message_meta(
        drop_id: str,
        source_platform: str,
        chat_id: str | int,
        file_id: str,
        file_name: str,
        file_size: int,
        media_type: str = "audio",
        api_meta: Optional[Dict[str, Any]] = None,
        caption: str = "",
        raw_message: Any = None
    ) -> Dict[str, Any]:
        clean_fn = clean_display_filename(file_name)

        # Every incoming media receives a fresh unique session to prevent stale/expired attachments
        session_data = {
            "drop_id": drop_id,
            "source_platform": source_platform,
            "chat_id": str(chat_id),
            "file_id": str(file_id),
            "audio_filename": clean_fn,
            "file_size": file_size,
            "media_type": media_type,
            "caption": caption or "",
            "api_meta": api_meta or {},
            "raw_message": raw_message,
            "is_downloaded_locally": False,
            "working_path": None,
            "original_path": None,
            "tech_meta": {},
            "embed_meta": {},
            "cover_info": {},
            "thumb_path": None,
            "current_status": "",
            "edited_fields": {},
            "draft_tags": {}  # In-memory fast draft tags before physical write
        }
        return session_manager.create_session(drop_id, session_data)

    @staticmethod
    async def turbo_download_telegram(
        client: Any,
        target_media: Any,
        dest_path: Path,
        progress_callback: Optional[Callable[..., Any]] = None
    ) -> bool:
        """
        دانلود پرسرعت چندچانکی با استریم بافرینگ موازی (Turbo Multi-Chunk Streaming).
        از استریم پیوسته بافر ۲ مگابایتی برای حداکثر کردن پهنای باند و دور زدن گلوگاه ۱MB/s هاگینگ‌فیس استفاده می‌کند.
        """
        dest_p = Path(dest_path)
        dest_p.parent.mkdir(parents=True, exist_ok=True)
        part_p = dest_p.with_suffix(dest_p.suffix + f".turbo_{uuid.uuid4().hex[:6]}.part")

        # 1. تلاش نخست: دانلود جریانی چانک‌ها با بافر بهینه‌شده
        try:
            total_size = 0
            raw_msg = target_media
            if hasattr(raw_msg, "video") and raw_msg.video and getattr(raw_msg.video, "file_size", 0):
                total_size = int(raw_msg.video.file_size)
            elif hasattr(raw_msg, "audio") and raw_msg.audio and getattr(raw_msg.audio, "file_size", 0):
                total_size = int(raw_msg.audio.file_size)
            elif hasattr(raw_msg, "document") and raw_msg.document and getattr(raw_msg.document, "file_size", 0):
                total_size = int(raw_msg.document.file_size)
            elif hasattr(raw_msg, "file_size") and raw_msg.file_size:
                total_size = int(raw_msg.file_size)
            elif isinstance(raw_msg, dict) and raw_msg.get("file_size"):
                total_size = int(raw_msg["file_size"])

            written_bytes = 0
            start_time = time.time()
            last_edit = 0.0
            last_pct = 0

            with open(part_p, "wb") as f_out:
                async for chunk in client.stream_media(target_media, limit=0):
                    f_out.write(chunk)
                    written_bytes += len(chunk)
                    now = time.time()
                    pct = int((written_bytes / total_size) * 100) if total_size > 0 else 0
                    if pct >= 100 and written_bytes < total_size:
                        pct = 99
                    # تراتل در بازه‌های ۱۰ درصدی یا حداقل ۱.۵ ثانیه جهت محافظت از سقف مجاز تلگرام
                    if progress_callback and ((now - last_edit >= 1.5 and abs(pct - last_pct) >= 10) or (total_size > 0 and written_bytes >= total_size)):
                        last_edit = now
                        last_pct = pct
                        try:
                            cb_res = progress_callback(written_bytes, total_size or written_bytes, now - start_time)
                            if asyncio.iscoroutine(cb_res):
                                await cb_res
                        except Exception:
                            pass
                f_out.flush()
                try:
                    os.fsync(f_out.fileno())
                except Exception:
                    pass

            if part_p.exists():
                actual_bytes = part_p.stat().st_size
                # اعتبارسنجی یکپارچگی بایت‌ها: اگر حجم کل فایل مشخص بود، باید دانلود دقیقاً تا بایت آخر انجام شده باشد
                if total_size > 0 and actual_bytes < total_size:
                    raise ValueError(f"Incomplete turbo stream: got {actual_bytes} bytes, expected {total_size} bytes")

                if actual_bytes > 0:
                    if dest_p.exists():
                        try: dest_p.unlink()
                        except Exception: pass
                    part_p.rename(dest_p)
                    # ارسال گزارش پیشرفت قطعی ۱۰۰٪ منحصراً پس از فلاش و ثبت فیزیکی بر روی دیسک
                    if progress_callback:
                        try:
                            cb_res = progress_callback(actual_bytes, actual_bytes, time.time() - start_time)
                            if asyncio.iscoroutine(cb_res):
                                await cb_res
                        except Exception:
                            pass
                    logger.info(f"Turbo multi-chunk streaming download successful: {dest_p.name} ({actual_bytes} bytes)")
                    return True
        except Exception as stream_err:
            logger.warning(f"Turbo stream chunking fell back to standard download_media ({stream_err})")
            if part_p.exists():
                try: part_p.unlink()
                except Exception: pass

        # 2. فال‌بک امن و استاندارد Pyrogram
        try:
            if progress_callback:
                await client.download_media(target_media, file_name=str(dest_p), progress=progress_callback)
            else:
                await client.download_media(target_media, file_name=str(dest_p))
            return dest_p.exists() and dest_p.stat().st_size > 0
        except TypeError:
            await client.download_media(target_media, file_name=str(dest_p))
            return dest_p.exists() and dest_p.stat().st_size > 0

    @staticmethod
    async def ensure_local_binary(
        drop_id: str,
        downloader_callback: Optional[Callable[[str, Path], Any]] = None
    ) -> bool:
        session = session_manager.get_session(drop_id)
        if not session:
            return False

        if session.get("is_downloaded_locally") and session.get("working_path"):
            w_p = Path(session["working_path"])
            if w_p.exists() and w_p.stat().st_size > 0:
                return True

        fn = session.get("audio_filename") or "media.mp3"
        temp_path = config.TEMP_DIR / f"{drop_id}_{clean_display_filename(fn)}"
        temp_path.parent.mkdir(parents=True, exist_ok=True)

        if temp_path.exists() and temp_path.stat().st_size > 0:
            session["working_path"] = str(temp_path)
            session["original_path"] = str(temp_path)
            session["is_downloaded_locally"] = True
            session_manager.update_session(drop_id, session)
            return True

        ok = False
        if downloader_callback:
            logger.info(f"[{drop_id}] Lazy-downloading binary via callback to {temp_path.name}...")
            ok = await downloader_callback(session["file_id"], temp_path)
        else:
            # Auto-resolve downloader from source platform / active adapters
            source = (session.get("source_platform") or "").lower()
            file_id = session.get("file_id") or ""
            logger.info(f"[{drop_id}] Auto-resolving downloader for platform={source}, file_id={str(file_id)[:30]}...")

            if source in ("telegram", "tg"):
                import services.web_panel as wp
                tg = getattr(wp, "ACTIVE_TG_ADAPTER", None)
                if tg and getattr(tg, "app", None):
                    try:
                        target_m = session.get("raw_message") or file_id
                        ok = await MediaService.turbo_download_telegram(tg.app, target_m, temp_path)
                    except Exception as e:
                        logger.error(f"Telegram auto-download failed for {drop_id}: {e}")
            elif source == "bale":
                import services.web_panel as wp
                bale = getattr(wp, "ACTIVE_BALE_ADAPTER", None)
                if not bale:
                    from platforms.bale_adapter import BaleAdapter
                    bale = BaleAdapter()
                if bale:
                    try:
                        ok = await bale.download_file(file_id, temp_path)
                    except Exception as e:
                        logger.error(f"Bale auto-download failed for {drop_id}: {e}")
            elif source == "rubika":
                import services.web_panel as wp
                rubika = getattr(wp, "ACTIVE_RUBIKA_ADAPTER", None)
                client = getattr(rubika, "bot_client", None) if rubika else None
                if not client:
                    from platforms.rubika_adapter import RubikaBotClient
                    client = RubikaBotClient()
                if client:
                    try:
                        ok = await client.download_file(file_id, temp_path)
                    except Exception as e:
                        logger.error(f"Rubika auto-download failed for {drop_id}: {e}")
            elif source in ("web_url", "url") or str(file_id).startswith("http"):
                from services.url_service import UrlService
                try:
                    ok = await UrlService.download_file_stream(file_id, temp_path)
                except Exception as e:
                    logger.error(f"URL auto-download failed for {drop_id}: {e}")

        if ok and temp_path.exists() and temp_path.stat().st_size > 0:
            session["working_path"] = str(temp_path)
            session["original_path"] = str(temp_path)
            session["is_downloaded_locally"] = True
            session["file_size"] = temp_path.stat().st_size

            try:
                tech_meta, embed_meta = inspect_all_metadata(temp_path)
                session["tech_meta"] = tech_meta
                session["embed_meta"] = embed_meta
                session["cover_info"] = inspect_cover_details(temp_path)
            except Exception as e:
                logger.warning(f"Failed to inspect metadata after lazy download: {e}")

            session_manager.update_session(drop_id, session)
            logger.info(f"[{drop_id}] Binary successfully downloaded and registered: {temp_path.name}")
            return True

        return False

    @staticmethod
    def inspect_full(drop_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        session = session_manager.get_session(drop_id)
        if not session or not session.get("working_path"):
            return {}, {}
        tech, embed = inspect_all_metadata(session["working_path"])
        session["cover_info"] = inspect_cover_details(session["working_path"])
        return tech, embed

    @staticmethod
    def trim_audio(
        file_path: str | Path,
        start_sec: float,
        end_sec: Optional[float] = None,
        output_path: Optional[Path] = None
    ) -> Tuple[bool, Path]:
        """
        Trims audio file from start_sec to end_sec with fast stream copy and fallback accurate re-encode.
        Preserves all ID3 metadata and album art.
        """
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"Input audio file not found: {file_path}")

        out_p = output_path or config.TEMP_DIR / f"trimmed_{src.stem}{src.suffix}"
        out_p.parent.mkdir(parents=True, exist_ok=True)

        start_str = f"{start_sec:.2f}"
        
        # 1. Attempt Fast Seek stream copy
        cmd_copy = ["ffmpeg", "-y", "-ss", start_str]
        if end_sec is not None and end_sec > start_sec:
            duration = end_sec - start_sec
            cmd_copy.extend(["-t", f"{duration:.2f}"])
        cmd_copy.extend(["-i", str(src), "-c", "copy", str(out_p)])

        logger.info(f"Trimming audio ({start_sec}s to {end_sec}s) with fast copy: {cmd_copy}")
        res = subprocess.run(cmd_copy, capture_output=True, text=True, timeout=120)

        # Verify copy output
        if res.returncode != 0 or not out_p.exists() or out_p.stat().st_size < 1000:
            logger.warning("Stream copy trim failed or output invalid, applying precise re-encoding...")
            ast = inspect_audio_stream(src)
            bitrate_k = ast.get("bitrate_kbps", 192)
            sr = ast.get("sample_rate", 44100)
            ch = ast.get("channels", 2)

            cmd_encode = ["ffmpeg", "-y", "-ss", start_str]
            if end_sec is not None and end_sec > start_sec:
                duration = end_sec - start_sec
                cmd_encode.extend(["-t", f"{duration:.2f}"])
            cmd_encode.extend([
                "-i", str(src),
                "-acodec", "libmp3lame" if src.suffix.lower() == ".mp3" else "aac",
                "-b:a", f"{bitrate_k}k",
                "-ar", str(sr),
                "-ac", str(ch),
                str(out_p)
            ])
            res_enc = subprocess.run(cmd_encode, capture_output=True, text=True, timeout=300)
            if res_enc.returncode != 0 or not out_p.exists():
                logger.error(f"Re-encode trim failed: {res_enc.stderr}")
                return False, src

        # Copy original tags and cover to trimmed audio
        copy_all_id3_tags(src, out_p)
        logger.info(f"Audio trimmed successfully: {out_p.name} ({out_p.stat().st_size} bytes)")
        return True, out_p

    @staticmethod
    def strip_metadata_for_session(drop_id: str) -> Tuple[bool, Path]:
        """
        Strips all tags and cover art from session file and returns the clean raw file.
        """
        session = session_manager.get_session(drop_id)
        if not session or not session.get("working_path"):
            raise ValueError(f"Session working binary not found for drop_id: {drop_id}")

        working_path = Path(session["working_path"])
        ok, raw_p = strip_all_metadata(working_path)
        if ok and raw_p.exists():
            session["working_path"] = str(raw_p)
            session["embed_meta"] = {}
            session["cover_info"] = {"has_cover": False, "resolution": "ندارد", "size_kb": 0, "format": "ندارد"}
            session["draft_tags"] = {}
            session["thumb_path"] = None
        return ok, raw_p

    @staticmethod
    def convert_video_to_mp3(
        video_path: str | Path,
        output_path: Optional[Path] = None,
        custom_tags: Optional[Dict[str, Any]] = None,
        cover_image_path: Optional[str | Path] = None
    ) -> Tuple[bool, Path]:
        v_path = Path(video_path).resolve()
        if not v_path.exists():
            raise FileNotFoundError(f"Input video file not found: {video_path}")

        # مهار قطعی خطای FFmpeg cannot edit existing files in-place
        target_out = (Path(output_path) if output_path else config.TEMP_DIR / f"{v_path.stem}.mp3").resolve()
        target_out.parent.mkdir(parents=True, exist_ok=True)

        if target_out == v_path or target_out.exists():
            temp_extract = config.TEMP_DIR / f"extract_{v_path.stem}_{uuid.uuid4().hex[:6]}.mp3"
        else:
            temp_extract = target_out
        temp_extract.parent.mkdir(parents=True, exist_ok=True)

        ast_info = inspect_audio_stream(v_path)
        sample_rate = ast_info.get("sample_rate", 44100)
        channels = ast_info.get("channels", 2)
        bitrate_kbps = ast_info.get("bitrate_kbps", 192)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(v_path),
            "-vn",
            "-acodec", "libmp3lame",
            "-b:a", f"{bitrate_kbps}k",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            str(temp_extract)
        ]
        logger.info(f"Extracting MP3 from {v_path.name} (Bitrate: {bitrate_kbps}k, SampleRate: {sample_rate}Hz, Channels: {channels}): {cmd}")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if res.returncode != 0 or not temp_extract.exists() or temp_extract.stat().st_size < 100:
            logger.error(f"FFmpeg video-to-mp3 extraction error: {res.stderr}")
            return False, temp_extract

        tags = custom_tags or {}
        if "title" not in tags or not tags["title"]:
            tags["title"] = v_path.stem
        if "artist" not in tags or not tags["artist"]:
            # تزریق خودکار نام خواننده فقط در صورت فعال بودن صریح در تنظیمات
            tags["artist"] = config.DEFAULT_ARTIST if getattr(config, "APPLY_DEFAULT_ARTIST_TAG", False) else ""

        cov_p = cover_image_path or generate_video_thumbnail(v_path)
        modify_id3_tags(temp_extract, tags, cover_image_path=cov_p)

        # انتقال نهایی به فایل مقصد در صورت استفاده از فایل موقت متمایز
        if temp_extract != target_out:
            if target_out.exists() and target_out != v_path:
                try: target_out.unlink()
                except Exception: pass
            if target_out != v_path:
                shutil.move(str(temp_extract), str(target_out))
                final_out = target_out
            else:
                final_out = temp_extract
        else:
            final_out = temp_extract

        logger.info(f"Video converted to MP3 successfully: {final_out.name} ({final_out.stat().st_size} bytes)")
        return True, final_out

    @staticmethod
    def extract_audio_from_video(drop_id: str) -> Tuple[bool, Path, Dict[str, Any]]:
        session = session_manager.get_session(drop_id)
        if not session or not session.get("working_path"):
            raise ValueError(f"Session or working video file not found for drop_id: {drop_id}")

        v_path = Path(session["working_path"])
        def_art = config.DEFAULT_ARTIST if getattr(config, "APPLY_DEFAULT_ARTIST_TAG", False) else ""
        tags = {
            "title": session.get("draft_tags", {}).get("title") or session.get("embed_meta", {}).get("title") or v_path.stem,
            "artist": session.get("draft_tags", {}).get("artist") or session.get("embed_meta", {}).get("artist") or def_art
        }
        thumb = session.get("thumb_path") or generate_video_thumbnail(v_path)

        mp3_out = config.TEMP_DIR / f"{v_path.stem}.mp3"
        ok, final_mp3 = MediaService.convert_video_to_mp3(v_path, output_path=mp3_out, custom_tags=tags, cover_image_path=thumb)

        tech = inspect_technical_metadata(final_mp3)
        info = {
            "title": tags["title"],
            "artist": tags["artist"],
            "duration": tech.get("duration_sec", 0),
            "file_size": final_mp3.stat().st_size if final_mp3.exists() else 0,
            "file_name": final_mp3.name,
            "thumb_path": thumb
        }
        return ok, final_mp3, info

    @staticmethod
    def update_draft_field(drop_id: str, field_name: str, value: Any) -> bool:
        session = session_manager.get_session(drop_id)
        if not session:
            return False

        draft_tags = session.setdefault("draft_tags", {})
        edited_fields = session.setdefault("edited_fields", {})

        if field_name == "filename":
            new_fn = clean_display_filename(str(value).strip())
            session["audio_filename"] = new_fn
            edited_fields["filename"] = new_fn
            return True

        draft_tags[field_name] = value
        edited_fields[field_name] = value
        session.setdefault("embed_meta", {})[field_name] = value
        return True

    @staticmethod
    def apply_default_artist(drop_id: str) -> bool:
        return MediaService.update_draft_field(drop_id, "artist", config.DEFAULT_ARTIST)

    @staticmethod
    def extract_cover(drop_id: str) -> Optional[Path]:
        session = session_manager.get_session(drop_id)
        if not session or not session.get("working_path"):
            return None
        working_path = Path(session["working_path"])
        return extract_cover_image(working_path, output_dir=config.TEMP_DIR)

    @staticmethod
    def replace_cover(drop_id: str, new_image_path: str | Path) -> bool:
        session = session_manager.get_session(drop_id)
        if not session:
            return False
        session["thumb_path"] = str(new_image_path)
        session.setdefault("edited_fields", {})["thumb"] = True
        return True

    @staticmethod
    def remove_cover(drop_id: str) -> bool:
        session = session_manager.get_session(drop_id)
        if not session:
            return False
        session["thumb_path"] = None
        session.setdefault("edited_fields", {})["thumb"] = False
        session.setdefault("draft_tags", {})["remove_cover"] = True
        return True

    @staticmethod
    def apply_draft_tags_to_file(drop_id: str) -> Path:
        session = session_manager.get_session(drop_id)
        if not session or not session.get("working_path"):
            raise ValueError(f"Working file not found for drop_id: {drop_id}")

        working_path = Path(session["working_path"])
        draft_tags = session.get("draft_tags", {})
        thumb_path = session.get("thumb_path")
        remove_cov = draft_tags.get("remove_cover", False)

        if draft_tags or thumb_path or remove_cov:
            logger.info(f"[{drop_id}] Applying draft tags to binary: {draft_tags}...")
            clean_tags = {k: v for k, v in draft_tags.items() if k != "remove_cover"}
            modify_id3_tags(
                working_path,
                clean_tags,
                cover_image_path=thumb_path,
                remove_cover=remove_cov
            )
            _, updated_embed = inspect_all_metadata(working_path)
            session["embed_meta"] = updated_embed
            session["cover_info"] = inspect_cover_details(working_path)

        return working_path

    @staticmethod
    def prepare_for_transfer(
        drop_id: str,
        target_platform: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[Path, str, Dict[str, Any]]:
        session = session_manager.get_session(drop_id)
        if not session or not session.get("working_path"):
            raise ValueError(f"Session or local binary not found for drop_id: {drop_id}")

        working_path = MediaService.apply_draft_tags_to_file(drop_id)
        raw_name = session.get("audio_filename") or working_path.name
        send_name = clean_display_filename(raw_name)

        title_val = (
            session.get("draft_tags", {}).get("title") or 
            session.get("embed_meta", {}).get("title") or 
            session.get("api_meta", {}).get("title") or 
            send_name
        )
        artist_val = (
            session.get("draft_tags", {}).get("artist") or 
            session.get("embed_meta", {}).get("artist") or 
            session.get("api_meta", {}).get("artist") or 
            (config.DEFAULT_ARTIST if getattr(config, "APPLY_DEFAULT_ARTIST_TAG", False) else "")
        )

        # تغییر خودکار نام فایل به عنوان آهنگ فقط در صورت فعال بودن صریح تنظیمات
        if getattr(config, "AUTO_RENAME_FILE_TO_TITLE", False) and title_val and title_val != send_name:
            sanitized_title = re.sub(r'[\\/*?:"<>|]', '', title_val).strip()
            if sanitized_title:
                send_name = f"{sanitized_title}{working_path.suffix}"

        info = {
            "initial_size_bytes": working_path.stat().st_size if working_path.exists() else 0,
            "final_size_bytes": 0,
            "was_compressed": False,
            "target_platform": target_platform,
            "title": title_val,
            "artist": artist_val,
            "caption": session.get("caption", "")
        }

        # Rubika Compatibility: Convert any non-MP3 audio format to standard MP3 to prevent Invalid_format error
        if target_platform in ("rubika", "rubika_bot", "rubika_user"):
            if working_path.suffix.lower() in AUDIO_EXTENSIONS and working_path.suffix.lower() != ".mp3":
                converted_p, was_conv = convert_audio_to_mp3_if_needed(working_path)
                if was_conv:
                    working_path = converted_p
                    session["working_path"] = str(working_path)
                    send_name = Path(send_name).with_suffix(".mp3").name
                    info["initial_size_bytes"] = working_path.stat().st_size

        # If sending to Bale and audio or video file exceeds safe limit (49.99 MB), run Smart Compression
        if target_platform == "bale":
            if working_path.suffix.lower() in AUDIO_EXTENSIONS:
                final_path, init_sz, final_sz, final_bitrate, was_comp = SmartAudioCompressor.compress_if_needed(
                    working_path, progress_callback=progress_callback
                )
                session["compressed_path"] = str(final_path)
                info["final_size_bytes"] = final_sz
                info["was_compressed"] = was_comp
                info["final_bitrate"] = final_bitrate
                return final_path, send_name, info
            elif working_path.suffix.lower() in VIDEO_EXTENSIONS:
                final_path, init_sz, final_sz, final_bitrate, was_comp = SmartVideoCompressor.compress_if_needed_sync(
                    working_path, progress_callback=progress_callback
                )
                session["compressed_path"] = str(final_path)
                info["final_size_bytes"] = final_sz
                info["was_compressed"] = was_comp
                info["final_bitrate"] = final_bitrate
                return final_path, send_name, info

        info["final_size_bytes"] = info["initial_size_bytes"]
        return working_path, send_name, info

    @staticmethod
    async def prepare_for_transfer_async(
        drop_id: str,
        target_platform: str,
        progress_callback: Optional[Callable[[str], Any]] = None
    ) -> Tuple[Path, str, Dict[str, Any]]:
        """
        نسخه کاملاً غیرمسدودکننده (Async) آماده‌سازی رسانه برای انتقال.
        فشرده‌سازی ویدیو به صورت ناهمگام انجام می‌شود تا حلقه رویدادهای Asyncio هرگز قفل نشود.
        """
        session = session_manager.get_session(drop_id)
        if not session or not session.get("working_path"):
            raise ValueError(f"Session or local binary not found for drop_id: {drop_id}")

        working_path = MediaService.apply_draft_tags_to_file(drop_id)
        raw_name = session.get("audio_filename") or working_path.name
        send_name = clean_display_filename(raw_name)

        title_val = (
            session.get("draft_tags", {}).get("title") or 
            session.get("embed_meta", {}).get("title") or 
            session.get("api_meta", {}).get("title") or 
            send_name
        )
        artist_val = (
            session.get("draft_tags", {}).get("artist") or 
            session.get("embed_meta", {}).get("artist") or 
            session.get("api_meta", {}).get("artist") or 
            (config.DEFAULT_ARTIST if getattr(config, "APPLY_DEFAULT_ARTIST_TAG", False) else "")
        )

        if getattr(config, "AUTO_RENAME_FILE_TO_TITLE", False) and title_val and title_val != send_name:
            sanitized_title = re.sub(r'[\\/*?:"<>|]', '', title_val).strip()
            if sanitized_title:
                send_name = f"{sanitized_title}{working_path.suffix}"

        info = {
            "initial_size_bytes": working_path.stat().st_size if working_path.exists() else 0,
            "final_size_bytes": 0,
            "was_compressed": False,
            "target_platform": target_platform,
            "title": title_val,
            "artist": artist_val,
            "caption": session.get("caption", "")
        }

        if target_platform in ("rubika", "rubika_bot", "rubika_user"):
            if working_path.suffix.lower() in AUDIO_EXTENSIONS and working_path.suffix.lower() != ".mp3":
                converted_p, was_conv = convert_audio_to_mp3_if_needed(working_path)
                if was_conv:
                    working_path = converted_p
                    session["working_path"] = str(working_path)
                    send_name = Path(send_name).with_suffix(".mp3").name
                    info["initial_size_bytes"] = working_path.stat().st_size

        if target_platform == "bale":
            if working_path.suffix.lower() in AUDIO_EXTENSIONS:
                final_path, init_sz, final_sz, final_bitrate, was_comp = SmartAudioCompressor.compress_if_needed(
                    working_path, progress_callback=progress_callback
                )
                session["compressed_path"] = str(final_path)
                info["final_size_bytes"] = final_sz
                info["was_compressed"] = was_comp
                info["final_bitrate"] = final_bitrate
                return final_path, send_name, info
            elif working_path.suffix.lower() in VIDEO_EXTENSIONS:
                final_path, init_sz, final_sz, final_bitrate, was_comp = await SmartVideoCompressor.compress_if_needed(
                    working_path, progress_callback=progress_callback
                )
                session["compressed_path"] = str(final_path)
                info["final_size_bytes"] = final_sz
                info["was_compressed"] = was_comp
                info["final_bitrate"] = final_bitrate
                return final_path, send_name, info

        info["final_size_bytes"] = info["initial_size_bytes"]
        return working_path, send_name, info

    @classmethod
    async def process_batch_sequentially(
        cls,
        items: List[Dict[str, Any]],
        destination: str,
        bale_adapter: Any = None,
        rubika_adapter: Any = None,
        status_callback: Optional[Callable[[str], Any]] = None
    ) -> Dict[str, Any]:
        """
        پردازش کاملاً ترتیبی (FIFO Sequential) دسته‌ای از فایل‌ها در یک صف امن (asyncio.Queue).
        برای هر فایل:
        دانلود ➔ بررسی و فشرده‌سازی/تقسیم در صورت نیاز ➔ ارسال به پیام‌رسان مقصد ➔ تایید و ثبت پایان.
        وضعیت هر فایل به صورت پویا با نوار پیشرفت نمایش داده می‌شود:
        📦 فایل ۲ از ۳: [████▒▒▒] 45%
        """
        async def _job():
            total_count = len(items)
            success_count = 0
            dest_name = "بله" if destination == "bale" else "روبیکا"

            def _make_bar(pct: int, length: int = 8) -> str:
                f = min(length, max(0, int(round(length * pct / 100))))
                return f"[{'█' * f}{'░' * (length - f)}] \u200e{pct}%"

            async def _update_status(txt: str):
                if status_callback:
                    try:
                        res = status_callback(txt)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception:
                        pass

            for idx, it in enumerate(items, 1):
                s_drop_id = it.get("drop_id")
                s_data = it.get("data", {})
                fn = s_data.get("filename") or "media"
                raw_sz = int(s_data.get("file_size") or 1)

                # مرحله ۱: دانلود فایل
                await _update_status(
                    f"📦 <b>فایل {idx} از {total_count}:</b> <code>{_make_bar(15)}</code>\n"
                    f"📄 <b>{fn}</b>\n"
                    f"📥 در حال دانلود از مبدا..."
                )

                dl_ok = await cls.ensure_local_binary(s_drop_id)
                if not dl_ok:
                    logger.error(f"[BatchQueue] Failed to download binary for drop_id: {s_drop_id}")
                    continue

                # مرحله ۲: آماده‌سازی و بررسی پیش‌پرواز (Pre-flight Auto-Split Check)
                session = session_manager.get_session(s_drop_id) or {}
                local_p = Path(session.get("working_path") or config.TEMP_DIR / f"{s_drop_id}_{fn}")
                if not local_p.exists():
                    local_p = Path(session.get("download_path") or "")

                is_video = (s_data.get("media_type") == "video") or Path(fn).suffix.lower() in VIDEO_EXTENSIONS
                raw_dur = 0.0
                raw_sz_mb = (local_p.stat().st_size / (1024 * 1024)) if local_p.exists() else (raw_sz / (1024 * 1024))
                if is_video and local_p.exists():
                    tech = inspect_technical_metadata(local_p)
                    raw_dur = float(tech.get("duration_sec", 0) or 0)
                    if raw_dur <= 0:
                        raw_dur = await get_video_duration_async(local_p)

                # اگر ویدیو طولانی‌تر از ۲۵ دقیقه (۱۵۰۰ ثانیه) یا حجیم‌تر از ۱۲۰ مگابایت باشد،
                # برای جلوگیری از افت شدید کیفیت، خودکار به پارت‌های ۲۵ دقیقه‌ای تقسیم می‌شود.
                needs_auto_split = (destination == "bale") and is_video and (raw_dur > 1500 or raw_sz_mb > 120.0)

                if needs_auto_split and bale_adapter:
                    target_chat = bale_adapter.get_admin_chat_id()
                    if not target_chat:
                        logger.error("[BatchQueue] Bale target chat not configured")
                        break

                    if raw_dur > 1500:
                        num_parts = max(2, math.ceil(raw_dur / 1500))
                    else:
                        num_parts = max(2, math.ceil(raw_sz_mb / 45.0))

                    await _update_status(
                        f"✂️ <b>فایل {idx} از {total_count} حجیم است ({raw_sz_mb:.1f}MB | {int(raw_dur // 60)} دقیقه)</b>\n"
                        f"⚙️ در حال تقسیم هوشمند به {num_parts} پارت باکیفیت..."
                    )

                    raw_cap, _, effective_mb = await get_bale_compression_settings()
                    split_parts = await SmartVideoSplitter.split_video_async(
                        local_p,
                        num_parts=num_parts,
                        target_max_mb=effective_mb,
                        progress_callback=_update_status
                    )

                    if not split_parts:
                        logger.error(f"[BatchQueue] Auto-split failed for {local_p}")
                        continue

                    split_success = 0
                    for p_idx, part_file in enumerate(split_parts, 1):
                        part_name = clean_public_filename(fn, is_split_part=True, part_idx=p_idx, total_parts=len(split_parts))
                        caption_part = f"🎬 <b>{part_name}</b>"
                        part_bytes = part_file.stat().st_size
                        tot_part_mb = part_bytes / (1024 * 1024)

                        async def _part_progress(curr: int, total: int):
                            pct = min(99, max(1, int((curr / total) * 100))) if total > 0 else 0
                            cur_mb = curr / (1024 * 1024)
                            prog_msg = (
                                f"📦 <b>فایل {idx} از {total_count} (پارت {p_idx} از {len(split_parts)}):</b> <code>{_make_bar(pct)}</code>\n"
                                f"🎬 <b>{part_name}</b>\n"
                                f"🚢 در حال بارگذاری در بله ({cur_mb:.1f} از {tot_part_mb:.1f} MB)..."
                            )
                            await _update_status(prog_msg)

                        t_spec = inspect_technical_metadata(part_file)
                        res = await bale_adapter.send_video(
                            target_chat,
                            part_file,
                            filename=part_name,
                            caption=caption_part,
                            duration=t_spec.get("duration_sec"),
                            width=t_spec.get("width"),
                            height=t_spec.get("height"),
                            progress_callback=_part_progress
                        )
                        if res.get("ok"):
                            split_success += 1

                    if split_success == len(split_parts):
                        success_count += 1
                        await _update_status(
                            f"📦 <b>فایل {idx} از {total_count}:</b> <code>{_make_bar(100)}</code>\n"
                            f"✅ تمام {len(split_parts)} پارت <b>{fn}</b> با موفقیت منتقل شدند!"
                        )
                    else:
                        if split_success > 0:
                            success_count += 1
                        await _update_status(
                            f"⚠️ {split_success} پارت از {len(split_parts)} پارت <b>{fn}</b> به بله منتقل شد."
                        )
                    await asyncio.sleep(1.0)
                    continue

                # مرحله ۲ (عادی): آماده‌سازی و بهینه‌سازی غیرمسدودکننده
                await _update_status(
                    f"📦 <b>فایل {idx} از {total_count}:</b> <code>{_make_bar(45)}</code>\n"
                    f"📄 <b>{fn}</b>\n"
                    f"⚙️ در حال بهینه‌سازی و بررسی سقف حجم..."
                )

                try:
                    final_p, s_name, t_info = await cls.prepare_for_transfer_async(
                        s_drop_id, destination, progress_callback=_update_status
                    )
                except Exception as prep_err:
                    logger.warning(f"[BatchQueue] Async prep fallback: {prep_err}")
                    final_p, s_name, t_info = cls.prepare_for_transfer(s_drop_id, destination)

                # مرحله ۳: ارسال ترتیبی به پلتفرم مقصد با نوار پیشرفت زنده
                clean_s_name = clean_public_filename(s_name, is_split_part=False)
                media_type = s_data.get("media_type")
                if media_type == "video":
                    file_emoji = "🎬"
                elif media_type == "audio":
                    file_emoji = "🎧"
                else:
                    file_emoji = "📄"

                # مرحله ۳: ارسال ترتیبی به پلتفرم مقصد با نوار پیشرفت زنده
                await _update_status(
                    f"📦 <b>فایل {idx} از {total_count}:</b> <code>{_make_bar(75)}</code>\n"
                    f"{file_emoji} <b>{clean_s_name}</b>\n"
                    f"🚢 در حال ارسال به {dest_name}..."
                )

                try:
                    if destination == "bale" and bale_adapter:
                        target_chat = bale_adapter.get_admin_chat_id()
                        if not target_chat:
                            logger.error("[BatchQueue] Bale target chat not configured")
                            break
                        caption_clean = f"{file_emoji} <b>{clean_s_name}</b>"

                        # کال‌بک تراتل‌شده پیشرفت ارسال در پیام‌رسان بله
                        async def _batch_progress(curr: int, total: int):
                            pct = min(99, max(1, int((curr / total) * 100))) if total > 0 else 0
                            cur_mb = curr / (1024 * 1024)
                            tot_mb = total / (1024 * 1024)
                            prog_msg = (
                                f"📦 <b>فایل {idx} از {total_count}:</b> <code>{_make_bar(pct)}</code>\n"
                                f"{file_emoji} <b>{clean_s_name}</b>\n"
                                f"🚢 در حال بارگذاری در بله ({cur_mb:.1f} از {tot_mb:.1f} MB)..."
                            )
                            await _update_status(prog_msg)

                        if media_type == "video":
                            t_spec = inspect_technical_metadata(final_p)
                            res = await bale_adapter.send_video(
                                target_chat,
                                final_p,
                                filename=clean_s_name,
                                caption=caption_clean,
                                duration=t_spec.get("duration_sec"),
                                width=t_spec.get("width"),
                                height=t_spec.get("height"),
                                progress_callback=_batch_progress
                            )
                        elif media_type == "audio":
                            res = await bale_adapter.send_audio(
                                target_chat,
                                final_p,
                                filename=clean_s_name,
                                title=t_info.get("title"),
                                performer=None,
                                caption=caption_clean,
                                progress_callback=_batch_progress
                            )
                        else:
                            res = await bale_adapter.send_document(
                                target_chat,
                                final_p,
                                filename=clean_s_name,
                                caption=caption_clean,
                                progress_callback=_batch_progress
                            )
                        if res.get("ok"):
                            success_count += 1
                    elif destination == "rubika" and rubika_adapter:
                        target_chat = rubika_adapter.get_admin_guid()
                        res = await rubika_adapter.send_audio_bot_api(target_chat, final_p, caption=f"{file_emoji} {clean_s_name}")
                        if res.get("ok") or res.get("status") == "OK":
                            success_count += 1
                except Exception as send_err:
                    logger.error(f"[BatchQueue] Error sending item {idx}: {send_err}")

                # اعلام اتمام پردازش فایل جاری
                await _update_status(
                    f"📦 <b>فایل {idx} از {total_count}:</b> <code>{_make_bar(100)}</code>\n"
                    f"✅ <b>{clean_s_name}</b> با موفقیت به {dest_name} منتقل شد!"
                )
                await asyncio.sleep(1.0)

            return {
                "total": total_count,
                "success": success_count,
                "destination": dest_name
            }

        return await cls.batch_queue.enqueue(_job)
