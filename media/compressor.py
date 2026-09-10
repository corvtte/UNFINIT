import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple, Callable
from core.config import config
from core.logger import get_logger
from media.inspector import inspect_technical_metadata
from media.tagger import copy_all_id3_tags

logger = get_logger("compressor")

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
        max_safe_bytes = getattr(config, "MAX_SAFE_BALE_SIZE_BYTES", 49 * 1024 * 1024)

        # If file is already within safe limit, do not compress
        if initial_size <= max_safe_bytes:
            tech = inspect_technical_metadata(src)
            return src, initial_size, initial_size, tech.get("bitrate_kbps", 128), False

        # File exceeds safe limit -> Run Smart Compression
        if progress_callback:
            orig_size_mb = f"{initial_size / (1024 * 1024):.1f}"
            progress_callback(
                "🎛 <b>در حال فشرده‌سازی هوشمند جهت رعایت سقف بله...</b>\n"
                f"📊 حجم فعلی: <code>{orig_size_mb} MB</code> ➔ هدف: <code>زیر 49.9 MB</code>\n"
                "⚙️ فرآیند بهینه‌سازی صدا و تصویر در حال اجراست، لطفاً شکیبا باشید..."
            )

        dur = SmartAudioCompressor.get_audio_duration(src)
        tech = inspect_technical_metadata(src)
        init_bitrate = int(tech.get("bitrate_kbps", 320) or 320)

        target_bitrate = SmartAudioCompressor.calculate_target_bitrate(
            duration_sec=dur,
            target_max_bytes=max_safe_bytes,
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
        max_safe_bytes = getattr(config, "MAX_SAFE_BALE_SIZE_BYTES", int(49.99 * 1024 * 1024))

        if initial_size <= max_safe_bytes:
            tech = inspect_technical_metadata(src)
            return src, initial_size, initial_size, tech.get("bitrate_kbps", 800), False

        if progress_callback:
            orig_size_mb = f"{initial_size / (1024 * 1024):.1f}"
            progress_callback(
                "🎛 <b>در حال فشرده‌سازی هوشمند جهت رعایت سقف بله...</b>\n"
                f"📊 حجم فعلی: <code>{orig_size_mb} MB</code> ➔ هدف: <code>زیر 49.9 MB</code>\n"
                "⚙️ فرآیند بهینه‌سازی صدا و تصویر در حال اجراست، لطفاً شکیبا باشید..."
            )

        tech = inspect_technical_metadata(src)
        dur = float(tech.get("duration_sec", 0) or 0)
        audio_kbps = 64 if dur > 1800 else 96
        target_v_bitrate = SmartVideoCompressor.calculate_target_video_bitrate(
            dur, max_safe_bytes, audio_bitrate_kbps=audio_kbps
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
