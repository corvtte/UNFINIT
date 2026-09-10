import re
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Callable
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
from services.session_manager import session_manager

logger = get_logger("media_service")

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac", ".wma", ".opus", ".m4b"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v", ".ts"}


def clean_display_filename(filename: str) -> str:
    """
    Strips system prefixes such as drop_id, task_id, or compressed_ from filename
    and unquotes any URL-encoded Persian/Unicode characters.
    """
    if not filename:
        return "audio.mp3"
    import urllib.parse
    raw = urllib.parse.unquote(str(filename).strip())
    clean = re.sub(r"^(?:compressed_|raw_|trimmed_|[0-9a-fA-F]{6,12}_)+", "", raw)
    clean = urllib.parse.unquote(clean).strip()
    return clean or "audio.mp3"


class MediaService:
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
                        await tg.app.download_media(file_id, file_name=str(temp_path))
                        ok = temp_path.exists() and temp_path.stat().st_size > 0
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
        v_path = Path(video_path)
        if not v_path.exists():
            raise FileNotFoundError(f"Input video file not found: {video_path}")

        out_p = output_path or config.TEMP_DIR / f"{v_path.stem}.mp3"
        out_p.parent.mkdir(parents=True, exist_ok=True)

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
            str(out_p)
        ]
        logger.info(f"Extracting MP3 from {v_path.name} (Bitrate: {bitrate_kbps}k, SampleRate: {sample_rate}Hz, Channels: {channels}): {cmd}")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if res.returncode != 0 or not out_p.exists() or out_p.stat().st_size < 100:
            logger.error(f"FFmpeg video-to-mp3 extraction error: {res.stderr}")
            return False, out_p

        tags = custom_tags or {}
        if "title" not in tags or not tags["title"]:
            tags["title"] = v_path.stem
        if "artist" not in tags or not tags["artist"]:
            tags["artist"] = config.DEFAULT_ARTIST

        cov_p = cover_image_path or generate_video_thumbnail(v_path)
        modify_id3_tags(out_p, tags, cover_image_path=cov_p)
        logger.info(f"Video converted to MP3 successfully: {out_p.name} ({out_p.stat().st_size} bytes)")
        return True, out_p

    @staticmethod
    def extract_audio_from_video(drop_id: str) -> Tuple[bool, Path, Dict[str, Any]]:
        session = session_manager.get_session(drop_id)
        if not session or not session.get("working_path"):
            raise ValueError(f"Session or working video file not found for drop_id: {drop_id}")

        v_path = Path(session["working_path"])
        tags = {
            "title": session.get("draft_tags", {}).get("title") or session.get("embed_meta", {}).get("title") or v_path.stem,
            "artist": session.get("draft_tags", {}).get("artist") or session.get("embed_meta", {}).get("artist") or config.DEFAULT_ARTIST
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
            ""
        )

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
                final_path, init_sz, final_sz, final_bitrate, was_comp = SmartVideoCompressor.compress_if_needed(
                    working_path, progress_callback=progress_callback
                )
                session["compressed_path"] = str(final_path)
                info["final_size_bytes"] = final_sz
                info["was_compressed"] = was_comp
                info["final_bitrate"] = final_bitrate
                return final_path, send_name, info

        info["final_size_bytes"] = info["initial_size_bytes"]
        return working_path, send_name, info
