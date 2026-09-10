from html import escape
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

def human_size(size_bytes: int | float) -> str:
    val = float(size_bytes or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if val < 1024.0 or unit == "GB":
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{size_bytes} B"

def format_duration(seconds: int | float) -> str:
    s = max(0, int(seconds or 0))
    h, rem = divmod(s, 3600)
    m, sec_rem = divmod(rem, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec_rem:02d}"
    return f"{m:02d}:{sec_rem:02d}"

def parse_time_to_seconds(time_str: str) -> Optional[float]:
    """
    Parses timestamps like '02:10', '01:02:10', '130', '130.5' into seconds.
    """
    if not time_str:
        return None
    s = str(time_str).strip()
    # If purely numeric
    if re.match(r"^\d+(?:\.\d+)?$", s):
        return float(s)
    # If MM:SS or HH:MM:SS
    parts = s.split(":")
    if len(parts) == 2:
        try:
            return int(parts[0]) * 60 + float(parts[1])
        except ValueError:
            return None
    elif len(parts) == 3:
        try:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except ValueError:
            return None
    return None

def parse_trim_input(user_input: str, total_duration: float = 0) -> Tuple[Optional[float], Optional[float]]:
    """
    Parses user trim input formats:
      - '02:10 - 21:28' or '02:10 21:28' or '02:10_21:28'
      - '02:10' (start to end of file)
      - '130 - 1288' or '130'
    """
    clean = user_input.strip().replace("تا", "-").replace("to", "-").replace("_", " ")
    parts = [p.strip() for p in re.split(r"[-–—\s]+", clean) if p.strip()]

    if len(parts) >= 2:
        start_sec = parse_time_to_seconds(parts[0])
        end_sec = parse_time_to_seconds(parts[1])
        return start_sec, end_sec
    elif len(parts) == 1:
        start_sec = parse_time_to_seconds(parts[0])
        end_sec = total_duration if total_duration > 0 else None
        return start_sec, end_sec
def format_transfer_progress(
    current: int,
    total: int,
    elapsed_sec: float,
    stage_title: str = "در حال انتقال فایل..."
) -> str:
    pct = int((current / total) * 100) if total > 0 else 0
    pct = min(100, max(0, pct))
    bar_len = 10
    filled = int((pct / 100) * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    transferred_mb = f"{current / (1024 * 1024):.2f}"
    total_mb = f"{total / (1024 * 1024):.2f}"
    speed_mbps = f"{(current / max(0.01, elapsed_sec)) / (1024 * 1024):.2f}"

    return (
        f"⏳ <b>{stage_title}</b>\n\n"
        f"<code>[{bar}] {pct}%</code>\n\n"
        f"📦 <b>حجم:</b> <code>{transferred_mb} MB</code> از <code>{total_mb} MB</code>\n"
        f"⚡️ <b>سرعت انتقال:</b> <code>{speed_mbps} MB/s</code>"
    )


class TelegramFormatter:
    @staticmethod
    def format_light_card(data: dict) -> str:
        api_meta = data.get("api_meta", {})
        embed_meta = data.get("embed_meta", {})
        draft_tags = data.get("draft_tags", {})
        edited_fields = data.get("edited_fields", {})
        mtype = data.get("media_type", "audio")

        raw_fn = edited_fields.get("filename") or data.get("audio_filename") or api_meta.get("filename") or "file.mp3"
        clean_fn = Path(raw_fn).name
        suffix = Path(clean_fn).suffix.lower()

        if mtype == "video" or suffix in (".mp4", ".mkv", ".mov", ".avi", ".webm"):
            type_label = f"ویدیو تصویری ({suffix.replace('.', '')})"
        elif mtype == "audio" or suffix in (".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac"):
            type_label = f"موزیک ({suffix.replace('.', '') or 'mp3'})"
        else:
            type_label = "سند / فایل"

        sz_bytes = data.get("file_size") or api_meta.get("file_size", 0)
        sz_text = f"{sz_bytes / (1024 * 1024):.2f} مگابایت" if sz_bytes > 0 else "نامشخص"

        title_val = draft_tags.get("title") or embed_meta.get("title") or api_meta.get("title") or "تنظیم نشده"
        artist_val = draft_tags.get("artist") or embed_meta.get("artist") or api_meta.get("artist") or "تنظیم نشده"

        dur_sec = api_meta.get("duration_sec") or data.get("tech_meta", {}).get("duration_sec", 0)
        dur_text = format_duration(dur_sec) if dur_sec > 0 else "نامشخص"

        has_cov = bool(embed_meta.get("has_cover") or data.get("thumb_path"))
        cov_text = "بله ✅" if has_cov else "خیر ❌"

        lines = [
            f"📌 <b>نوع فایل:</b> <code>{escape(type_label)}</code>",
            f"📦 <b>حجم فایل:</b> <b>{sz_text}</b>",
            f"🎵 <b>نام موزیک:</b> <code>{escape(str(title_val))}</code>",
            f"🗣 <b>نام خواننده:</b> <code>{escape(str(artist_val))}</code>",
            f"⏱️ <b>مدت زمان:</b> <code>{dur_text}</code>",
            f"🖼 <b>تصویر بند انگشتی (تامبنیل) دارد؟</b> {cov_text}",
            f"📄 <b>نام فایل:</b> <code>{escape(clean_fn)}</code>"
        ]

        if data.get("current_status"):
            lines.append(f"\n⏳ <b>وضعیت:</b> {escape(data['current_status'])}")

        return "\n".join(lines)

    @staticmethod
    def format_tag_details(data: dict) -> str:
        e_meta = data.get("embed_meta", {})
        draft_tags = data.get("draft_tags", {})
        cov_info = data.get("cover_info", {})

        title_val = draft_tags.get("title") or e_meta.get("title") or "تنظیم نشده"
        artist_val = draft_tags.get("artist") or e_meta.get("artist") or "تنظیم نشده"
        album_val = draft_tags.get("album") or e_meta.get("album") or "تنظیم نشده"
        album_artist = e_meta.get("album_artist") or "تنظیم نشده"
        year_val = e_meta.get("year") or "تنظیم نشده"
        track_val = e_meta.get("track_number") or "تنظیم نشده"
        disc_val = e_meta.get("disc_number") or "تنظیم نشده"
        genre_val = e_meta.get("genre") or "تنظیم نشده"
        comm_val = e_meta.get("comment") or "تنظیم نشده"
        composer_val = e_meta.get("composer") or "تنظیم نشده"

        has_cov = cov_info.get("has_cover", bool(e_meta.get("has_cover")))
        cov_res = cov_info.get("resolution", "مشخص شده" if has_cov else "ندارد")
        cov_sz = f"{cov_info.get('size_kb', 0)} KB" if has_cov else "0 KB"
        cov_fmt = cov_info.get("format", "JPEG" if has_cov else "ندارد")

        lines = [
            "📋 <b>اطلاعات تگ‌ها و متادیتا (Mp3tag Standard):</b>",
            "",
            f"🎵 <b>Title:</b> <code>{escape(str(title_val))}</code>",
            f"🗣 <b>Artist:</b> <code>{escape(str(artist_val))}</code>",
            f"💿 <b>Album:</b> <code>{escape(str(album_val))}</code>",
            f"👤 <b>Album Artist:</b> <code>{escape(str(album_artist))}</code>",
            f"🎼 <b>Composer:</b> <code>{escape(str(composer_val))}</code>",
            f"📅 <b>Year:</b> <code>{escape(str(year_val))}</code>",
            f"🔢 <b>Track:</b> <code>{escape(str(track_val))}</code>",
            f"💽 <b>Discnumber:</b> <code>{escape(str(disc_val))}</code>",
            f"📂 <b>Genre:</b> <code>{escape(str(genre_val))}</code>",
            f"💬 <b>Comment:</b> <code>{escape(str(comm_val))}</code>",
            "",
            "🖼 <b>مشخصات کاور آلبوم:</b>",
            f"▫️ وضعیت: <b>{'دارد ✅' if has_cov else 'ندارد ❌'}</b>",
            f"▫️ ابعاد تصویر: <code>{cov_res}</code>",
            f"▫️ حجم کاور: <code>{cov_sz}</code>",
            f"▫️ فرمت تصویر: <code>{cov_fmt}</code>"
        ]
        return "\n".join(lines)

    @staticmethod
    def format_audio_specs(data: dict) -> str:
        t_meta = data.get("tech_meta", {})
        size = int(data.get("file_size", 0) or 0)
        dur = int(t_meta.get("duration_sec", 0) or 0)
        bitrate = t_meta.get("bitrate_kbps") or (round((size * 8) / (dur * 1000)) if (size and dur) else 192)
        sample_rate = t_meta.get("sample_rate", 44100)
        channels = t_meta.get("channels", "Stereo (2 channels)")
        codec = t_meta.get("audio_codec") or t_meta.get("codec", "mp3")

        lines = [
            "📊 <b>مشخصات فنی و ساختار صوت (FFprobe Engine):</b>",
            "",
            f"📁 <b>نام فایل:</b> <code>{escape(data.get('audio_filename') or 'file.mp3')}</code>",
            f"📦 <b>حجم دقیق:</b> <b>{human_size(size)}</b> ({size:,} بایت)",
            f"⏱️ <b>مدت زمان دقیق:</b> <b>{format_duration(dur)}</b> ({dur} ثانیه)",
            f"📻 <b>بیت‌ریت کل (Bitrate):</b> <b>{bitrate} kbps</b>",
            f"🎚 <b>نرخ نمونه‌برداری (Sample Rate):</b> <b>{sample_rate:,} Hz</b>",
            f"🎧 <b>حالت کانال (Channels):</b> <b>{escape(channels)}</b>",
            f"🎼 <b>کدک صوتی (Codec):</b> <code>{escape(codec)}</code>"
        ]
        return "\n".join(lines)


class BaleFormatter:
    @staticmethod
    def clean_text(text: str) -> str:
        if not text: return ""
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()

    @staticmethod
    def format_light_card(data: dict) -> str:
        api_meta = data.get("api_meta", {})
        embed_meta = data.get("embed_meta", {})
        draft_tags = data.get("draft_tags", {})
        edited_fields = data.get("edited_fields", {})
        mtype = data.get("media_type", "audio")

        raw_fn = edited_fields.get("filename") or data.get("audio_filename") or api_meta.get("filename") or "file.mp3"
        clean_fn = Path(raw_fn).name
        suffix = Path(clean_fn).suffix.lower()

        if mtype == "video" or suffix in (".mp4", ".mkv", ".mov", ".avi", ".webm"):
            type_label = f"ویدیو تصویری ({suffix.replace('.', '')})"
        elif mtype == "audio" or suffix in (".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac"):
            type_label = f"موزیک ({suffix.replace('.', '') or 'mp3'})"
        else:
            type_label = "سند / فایل"

        sz_bytes = data.get("file_size") or api_meta.get("file_size", 0)
        sz_text = f"{sz_bytes / (1024 * 1024):.2f} مگابایت" if sz_bytes > 0 else "نامشخص"

        title_val = draft_tags.get("title") or embed_meta.get("title") or api_meta.get("title") or "تنظیم نشده"
        artist_val = draft_tags.get("artist") or embed_meta.get("artist") or api_meta.get("artist") or "تنظیم نشده"

        dur_sec = api_meta.get("duration_sec") or data.get("tech_meta", {}).get("duration_sec", 0)
        dur_text = format_duration(dur_sec) if dur_sec > 0 else "نامشخص"

        has_cov = bool(embed_meta.get("has_cover") or data.get("thumb_path"))
        cov_text = "بله ✅" if has_cov else "خیر ❌"

        lines = [
            f"📌 نوع فایل: {type_label}",
            f"📦 حجم فایل: {sz_text}",
            f"🎵 نام موزیک: {title_val}",
            f"🗣 نام خواننده: {artist_val}",
            f"⏱️ مدت زمان: {dur_text}",
            f"🖼 تصویر بند انگشتی (تامبنیل) دارد؟ {cov_text}",
            f"📄 نام فایل: {clean_fn}"
        ]

        if data.get("current_status"):
            lines.append(f"\n⏳ وضعیت: {data['current_status']}")

        return "\n".join(lines)

    @staticmethod
    def format_tag_details(data: dict) -> str:
        e_meta = data.get("embed_meta", {})
        draft_tags = data.get("draft_tags", {})
        cov_info = data.get("cover_info", {})

        title_val = draft_tags.get("title") or e_meta.get("title") or "تنظیم نشده"
        artist_val = draft_tags.get("artist") or e_meta.get("artist") or "تنظیم نشده"
        album_val = draft_tags.get("album") or e_meta.get("album") or "تنظیم نشده"
        has_cov = cov_info.get("has_cover", bool(e_meta.get("has_cover")))

        lines = [
            "📋 اطلاعات تگ‌ها (Mp3tag Standard):",
            "",
            f"🎵 Title: {title_val}",
            f"🗣 Artist: {artist_val}",
            f"💿 Album: {album_val}",
            f"📅 Year: {e_meta.get('year') or 'تنظیم نشده'}",
            f"📂 Genre: {e_meta.get('genre') or 'تنظیم نشده'}",
            f"💬 Comment: {e_meta.get('comment') or 'تنظیم نشده'}",
            "",
            "🖼 کاور آلبوم:",
            f"▫️ وضعیت: {'دارد ✅' if has_cov else 'ندارد ❌'}",
            f"▫️ ابعاد: {cov_info.get('resolution', 'مشخص شده')}",
            f"▫️ حجم: {cov_info.get('size_kb', 0)} KB",
            f"▫️ فرمت: {cov_info.get('format', 'JPEG')}"
        ]
        return "\n".join(lines)

    @staticmethod
    def format_audio_specs(data: dict) -> str:
        t_meta = data.get("tech_meta", {})
        size = int(data.get("file_size", 0) or 0)
        dur = int(t_meta.get("duration_sec", 0) or 0)
        bitrate = t_meta.get("bitrate_kbps") or 192
        sample_rate = t_meta.get("sample_rate", 44100)

        lines = [
            "📊 مشخصات فنی صوت (FFprobe):",
            "",
            f"📁 نام فایل: {data.get('audio_filename') or 'file.mp3'}",
            f"📦 حجم: {human_size(size)}",
            f"⏱️ مدت زمان: {format_duration(dur)}",
            f"📻 بیت‌ریت: {bitrate} kbps",
            f"🎚 سمپل‌ریت: {sample_rate:,} Hz",
            f"🎧 کانال‌ها: {t_meta.get('channels', 'Stereo')}"
        ]
        return "\n".join(lines)


class RubikaFormatter(BaleFormatter):
    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()
