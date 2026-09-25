# -*- coding: utf-8 -*-
"""
ماژول اختصاصی فشرده‌سازی و تقسیم هوشمند رسانه‌ها (Smart Media Compressor & Splitter)
این ماژول وظیفه فشرده‌سازی غیرمسدودکننده صوت و تصویر، مهار فریزهای طولانی رویدادهای Asyncio،
گزارش زنده پیشرفت FFmpeg هر ۳ ثانیه، و مدیریت هوشمند تقسیم ویدیو به پارت‌های ایمن را بر عهده دارد.
"""

import os
import sys
import math
import time
import asyncio
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple, Callable, List, Dict, Any
from core.config import config
from core.logger import get_logger
from media.inspector import inspect_technical_metadata
from media.tagger import copy_all_id3_tags

logger = get_logger("compressor")

# سقف ایمن مگابایتی برای پارت‌های ویدیویی بله (حاشیه امن ۴۵ مگابایت جهت مهار خطای ۴۱۳ Nginx)
SAFE_BALE_PART_LIMIT_MB: float = 45.0


def format_compression_progress(
    part_idx: Optional[int] = None,
    total_parts: Optional[int] = None,
    percent: float = 0.0,
    speed: float | str = "1.0x",
    eta_str: str = "00:00",
    orig_mb: float = 0.0,
    est_mb: float = 0.0
) -> str:
    """
    قالب‌بندی استاندارد و زیبای پیشرفت فشرده‌سازی هوشمند ویدیو در تلگرام.
    """
    bar_length = 10
    pct = min(100.0, max(0.0, float(percent)))
    filled = int(bar_length * pct // 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    spd_str = f"{float(speed):.1f}x" if (isinstance(speed, (int, float)) or (isinstance(speed, str) and speed.replace('.', '', 1).isdigit())) else str(speed)
    p_str = f" (بخش {part_idx} از {total_parts})" if (part_idx and total_parts and int(total_parts) > 1) else ""
    return (
        f"⚙️ <b>فشرده‌سازی هوشمند ویدیو{p_str}</b>\n\n"
        f"<code>[{bar}] {pct:.1f}%</code>\n\n"
        f"⏱ <b>باقیمانده:</b> <code>{eta_str}</code> | ⚡️ <b>سرعت:</b> <code>{spd_str}</code>\n"
        f"📦 <b>حجم:</b> <code>{orig_mb:.1f} MB</code> ➔ 🎯 <b>تخمین:</b> <code>{est_mb:.1f} MB</code>"
    )


def _format_video_progress_msg(
    pct: int,
    speed: str,
    remaining_sec: float,
    orig_mb: float,
    target_mb: float,
    part_info: Optional[str] = None
) -> str:
    """
    فرمت‌بندی پیام گزارش زنده فشرده‌سازی هوشمند ویدیو با نوار پیشرفت استاندارد.
    """
    import re
    m, s = divmod(int(max(0, remaining_sec)), 60)
    h, m = divmod(m, 60)
    eta_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

    p_idx, total_p = None, None
    if part_info:
        m_parts = re.search(r'(\d+)\s*(?:از|of|/)\s*(\d+)', str(part_info))
        if m_parts:
            p_idx, total_p = int(m_parts.group(1)), int(m_parts.group(2))

    return format_compression_progress(
        part_idx=p_idx,
        total_parts=total_p,
        percent=float(pct),
        speed=speed,
        eta_str=eta_str,
        orig_mb=orig_mb,
        est_mb=target_mb
    )


async def get_video_duration_async(file_path: str | Path) -> float:
    """
    سنجش دقیق مدت‌زمان فایل ویدیویی بر حسب ثانیه با ffprobe پیش از ورود به محاسبات فشرده‌سازی.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(file_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        val = float(stdout.decode().strip())
        if val > 0:
            return val
    except Exception:
        pass

    try:
        tech = inspect_technical_metadata(Path(file_path))
        return float(tech.get("duration_sec", 0) or 0.0)
    except Exception:
        return 0.0


def get_video_duration_sync(file_path: str | Path) -> float:
    """نسخه همگام سنجش مدت‌زمان ویدیو با ffprobe"""
    try:
        res = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(file_path)],
            capture_output=True, text=True, timeout=10
        )
        val = float(res.stdout.strip())
        if val > 0:
            return val
    except Exception:
        pass

    try:
        tech = inspect_technical_metadata(Path(file_path))
        return float(tech.get("duration_sec", 0) or 0.0)
    except Exception:
        return 0.0


class SmartAudioCompressor:
    """کلاس مدیریت فشرده‌سازی هوشمند فایل‌های صوتی بر مبنای سقف حجم مجاز پیام‌رسان‌ها"""

    @staticmethod
    def calculate_target_bitrate(
        duration_sec: float,
        target_max_bytes: int,
        initial_bitrate_kbps: int = 320
    ) -> int:
        if duration_sec <= 0:
            return 128
        safe_bytes = target_max_bytes * 0.95
        calc_kbps = int((safe_bytes * 8) / (duration_sec * 1000))
        calc_kbps = min(initial_bitrate_kbps, calc_kbps)
        calc_kbps = max(24, min(320, calc_kbps))
        return calc_kbps

    @staticmethod
    def get_audio_duration(file_path: Path) -> float:
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(str(file_path))
            if audio and audio.info and getattr(audio.info, "length", None):
                return float(audio.info.length)
        except Exception:
            pass
        tech = inspect_technical_metadata(file_path)
        return float(tech.get("duration_sec", 0) or 0)

    @staticmethod
    def compress_if_needed(
        file_path: str | Path,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[Path, int, int, int, bool]:
        """
        فشرده‌سازی فایل‌های صوتی حجیم به فرمت استاندارد MP3 با رعایت سقف حجم مجاز.
        """
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"File not found: {src}")

        initial_size = src.stat().st_size
        safe_limit_mb = float(getattr(config, "MAX_SAFE_BALE_SIZE_MB", 49.99))
        target_mb = max(1.0, round(safe_limit_mb - 1.5, 2))
        max_safe_bytes = int(safe_limit_mb * 1024 * 1024)
        target_max_bytes = int(target_mb * 1024 * 1024)

        if initial_size <= max_safe_bytes:
            tech = inspect_technical_metadata(src)
            return src, initial_size, initial_size, tech.get("bitrate_kbps", 128), False

        if progress_callback:
            orig_size_mb = f"{initial_size / (1024 * 1024):.1f}"
            try:
                progress_callback(
                    "⚙️ <b>در حال فشرده‌سازی هوشمند صوت...</b>\n"
                    f"📦 حجم فعلی: <code>{orig_size_mb} MB</code> ➔ هدف: <code>زیر {target_mb} MB</code>\n"
                    "⚙️ فرآیند بهینه‌سازی صدا در حال اجراست، لطفاً شکیبا باشید..."
                )
            except Exception:
                pass

        dur = SmartAudioCompressor.get_audio_duration(src)
        tech = inspect_technical_metadata(src)
        init_bitrate = int(tech.get("bitrate_kbps", 320) or 320)

        target_bitrate = SmartAudioCompressor.calculate_target_bitrate(
            duration_sec=dur,
            target_max_bytes=target_max_bytes,
            initial_bitrate_kbps=init_bitrate
        )

        out_path = config.TEMP_DIR / f"compressed_{src.stem}.mp3"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", f"{target_bitrate}k",
            "-ar", "44100"
        ]
        if target_bitrate < 64:
            cmd.extend(["-ac", "1"])

        cmd.append(str(out_path))

        logger.info(f"Running smart audio compression: {target_bitrate}k on {src.name} -> {out_path.name}")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if res.returncode != 0 or not out_path.exists():
            logger.error(f"FFmpeg audio compression failed: {res.stderr}")
            raise RuntimeError("خطا در فشرده‌سازی فایل صوتی با FFmpeg.")

        final_size = out_path.stat().st_size

        if final_size > max_safe_bytes and target_bitrate > 32:
            adjusted_bitrate = max(24, int(target_bitrate * 0.88))
            cmd_adj = [
                "ffmpeg", "-y", "-i", str(src),
                "-vn", "-c:a", "libmp3lame",
                "-b:a", f"{adjusted_bitrate}k",
                "-ar", "44100"
            ]
            if adjusted_bitrate < 64:
                cmd_adj.extend(["-ac", "1"])
            cmd_adj.append(str(out_path))
            subprocess.run(cmd_adj, capture_output=True, text=True, timeout=300)
            final_size = out_path.stat().st_size

        if final_size > max_safe_bytes:
            if out_path.exists():
                out_path.unlink()
            raise RuntimeError("امکان رساندن این فایل صوتی به حجم زیر ۵۰ مگابایت با حفظ کیفیت قابل قبول وجود نداشت.")

        try:
            copy_all_id3_tags(src, out_path)
        except Exception as e:
            logger.warning(f"Could not copy ID3 tags to compressed file: {e}")

        logger.info(
            f"Smart audio compression complete: initial={initial_size/(1024*1024):.2f}MB -> "
            f"final={final_size/(1024*1024):.2f}MB at {target_bitrate}kbps."
        )

        return out_path, initial_size, final_size, target_bitrate, True

    compress_if_needed_sync = compress_if_needed


class SmartVideoCompressor:
    """
    کلاس فشرده‌سازی هوشمند ویدیو با معماری کاملاً غیرمسدودکننده (True Async FFmpeg).
    از قفل شدن حلقه رویدادهای Asyncio جلوگیری کرده و پروگرس‌بار زنده را هر ۳ ثانیه به پیام‌رسان‌ها می‌فرستد.
    """

    @staticmethod
    def calculate_target_video_bitrate(
        duration_sec: float,
        target_max_bytes: int,
        audio_bitrate_kbps: int = 96
    ) -> int:
        if duration_sec <= 0:
            return 800
        safe_bytes = target_max_bytes * 0.96
        total_kbps = int((safe_bytes * 8) / (duration_sec * 1000))
        video_kbps = max(64, total_kbps - audio_bitrate_kbps)
        return video_kbps

    @staticmethod
    async def _execute_ffmpeg_progress_async(
        cmd: List[str],
        duration_sec: float,
        orig_mb: float,
        target_mb: float,
        progress_callback: Optional[Callable[[str], Any]] = None,
        part_info: Optional[str] = None,
        timeout_sec: int = 900
    ) -> None:
        """
        اجرای کاملاً آسنکرون و غیرمسدودکننده FFmpeg با استفاده از asyncio.create_subprocess_exec.
        پارس خطوط خروجی پایپ و ارسال لحظه‌ای درصد، سرعت و زمان باقی‌مانده با تراتل هر ۳ ثانیه.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        except Exception as spawn_err:
            logger.error(f"Failed to spawn FFmpeg async subprocess: {spawn_err}")
            raise RuntimeError(f"خطا در آغاز پردازش FFmpeg: {spawn_err}")

        last_update = time.time()
        speed = "1.0x"
        speed_val = 1.0
        current_sec = 0.0

        if proc.stdout:
            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                if "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip()
                    if k == "out_time_us":
                        try:
                            current_sec = int(v) / 1_000_000.0
                        except Exception:
                            pass
                    elif k == "out_time_ms":
                        try:
                            current_sec = int(v) / 1_000.0
                        except Exception:
                            pass
                    elif k == "speed":
                        speed = v
                        try:
                            speed_val = float(v.replace("x", "").strip())
                        except Exception:
                            speed_val = 1.0
                    elif k == "out_time":
                        try:
                            t_parts = v.split(":")
                            if len(t_parts) == 3:
                                current_sec = float(t_parts[0]) * 3600 + float(t_parts[1]) * 60 + float(t_parts[2])
                        except Exception:
                            pass
                    elif k == "progress" and v == "end":
                        current_sec = duration_sec

                now = time.time()
                if progress_callback and (now - last_update >= 3.0) and duration_sec > 0:
                    last_update = now
                    pct = min(99, max(1, int((current_sec / duration_sec) * 100)))
                    rem_sec = max(0, int((duration_sec - current_sec) / max(0.1, speed_val)))
                    msg = _format_video_progress_msg(
                        pct=pct,
                        speed=speed,
                        remaining_sec=rem_sec,
                        orig_mb=orig_mb,
                        target_mb=target_mb,
                        part_info=part_info
                    )
                    try:
                        res = progress_callback(msg)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception as cb_err:
                        logger.debug(f"Progress callback non-fatal error: {cb_err}")

        try:
            _, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=float(timeout_sec))
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise TimeoutError("پردازش فشرده‌سازی ویدیوی FFmpeg به دلیل طولانی شدن زمان متوقف شد.")

        if proc.returncode != 0:
            err_text = stderr_bytes.decode("utf-8", errors="ignore") if stderr_bytes else "Unknown FFmpeg error"
            logger.error(f"FFmpeg process error (code {proc.returncode}): {err_text}")
            raise RuntimeError(f"خطا در فشرده‌سازی ویدیو با FFmpeg (کد {proc.returncode}).")

    @staticmethod
    def _execute_ffmpeg_progress(
        cmd: List[str],
        duration_sec: float,
        orig_mb: float,
        target_mb: float,
        progress_callback: Optional[Callable[[str], None]] = None,
        part_info: Optional[str] = None,
        timeout_sec: int = 600
    ) -> None:
        """اجرای همگام fallback برای محیط‌های خارج از حلقه رویدادهای asyncio"""
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
        except Exception as spawn_err:
            logger.error(f"Failed to spawn FFmpeg sync: {spawn_err}")
            raise RuntimeError(f"خطا در اجرای پردازش FFmpeg: {spawn_err}")

        last_update = time.time()
        speed = "1.0x"
        speed_val = 1.0
        current_sec = 0.0

        if proc.stdout:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip()
                    if k == "out_time_us":
                        try:
                            current_sec = int(v) / 1_000_000.0
                        except Exception:
                            pass
                    elif k == "out_time_ms":
                        try:
                            current_sec = int(v) / 1_000.0
                        except Exception:
                            pass
                    elif k == "speed":
                        speed = v
                        try:
                            speed_val = float(v.replace("x", "").strip())
                        except Exception:
                            speed_val = 1.0
                    elif k == "out_time":
                        try:
                            t_parts = v.split(":")
                            if len(t_parts) == 3:
                                current_sec = float(t_parts[0]) * 3600 + float(t_parts[1]) * 60 + float(t_parts[2])
                        except Exception:
                            pass
                    elif k == "progress" and v == "end":
                        current_sec = duration_sec

                now = time.time()
                if progress_callback and (now - last_update >= 3.0) and duration_sec > 0:
                    last_update = now
                    pct = min(99, max(1, int((current_sec / duration_sec) * 100)))
                    rem_sec = max(0, int((duration_sec - current_sec) / max(0.1, speed_val)))
                    msg = _format_video_progress_msg(
                        pct=pct,
                        speed=speed,
                        remaining_sec=rem_sec,
                        orig_mb=orig_mb,
                        target_mb=target_mb,
                        part_info=part_info
                    )
                    try:
                        progress_callback(msg)
                    except Exception:
                        pass

        try:
            _, stderr_data = proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise TimeoutError("پردازش فشرده‌سازی ویدیوی FFmpeg به دلیل طولانی شدن زمان متوقف شد.")

        if proc.returncode != 0:
            logger.error(f"FFmpeg sync error (code {proc.returncode}): {stderr_data}")
            raise RuntimeError("خطا در فشرده‌سازی ویدیو با FFmpeg.")

    @classmethod
    async def compress_if_needed(
        cls,
        file_path: str | Path,
        progress_callback: Optional[Callable[[str], Any]] = None,
        target_max_mb: Optional[float] = None,
        part_info: Optional[str] = None
    ) -> Tuple[Path, int, int, int, bool]:
        """
        فشرده‌سازی هوشمند غیرمسدودکننده ویدیو.
        اگر حجم فایل از سقف مجاز بیشتر باشد، با بهینه‌سازی بیت‌ریت و انکود سبک ultrafast حجم آن را زیر سقف می‌آورد.
        """
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"File not found: {src}")

        initial_size = src.stat().st_size
        if target_max_mb is not None:
            safe_limit_mb = float(target_max_mb)
        else:
            safe_limit_mb = float(getattr(config, "MAX_SAFE_BALE_SIZE_MB", 49.99))

        target_mb = max(1.0, round(safe_limit_mb - 1.5, 2))
        max_safe_bytes = int(safe_limit_mb * 1024 * 1024)
        target_max_bytes = int(target_mb * 1024 * 1024)

        if initial_size <= max_safe_bytes:
            tech = inspect_technical_metadata(src)
            return src, initial_size, initial_size, tech.get("bitrate_kbps", 800), False

        # پروب دقیق مدت زمان با ffprobe به جای تکیه بر اطلاعات فرضی یا والد
        dur = await get_video_duration_async(src)
        if dur <= 0:
            tech = inspect_technical_metadata(src)
            dur = float(tech.get("duration_sec", 0) or 0)
        audio_kbps = 64 if dur > 1800 else 96
        target_v_bitrate = cls.calculate_target_video_bitrate(
            dur, target_max_bytes, audio_bitrate_kbps=audio_kbps
        )

        out_path = config.TEMP_DIR / f"compressed_{src.stem}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        v_scale = "scale='min(854,iw)':-2" if (target_v_bitrate < 600 or dur > 600) else "scale='min(1280,iw)':-2"
        orig_mb = initial_size / (1024 * 1024)

        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-c:v", "libx264",
            "-preset", "faster",
            "-crf", "23",
            "-threads", "0",
            "-b:v", f"{target_v_bitrate}k",
            "-maxrate", f"{int(target_v_bitrate * 1.15)}k",
            "-bufsize", f"{int(target_v_bitrate * 2)}k",
            "-c:a", "copy",
            "-vf", v_scale,
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-nostats",
            str(out_path)
        ]

        logger.info(f"Running async video compression: target_v={target_v_bitrate}k on {src.name} -> {out_path.name}")

        await cls._execute_ffmpeg_progress_async(
            cmd=cmd,
            duration_sec=dur,
            orig_mb=orig_mb,
            target_mb=target_mb,
            progress_callback=progress_callback,
            part_info=part_info,
            timeout_sec=900
        )

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError("خطا در فشرده‌سازی ویدیو با FFmpeg: فایل خروجی تولید نشد.")

        final_size = out_path.stat().st_size

        if final_size > max_safe_bytes and target_v_bitrate > 100:
            adj_v = max(64, int(target_v_bitrate * 0.88))
            v_adj_scale = "scale='min(640,iw)':-2" if (adj_v < 400 or dur > 600) else "scale='min(854,iw)':-2"
            cmd_adj = [
                "ffmpeg", "-y", "-i", str(src),
                "-c:v", "libx264",
                "-preset", "faster",
                "-crf", "23",
                "-threads", "0",
                "-b:v", f"{adj_v}k",
                "-maxrate", f"{int(adj_v * 1.15)}k",
                "-bufsize", f"{int(adj_v * 2)}k",
                "-c:a", "copy",
                "-vf", v_adj_scale,
                "-movflags", "+faststart",
                "-progress", "pipe:1",
                "-nostats",
                str(out_path)
            ]
            await cls._execute_ffmpeg_progress_async(
                cmd=cmd_adj,
                duration_sec=dur,
                orig_mb=orig_mb,
                target_mb=target_mb,
                progress_callback=progress_callback,
                part_info=part_info,
                timeout_sec=900
            )
            final_size = out_path.stat().st_size

        logger.info(
            f"Video compression complete: initial={initial_size/(1024*1024):.2f}MB -> "
            f"final={final_size/(1024*1024):.2f}MB"
        )
        return out_path, initial_size, final_size, target_v_bitrate, True

    @classmethod
    def compress_if_needed_sync(
        cls,
        file_path: str | Path,
        progress_callback: Optional[Callable[[str], None]] = None,
        target_max_mb: Optional[float] = None,
        part_info: Optional[str] = None
    ) -> Tuple[Path, int, int, int, bool]:
        """نسخه همگام فشرده‌سازی جهت حفظ سازگاری در کدهای سنکرون"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # در صورتی که در ترد اصلی با حلقه فعال باشیم، در executor فراخوانی می‌شود
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                def _run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            cls.compress_if_needed(file_path, progress_callback, target_max_mb, part_info)
                        )
                    finally:
                        new_loop.close()
                return pool.submit(_run_in_new_loop).result()
        else:
            return asyncio.run(cls.compress_if_needed(file_path, progress_callback, target_max_mb, part_info))

    @staticmethod
    def precalculate_video_quality(
        file_path: str | Path,
        target_max_mb: float = SAFE_BALE_PART_LIMIT_MB
    ) -> Dict[str, Any]:
        """
        محاسبه پیش از پردازش (Pre-Calculation):
        سنجش کیفیت تقریبی خروجی ویدیو بر اساس مدت‌زمان و سقف بله، قبل از ورود به پردازش سنگین FFmpeg.
        """
        src = Path(file_path)
        if not src.exists():
            return {
                "duration_sec": 0, "target_v_bitrate": 800,
                "estimated_resolution": "720p", "severe_quality_drop": False,
                "recommended_parts": 2, "initial_size_mb": 0.0
            }

        tech = inspect_technical_metadata(src)
        dur = float(tech.get("duration_sec", 0) or 0)
        file_sz = src.stat().st_size
        init_mb = round(file_sz / (1024 * 1024), 2)

        target_max_bytes = int(target_max_mb * 1024 * 1024)
        if init_mb <= target_max_mb:
            return {
                "duration_sec": dur,
                "target_v_bitrate": 2000,
                "estimated_resolution": "Original",
                "severe_quality_drop": False,
                "recommended_parts": 1,
                "initial_size_mb": init_mb
            }

        audio_kbps = 64 if dur > 1800 else 96
        target_v_bitrate = SmartVideoCompressor.calculate_target_video_bitrate(
            dur, target_max_bytes, audio_bitrate_kbps=audio_kbps
        )

        if target_v_bitrate < 250:
            est_res = "240p"
            severe_drop = True
        elif target_v_bitrate < 450:
            est_res = "360p"
            severe_drop = True
        elif target_v_bitrate < 750:
            est_res = "480p"
            severe_drop = False
        else:
            est_res = "720p"
            severe_drop = False

        if dur >= 900 and target_v_bitrate < 600:
            severe_drop = True
            if est_res == "480p":
                est_res = "360p"

        rec_parts = max(2, math.ceil(init_mb / target_max_mb)) if init_mb > target_max_mb else 2

        return {
            "duration_sec": dur,
            "target_v_bitrate": target_v_bitrate,
            "estimated_resolution": est_res,
            "severe_quality_drop": severe_drop,
            "recommended_parts": rec_parts,
            "initial_size_mb": init_mb
        }

    # متدهای سنجش دقیق مدت زمان با ffprobe
    get_video_duration_async = staticmethod(get_video_duration_async)
    get_video_duration = staticmethod(get_video_duration_async)
    get_video_duration_sync = staticmethod(get_video_duration_sync)

    # نام مستعار جهت سازگاری و جلوگیری از خطای AttributeError
    compress_video = compress_if_needed
    compress_video_sync = compress_if_needed_sync


class SmartVideoSplitter:
    """
    کلاس مدیریت تقسیم هوشمند ویدیو به پارت‌های باکیفیت و ایمن
    با پشتیبانی کامل از اجرای غیرمسدودکننده (Async FFmpeg) و فشرده‌سازی ثانویه خودکار.
    """

    @classmethod
    async def split_single_part_async(
        cls,
        file_path: str | Path,
        part_index: int,
        num_parts: int,
        total_duration: float
    ) -> Path:
        """
        برش و استخراج یک پارت منفرد از ویدیو به صورت کاملاً غیرمسدودکننده با استفاده از Stream Copy سریع
        یا انکود سبک Ultrafast در صورت عدم پشتیبانی کپی جریان.
        """
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"Input video not found: {file_path}")

        if total_duration <= 0:
            total_duration = await get_video_duration_async(src)
            if total_duration <= 0:
                total_duration = 600.0

        part_duration = total_duration / num_parts
        start_sec = (part_index - 1) * part_duration
        out_p = config.TEMP_DIR / f"{src.stem}_part{part_index}of{num_parts}{src.suffix}"
        out_p.parent.mkdir(parents=True, exist_ok=True)

        cmd_copy = [
            "ffmpeg", "-y",
            "-ss", f"{start_sec:.2f}",
            "-t", f"{part_duration:.2f}",
            "-i", str(src),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(out_p)
        ]
        logger.info(f"Splitting single part {part_index}/{num_parts} (copy): {cmd_copy}")

        proc = await asyncio.create_subprocess_exec(
            *cmd_copy,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

        if proc.returncode != 0 or not out_p.exists() or out_p.stat().st_size < 1000:
            logger.warning(f"Stream copy split failed for part {part_index}, falling back to fast encode...")
            cmd_enc = [
                "ffmpeg", "-y",
                "-ss", f"{start_sec:.2f}",
                "-t", f"{part_duration:.2f}",
                "-i", str(src),
                "-c:v", "libx264",
                "-preset", "faster",
                "-crf", "23",
                "-threads", "0",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(out_p)
            ]
            proc_enc = await asyncio.create_subprocess_exec(
                *cmd_enc,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc_enc.communicate()

        return out_p

    @classmethod
    async def split_video_async(
        cls,
        file_path: str | Path,
        num_parts: Optional[int] = None,
        target_max_mb: float = SAFE_BALE_PART_LIMIT_MB,
        progress_callback: Optional[Callable[[str], Any]] = None
    ) -> List[Path]:
        """
        تقسیم آسنکرون و غیرمسدودکننده ویدیو به تعداد پارت‌های مورد نظر.
        هر پارت تولیدشده بررسی می‌شود و در صورت فراتر رفتن از ۴۸.۵ مگابایت،
        به صورت خودکار تا ۴۵ مگابایت فشرده می‌شود تا سقف بله تضمین گردد.
        """
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"Input video not found: {file_path}")

        file_sz = src.stat().st_size
        total_mb = file_sz / (1024 * 1024)

        if num_parts is not None and int(num_parts) >= 2:
            num_parts = int(num_parts)
            logger.info(f"SmartVideoSplitter async: User specified manual parts = {num_parts} for {total_mb:.1f}MB")
        else:
            num_parts = max(2, math.ceil(total_mb / target_max_mb))
            logger.info(f"SmartVideoSplitter async: Auto-calculated parts = {num_parts} for {total_mb:.1f}MB")

        dur = await get_video_duration_async(src)
        if dur <= 0:
            tech = inspect_technical_metadata(src)
            dur = float(tech.get("duration_sec", 0) or 0)
        if dur <= 0:
            dur = 600.0

        output_files: List[Path] = []

        if progress_callback:
            try:
                res = progress_callback(
                    f"✂️ <b>در حال تقسیم هوشمند ویدیو به {num_parts} پارت باکیفیت (هر پارت زیر {target_max_mb:.0f}MB)...</b>"
                )
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

        for i in range(1, num_parts + 1):
            out_p = await cls.split_single_part_async(src, i, num_parts, dur)

            if out_p.exists() and out_p.stat().st_size > 0:
                part_sz_mb = out_p.stat().st_size / (1024 * 1024)
                if part_sz_mb > target_max_mb:
                    logger.info(f"Split part {out_p.name} ({part_sz_mb:.1f}MB) exceeds target {target_max_mb:.1f}MB, auto-compressing...")
                    comp_out, _, _, _, ok = await SmartVideoCompressor.compress_if_needed(
                        out_p,
                        target_max_mb=target_max_mb,
                        part_info=f"پارت {i} از {num_parts}",
                        progress_callback=progress_callback
                    )
                    if ok and comp_out and comp_out.exists() and comp_out.stat().st_size > 0:
                        try:
                            out_p.unlink(missing_ok=True)
                            comp_out.rename(out_p)
                        except Exception as e:
                            logger.warning(f"Could not replace part with compressed: {e}")
                            out_p = comp_out
                output_files.append(out_p)
            else:
                logger.error(f"Failed to generate part {i} of {src.name}")

        return output_files

    @classmethod
    def split_video(
        cls,
        file_path: str | Path,
        num_parts: Optional[int] = None,
        target_max_mb: float = SAFE_BALE_PART_LIMIT_MB,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Path]:
        """پوشش همگام (Sync wrapper) جهت حفظ سازگاری کامل با کدهای قبلی"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                def _run_split():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            cls.split_video_async(file_path, num_parts, target_max_mb, progress_callback)
                        )
                    finally:
                        new_loop.close()
                return pool.submit(_run_split).result()
        else:
            return asyncio.run(cls.split_video_async(file_path, num_parts, target_max_mb, progress_callback))


def convert_audio_to_mp3_if_needed(file_path: str | Path) -> Tuple[Path, bool]:
    """تبدیل خودکار فرمت‌های غیر mp3 به فرمت استاندارد MP3 با FFmpeg جهت رفع خطای سرورهای روبیکا"""
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(f"File not found: {src}")

    if src.suffix.lower() == ".mp3":
        return src, False

    out_mp3 = config.TEMP_DIR / f"{src.stem}.mp3"
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        "-ar", "44100",
        str(out_mp3)
    ]
    logger.info(f"Auto-converting non-MP3 audio {src.name} to MP3 for Rubika compatibility...")
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if res.returncode == 0 and out_mp3.exists() and out_mp3.stat().st_size > 0:
        try:
            copy_all_id3_tags(src, out_mp3)
        except Exception:
            pass
        return out_mp3, True

    logger.warning(f"Audio to MP3 conversion failed, fallback to original: {res.stderr}")
    return src, False
