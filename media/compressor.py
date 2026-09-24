import math
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

class SmartAudioCompressor:
    @staticmethod
    def calculate_target_bitrate(
        duration_sec: float,
        target_max_bytes: int,
        initial_bitrate_kbps: int = 320
    ) -> int:
        if duration_sec <= 0:
            return 128
        # Calculate raw bitrate in kbps for target size with 5% safety margin
        safe_bytes = target_max_bytes * 0.95
        calc_kbps = int((safe_bytes * 8) / (duration_sec * 1000))
        # Clamp to realistic range
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
        Compresses any audio format (mp3, m4a, aac, wav, flac, ogg, etc.) 
        if file size exceeds MAX_SAFE_BALE_SIZE_BYTES (default ~49MB).
        Returns:
            (final_file_path, initial_size_bytes, final_size_bytes, final_bitrate_kbps, was_compressed)
        """
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"File not found: {src}")

        initial_size = src.stat().st_size
        safe_limit_mb = float(getattr(config, "MAX_SAFE_BALE_SIZE_MB", 49.99))
        target_mb = max(1.0, round(safe_limit_mb - 1.5, 2))
        max_safe_bytes = int(safe_limit_mb * 1024 * 1024)
        target_max_bytes = int(target_mb * 1024 * 1024)

        # If file is already within safe limit, do not compress
        if initial_size <= max_safe_bytes:
            tech = inspect_technical_metadata(src)
            return src, initial_size, initial_size, tech.get("bitrate_kbps", 128), False

        # File exceeds safe limit -> Run Smart Compression
        if progress_callback:
            orig_size_mb = f"{initial_size / (1024 * 1024):.1f}"
            progress_callback(
                "⚙️ <b>در حال فشرده‌سازی هوشمند...</b>\n"
                f"📦 حجم فعلی: <code>{orig_size_mb} MB</code> ➔ هدف: <code>زیر {target_mb} MB</code>\n"
                "⚙️ فرآیند بهینه‌سازی صدا و تصویر در حال اجراست، لطفاً شکیبا باشید..."
            )

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

        # Step 1: Optimize Bitrate using FFmpeg with standard MP3 output for universal player compatibility
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

        logger.info(f"Running smart compression: target_bitrate={target_bitrate}k on {src.name} -> {out_path.name}")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if res.returncode != 0 or not out_path.exists():
            logger.error(f"FFmpeg compression failed: {res.stderr}")
            raise RuntimeError("خطا در فشرده‌سازی فایل صوتی با FFmpeg.")

        final_size = out_path.stat().st_size

        # If output is still slightly above safe limit, reduce bitrate and re-encode
        if final_size > max_safe_bytes and target_bitrate > 32:
            adjusted_bitrate = max(24, int(target_bitrate * 0.88))
            logger.info(f"Re-adjusting compression with lower bitrate {adjusted_bitrate}k...")
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

        # Step 2: Preserve original tags & cover
        try:
            copy_all_id3_tags(src, out_path)
        except Exception as e:
            logger.warning(f"Could not copy ID3 tags to compressed file: {e}")

        logger.info(
            f"Smart compression complete: initial={initial_size/(1024*1024):.2f}MB -> "
            f"final={final_size/(1024*1024):.2f}MB at {target_bitrate}kbps."
        )

        return out_path, initial_size, final_size, target_bitrate, True


class SmartVideoCompressor:
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
    def compress_if_needed(
        file_path: str | Path,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[Path, int, int, int, bool]:
        """
        Compresses any video format (mp4, mkv, avi, mov, etc.) 
        if file size exceeds MAX_SAFE_BALE_SIZE_BYTES (49.99 MB).
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
            return src, initial_size, initial_size, tech.get("bitrate_kbps", 800), False

        if progress_callback:
            orig_size_mb = f"{initial_size / (1024 * 1024):.1f}"
            progress_callback(
                "⚙️ <b>در حال فشرده‌سازی هوشمند...</b>\n"
                f"📦 حجم فعلی: <code>{orig_size_mb} MB</code> ➔ هدف: <code>زیر {target_mb} MB</code>\n"
                "⚙️ فرآیند بهینه‌سازی صدا و تصویر در حال اجراست، لطفاً شکیبا باشید..."
            )

        tech = inspect_technical_metadata(src)
        dur = float(tech.get("duration_sec", 0) or 0)
        audio_kbps = 64 if dur > 1800 else 96
        target_v_bitrate = SmartVideoCompressor.calculate_target_video_bitrate(
            dur, target_max_bytes, audio_bitrate_kbps=audio_kbps
        )

        out_path = config.TEMP_DIR / f"compressed_{src.stem}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Ultrafast preset & dynamic scaling to prevent timeouts on HuggingFace CPU
        v_scale = "scale='min(854,iw)':-2" if (target_v_bitrate < 600 or dur > 600) else "scale='min(1280,iw)':-2"
        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-c:v", "libx264",
            "-b:v", f"{target_v_bitrate}k",
            "-maxrate", f"{int(target_v_bitrate * 1.15)}k",
            "-bufsize", f"{int(target_v_bitrate * 2)}k",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-b:a", f"{audio_kbps}k",
            "-vf", v_scale,
            "-movflags", "+faststart",
            str(out_path)
        ]

        logger.info(f"Running video smart compression: target_v={target_v_bitrate}k, audio={audio_kbps}k on {src.name} -> {out_path.name}")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if res.returncode != 0 or not out_path.exists():
            logger.error(f"FFmpeg video compression failed: {res.stderr}")
            raise RuntimeError("خطا در فشرده‌سازی ویدیو با FFmpeg.")

        final_size = out_path.stat().st_size

        if final_size > max_safe_bytes and target_v_bitrate > 100:
            adj_v = max(64, int(target_v_bitrate * 0.88))
            logger.info(f"Re-adjusting video compression with lower bitrate {adj_v}k...")
            v_adj_scale = "scale='min(640,iw)':-2" if (adj_v < 400 or dur > 600) else "scale='min(854,iw)':-2"
            cmd_adj = [
                "ffmpeg", "-y", "-i", str(src),
                "-c:v", "libx264",
                "-b:v", f"{adj_v}k",
                "-maxrate", f"{int(adj_v * 1.15)}k",
                "-bufsize", f"{int(adj_v * 2)}k",
                "-preset", "ultrafast",
                "-c:a", "aac",
                "-b:a", f"{audio_kbps}k",
                "-vf", v_adj_scale,
                "-movflags", "+faststart",
                str(out_path)
            ]
            subprocess.run(cmd_adj, capture_output=True, text=True, timeout=600)
            final_size = out_path.stat().st_size

        logger.info(
            f"Video smart compression complete: initial={initial_size/(1024*1024):.2f}MB -> "
            f"final={final_size/(1024*1024):.2f}MB"
        )
        return out_path, initial_size, final_size, target_v_bitrate, True

    @staticmethod
    def precalculate_video_quality(
        file_path: str | Path,
        target_max_mb: float = SAFE_BALE_PART_LIMIT_MB
    ) -> Dict[str, Any]:
        """
        محاسبه پیش از پردازش (Pre-Calculation):
        سنجش کیفیت تقریبی خروجی ویدیو بر اساس مدت‌زمان و سقف بله، قبل از ورود به پردازش سنگین FFmpeg.
        ورودی: مسیر فایل ویدیویی و سقف مگابایتی هدف (پیش‌فرض ۴۵MB با حاشیه امن).
        خروجی: دیکشنری شامل مدت‌زمان، بیت‌ریت هدف، رزولوشن تخمینی، پرچم افت شدید کیفیت و پارت‌های پیشنهادی.
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

        # محاسبه داینامیک تعداد پارت‌ها با حاشیه امن ۴۵ مگابایت برای بله
        rec_parts = max(2, math.ceil(init_mb / target_max_mb)) if init_mb > target_max_mb else 2

        return {
            "duration_sec": dur,
            "target_v_bitrate": target_v_bitrate,
            "estimated_resolution": est_res,
            "severe_quality_drop": severe_drop,
            "recommended_parts": rec_parts,
            "initial_size_mb": init_mb
        }


class SmartVideoSplitter:
    """
    کلاس مدیریت تقسیم هوشمند ویدیوهای حجیم یا طولانی به پارت‌های باکیفیت
    بر اساس سقف مجاز بله با حفظ وضوح اصلی با استفاده از Stream Copy سریع یا انکود سبک.
    """
    @staticmethod
    def split_video(
        file_path: str | Path,
        num_parts: Optional[int] = None,
        target_max_mb: float = SAFE_BALE_PART_LIMIT_MB,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Path]:
        """
        ویدیو را بر اساس تعداد پارت‌های انتخابی کاربر یا سقف مجاز بله تکه‌تکه می‌کند.
        در صورتی که کاربر صریحاً ۲ یا ۳ پارت را انتخاب کند، ویدیو دقیقاً به همان تعداد پارت تقسیم شده
        و در صورت نیاز، هر پارت به صورت خودکار تا سقف ۴۵MB فشرده می‌شود تا خطای ۴۱۳ بله پیش نیاید.
        ورودی: مسیر فایل ویدیو، تعداد پارت‌ها، سقف مگابایتی و کالبک پیشرفت اختیاری.
        خروجی: لیستی از مسیر فایل‌های پارت تقسیم‌شده (Path).
        """
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"Input video not found: {file_path}")

        file_sz = src.stat().st_size
        total_mb = file_sz / (1024 * 1024)

        # اعطای حق انتخاب دستی به کاربر در صورت ارسال صریح تعداد پارت
        if num_parts is not None and int(num_parts) >= 2:
            num_parts = int(num_parts)
            logger.info(f"SmartVideoSplitter: User specified manual parts count = {num_parts} for {total_mb:.1f}MB video")
        else:
            # محاسبه خودکار در صورت عدم تعیین دستی
            num_parts = max(2, math.ceil(total_mb / target_max_mb))
            logger.info(f"SmartVideoSplitter: Auto-calculated parts count = {num_parts} for {total_mb:.1f}MB video")

        tech = inspect_technical_metadata(src)
        dur = float(tech.get("duration_sec", 0) or 0)
        if dur <= 0:
            dur = 600.0

        part_duration = dur / num_parts
        output_files: List[Path] = []

        if progress_callback:
            progress_callback(f"✂️ <b>در حال تقسیم هوشمند ویدیو به {num_parts} پارت باکیفیت (هر پارت زیر {target_max_mb:.0f}MB)...</b>")

        for i in range(num_parts):
            start_sec = i * part_duration
            out_p = config.TEMP_DIR / f"{src.stem}_part{i+1}of{num_parts}{src.suffix}"
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
            logger.info(f"Splitting part {i+1}/{num_parts}: {cmd_copy}")
            res = subprocess.run(cmd_copy, capture_output=True, text=True, timeout=300)

            if res.returncode != 0 or not out_p.exists() or out_p.stat().st_size < 1000:
                logger.warning(f"Stream copy split failed for part {i+1}, falling back to fast encode...")
                cmd_enc = [
                    "ffmpeg", "-y",
                    "-ss", f"{start_sec:.2f}",
                    "-t", f"{part_duration:.2f}",
                    "-i", str(src),
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-c:a", "aac",
                    "-b:a", "96k",
                    str(out_p)
                ]
                subprocess.run(cmd_enc, capture_output=True, text=True, timeout=600)

            if out_p.exists() and out_p.stat().st_size > 0:
                part_sz_mb = out_p.stat().st_size / (1024 * 1024)
                # در صورتی که پارت تولیدشده از ۴۸.۵ مگابایت عبور کرده باشد، فشرده‌سازی خودکار تا ۴۵MB
                if part_sz_mb > 48.5:
                    logger.info(f"Split part {out_p.name} ({part_sz_mb:.1f}MB) exceeds 48.5MB, auto-compressing to safe 45MB...")
                    comp_out, _, _, _, ok = SmartVideoCompressor.compress_video(out_p, target_max_mb=SAFE_BALE_PART_LIMIT_MB)
                    if ok and comp_out and comp_out.exists() and comp_out.stat().st_size > 0:
                        try:
                            out_p.unlink(missing_ok=True)
                            comp_out.rename(out_p)
                        except Exception as e:
                            logger.warning(f"Could not replace original part with compressed: {e}")
                            out_p = comp_out
                output_files.append(out_p)
            else:
                logger.error(f"Failed to generate part {i+1} of {src.name}")

        return output_files


def convert_audio_to_mp3_if_needed(file_path: str | Path) -> Tuple[Path, bool]:
    """
    Auto-converts non-mp3 audio (m4a, wav, ogg, flac, opus, etc.) to standard MP3
    using FFmpeg to prevent Rubika server Invalid_format errors.
    """
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
