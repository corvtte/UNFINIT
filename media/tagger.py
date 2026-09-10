import shutil
import struct
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from core.config import config
from core.logger import get_logger

logger = get_logger("tagger")

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v", ".ts"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac", ".wma", ".opus", ".m4b"}


def strip_existing_id3(file_path: Path) -> bytes:
    with open(file_path, "rb") as f:
        data = f.read()
    if len(data) >= 10 and data[:3] == b"ID3":
        tag_size = (
            ((data[6] & 0x7F) << 21)
            | ((data[7] & 0x7F) << 14)
            | ((data[8] & 0x7F) << 7)
            | (data[9] & 0x7F)
        )
        total_header_size = 10 + tag_size
        data = data[total_header_size:]
    # Strip ID3v1 at the end (128 bytes starting with TAG)
    if len(data) >= 128 and data[-128:-125] == b"TAG":
        data = data[:-128]
    return data


def strip_all_metadata(file_path: str | Path, output_path: Optional[Path] = None) -> Tuple[bool, Path]:
    """
    Completely removes all ID3 tags (v1 & v2), comments, and embedded cover art from audio files.
    """
    src = Path(file_path)
    if not src.exists():
        return False, src

    out_p = output_path or config.TEMP_DIR / f"raw_{src.name}"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(out_p))

    suffix = out_p.suffix.lower()

    # 1. Mutagen stripping
    try:
        if suffix == ".mp3":
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3
            try:
                audio = ID3(str(out_p))
                audio.delete(str(out_p))
            except Exception:
                pass
            try:
                mp3 = MP3(str(out_p))
                mp3.delete()
            except Exception:
                pass
            logger.info(f"Mutagen successfully stripped all ID3 tags from {out_p.name}")
            return True, out_p
        elif suffix in (".m4a", ".mp4", ".m4b"):
            from mutagen.mp4 import MP4
            audio = MP4(str(out_p))
            audio.clear()
            audio.save()
            logger.info(f"Mutagen successfully stripped all MP4 tags from {out_p.name}")
            return True, out_p
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Mutagen strip notice ({e}), applying binary fallback...")

    # 2. Binary ID3 Header/Footer Stripping for MP3
    if suffix == ".mp3":
        try:
            raw_audio_bytes = strip_existing_id3(out_p)
            with open(out_p, "wb") as f:
                f.write(raw_audio_bytes)
            logger.info(f"Binary raw strip successful on {out_p.name}")
            return True, out_p
        except Exception as e:
            logger.error(f"Binary strip error: {e}")

    # 3. FFmpeg map_metadata -1 fallback
    try:
        temp_ffmpeg = out_p.parent / f"ffraw_{out_p.name}"
        cmd = [
            "ffmpeg", "-y", "-i", str(out_p),
            "-map_metadata", "-1", "-vn", "-c:a", "copy",
            str(temp_ffmpeg)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0 and temp_ffmpeg.exists() and temp_ffmpeg.stat().st_size > 100:
            shutil.move(str(temp_ffmpeg), str(out_p))
            logger.info(f"FFmpeg raw strip successful on {out_p.name}")
            return True, out_p
    except Exception as e:
        logger.error(f"FFmpeg strip error: {e}")

    return False, out_p


def inspect_cover_details(file_path: str | Path) -> Dict[str, Any]:
    """
    Extracts cover art specifications: resolution, size, format.
    """
    path = Path(file_path)
    res = {
        "has_cover": False,
        "resolution": "ندارد",
        "size_kb": 0,
        "format": "نامشخص",
        "mime": None
    }
    if not path.exists():
        return res

    cov_file = extract_cover_image(path)
    if cov_file and cov_file.exists() and cov_file.stat().st_size > 50:
        res["has_cover"] = True
        sz_bytes = cov_file.stat().st_size
        res["size_kb"] = round(sz_bytes / 1024, 1)
        ext = cov_file.suffix.lower().replace(".", "").upper()
        res["format"] = "JPEG" if ext in ("JPG", "JPEG") else ("PNG" if ext == "PNG" else ext)
        res["mime"] = f"image/{ext.lower()}"

        # Get image resolution via ffprobe or PIL
        try:
            cmd = [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0",
                str(cov_file)
            ]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if p.returncode == 0 and p.stdout.strip():
                res["resolution"] = f"{p.stdout.strip()} px"
        except Exception:
            res["resolution"] = "مشخص شده"

    return res


def build_native_id3v23(tags: Dict[str, Any], cover_bytes: Optional[bytes] = None, cover_mime: str = "image/jpeg") -> bytes:
    frames = bytearray()

    def add_text_frame(frame_id: str, text: Any):
        s = str(text or "").strip()
        if not s:
            return
        payload = b"\x03" + s.encode("utf-8")
        size = len(payload)
        header = frame_id.encode("ascii") + struct.pack(">I", size) + b"\x00\x00"
        frames.extend(header)
        frames.extend(payload)

    add_text_frame("TIT2", tags.get("title"))
    add_text_frame("TPE1", tags.get("artist"))
    add_text_frame("TALB", tags.get("album"))
    add_text_frame("TPE2", tags.get("album_artist"))
    add_text_frame("TCON", tags.get("genre"))
    add_text_frame("TYER", tags.get("year"))
    add_text_frame("TRCK", tags.get("track_number"))
    add_text_frame("TPOS", tags.get("disc_number"))
    add_text_frame("TCOM", tags.get("composer"))
    add_text_frame("TCOP", tags.get("copyright"))

    comm = tags.get("comment")
    if comm and str(comm).strip():
        payload = b"\x03eng\x00" + str(comm).strip().encode("utf-8")
        size = len(payload)
        header = b"COMM" + struct.pack(">I", size) + b"\x00\x00"
        frames.extend(header)
        frames.extend(payload)

    if cover_bytes:
        encoded_mime = cover_mime.encode("ascii") + b"\x00"
        apic_payload = b"\x03" + encoded_mime + b"\x03" + b"\x00" + cover_bytes
        size = len(apic_payload)
        header = b"APIC" + struct.pack(">I", size) + b"\x00\x00"
        frames.extend(header)
        frames.extend(apic_payload)

    if not frames:
        return b""

    tag_size = len(frames)
    b0 = (tag_size >> 21) & 0x7F
    b1 = (tag_size >> 14) & 0x7F
    b2 = (tag_size >> 7) & 0x7F
    b3 = tag_size & 0x7F

    header = b"ID3\x03\x00\x00" + bytes([b0, b1, b2, b3])
    return bytes(header + frames)


def modify_id3_tags(
    file_path: str | Path,
    tags: Dict[str, Any],
    cover_image_path: Optional[str | Path] = None,
    remove_cover: bool = False
) -> bool:
    path = Path(file_path)
    if not path.exists():
        return False

    suffix = path.suffix.lower()

    # Strategy 1: Mutagen ID3 / MP4
    try:
        if suffix == ".mp3":
            from mutagen.id3 import (
                ID3, TIT2, TPE1, TALB, TPE2, TCON, TYER, TDRC,
                TRCK, TPOS, TCOM, COMM, TCOP, APIC, ID3NoHeaderError
            )
            try:
                audio = ID3(str(path))
            except ID3NoHeaderError:
                audio = ID3()

            if "title" in tags and tags["title"] is not None:
                audio.delall("TIT2")
                title_val = str(tags["title"]).strip()
                if title_val:
                    audio.add(TIT2(encoding=3, text=title_val))

            if "artist" in tags and tags["artist"] is not None:
                audio.delall("TPE1")
                artist_val = str(tags["artist"]).strip()
                if artist_val:
                    audio.add(TPE1(encoding=3, text=artist_val))

            if "album" in tags and tags["album"] is not None:
                audio.delall("TALB")
                album_val = str(tags["album"]).strip()
                if album_val:
                    audio.add(TALB(encoding=3, text=album_val))

            if "comment" in tags and tags["comment"] is not None:
                audio.delall("COMM")
                comm_val = str(tags["comment"]).strip()
                if comm_val:
                    audio.add(COMM(encoding=3, lang="eng", desc="", text=comm_val))

            if remove_cover:
                audio.delall("APIC")

            if cover_image_path and Path(cover_image_path).exists():
                c_path = Path(cover_image_path)
                mime = "image/png" if c_path.suffix.lower() == ".png" else "image/jpeg"
                with open(c_path, "rb") as cf:
                    audio.delall("APIC")
                    audio.add(
                        APIC(
                            encoding=3,
                            mime=mime,
                            type=3,
                            desc="Cover",
                            data=cf.read()
                        )
                    )

            audio.save(str(path), v2_version=3)
            logger.info(f"Mutagen ID3 physical save success on {path.name}: {tags}")
            return True

        elif suffix in (".m4a", ".mp4", ".m4b"):
            from mutagen.mp4 import MP4, MP4Cover
            audio = MP4(str(path))
            if "title" in tags and tags["title"] is not None:
                audio["\xa9nam"] = [str(tags["title"]).strip()]
            if "artist" in tags and tags["artist"] is not None:
                audio["\xa9ART"] = [str(tags["artist"]).strip()]
            if "album" in tags and tags["album"] is not None:
                audio["\xa9alb"] = [str(tags["album"]).strip()]
            if remove_cover and "covr" in audio:
                del audio["covr"]
            if cover_image_path and Path(cover_image_path).exists():
                c_path = Path(cover_image_path)
                fmt = MP4Cover.FORMAT_PNG if c_path.suffix.lower() == ".png" else MP4Cover.FORMAT_JPEG
                with open(c_path, "rb") as cf:
                    audio["covr"] = [MP4Cover(cf.read(), imageformat=fmt)]
            audio.save()
            logger.info(f"Mutagen MP4 physical save success on {path.name}: {tags}")
            return True
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Mutagen modification attempt failed ({e}), falling back to native engine...")

    # Strategy 2: Native pure-Python ID3v2.3 binary modification for MP3
    if suffix == ".mp3":
        try:
            cov_bytes = None
            cov_mime = "image/jpeg"
            if cover_image_path and Path(cover_image_path).exists():
                with open(cover_image_path, "rb") as cf:
                    cov_bytes = cf.read()
                cov_mime = "image/png" if Path(cover_image_path).suffix.lower() == ".png" else "image/jpeg"

            audio_body = strip_existing_id3(path)
            id3_tag = build_native_id3v23(tags, cover_bytes=cov_bytes, cover_mime=cov_mime)
            with open(path, "wb") as f:
                f.write(id3_tag + audio_body)
            logger.info(f"Native pure-Python ID3v2.3 physical save success on {path.name}: {tags}")
            return True
        except Exception as e:
            logger.error(f"Native ID3 tag modification error: {e}")

    # Strategy 3: FFmpeg metadata rewrite fallback
    try:
        temp_out = path.parent / f"tagged_{path.stem}_{suffix}"
        temp_out.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", "-i", str(path)]
        if tags.get("title"):
            cmd.extend(["-metadata", f"title={tags['title']}"])
        if tags.get("artist"):
            cmd.extend(["-metadata", f"artist={tags['artist']}"])
        if tags.get("album"):
            cmd.extend(["-metadata", f"album={tags['album']}"])
        cmd.extend(["-c", "copy", str(temp_out)])
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0 and temp_out.exists():
            shutil.move(str(temp_out), str(path))
            logger.info(f"FFmpeg copy metadata physical save success on {path.name}: {tags}")
            return True
    except Exception as e:
        logger.error(f"FFmpeg tag fallback error: {e}")

    return False


def generate_video_thumbnail(
    video_path: str | Path,
    output_dir: Optional[Path] = None,
    timestamp: str = "00:00:02"
) -> Optional[Path]:
    """
    Generates standard high quality video thumbnail from exactly 00:00:02 with scale=320:-1.
    """
    src = Path(video_path)
    if not src.exists():
        return None
    out_dir = output_dir or config.TEMP_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = out_dir / f"vthumb_{src.stem}.jpg"
    
    cmd = [
        "ffmpeg", "-y", "-ss", timestamp,
        "-i", str(src),
        "-vframes", "1",
        "-q:v", "2",
        "-vf", "scale=320:-1",
        str(thumb_path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and thumb_path.exists() and thumb_path.stat().st_size > 100:
            return thumb_path
        # Fallback to second 00:00:01
        cmd[3] = "00:00:01"
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if thumb_path.exists() and thumb_path.stat().st_size > 100:
            return thumb_path
    except Exception as e:
        logger.warning(f"Video thumbnail generation error: {e}")
    return None


def extract_cover_image(file_path: str | Path, output_dir: Optional[Path] = None) -> Optional[Path]:
    path = Path(file_path)
    if not path.exists():
        return None
    
    suffix = path.suffix.lower()

    if suffix in VIDEO_EXTENSIONS:
        return generate_video_thumbnail(path, output_dir=output_dir)

    # 1. MP3 Cover Extraction (Mutagen ID3 APIC)
    if suffix == ".mp3":
        try:
            from mutagen.id3 import ID3
            audio = ID3(str(path))
            apic_keys = [k for k in audio.keys() if k.startswith("APIC")]
            if apic_keys:
                apic = audio[apic_keys[0]]
                ext = ".png" if getattr(apic, "mime", "").lower() == "image/png" else ".jpg"
                out_dir = output_dir or config.TEMP_DIR
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file = out_dir / f"cover_{path.stem}{ext}"
                with open(out_file, "wb") as f:
                    f.write(apic.data)
                return out_file
        except Exception:
            pass

        # Native MP3 ID3 APIC extraction
        try:
            with open(path, "rb") as f:
                header = f.read(10)
                if len(header) == 10 and header[:3] == b"ID3":
                    tag_size = (
                        ((header[6] & 0x7F) << 21)
                        | ((header[7] & 0x7F) << 14)
                        | ((header[8] & 0x7F) << 7)
                        | (header[9] & 0x7F)
                    )
                    tag_data = f.read(tag_size)
                    idx = 0
                    while idx + 10 <= len(tag_data):
                        frame_id = tag_data[idx:idx+4]
                        if not frame_id.isalnum() or frame_id.startswith(b"\x00"):
                            break
                        frame_size = struct.unpack(">I", tag_data[idx+4:idx+8])[0]
                        idx += 10
                        frame_bytes = tag_data[idx:idx+frame_size]
                        idx += frame_size
                        if frame_id == b"APIC" and len(frame_bytes) > 4:
                            null_idx = frame_bytes.find(b"\x00", 1)
                            if null_idx > 0:
                                mime_str = frame_bytes[1:null_idx].decode("ascii", errors="ignore")
                                ext = ".png" if "png" in mime_str else ".jpg"
                                img_start = frame_bytes.find(b"\xFF\xD8")
                                if img_start == -1:
                                    img_start = frame_bytes.find(b"\x89PNG")
                                if img_start == -1:
                                    img_start = null_idx + 3
                                out_dir = output_dir or config.TEMP_DIR
                                out_dir.mkdir(parents=True, exist_ok=True)
                                out_file = out_dir / f"cover_{path.stem}{ext}"
                                with open(out_file, "wb") as out_f:
                                    out_f.write(frame_bytes[img_start:])
                                return out_file
        except Exception:
            pass

    # 2. M4A / MP4 Cover Extraction
    elif suffix in (".m4a", ".mp4", ".m4b", ".aac"):
        try:
            from mutagen.mp4 import MP4
            audio = MP4(str(path))
            if "covr" in audio and len(audio["covr"]) > 0:
                cov = audio["covr"][0]
                ext = ".png" if getattr(cov, "imageformat", 0) == 14 else ".jpg"
                out_dir = output_dir or config.TEMP_DIR
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file = out_dir / f"cover_{path.stem}{ext}"
                with open(out_file, "wb") as f:
                    f.write(bytes(cov))
                return out_file
        except Exception:
            pass

        try:
            with open(path, "rb") as f:
                data = f.read(min(path.stat().st_size, 10 * 1024 * 1024))
                covr_idx = data.find(b"covr")
                if covr_idx != -1:
                    sub = data[covr_idx:]
                    jpg_idx = sub.find(b"\xFF\xD8\xFF")
                    png_idx = sub.find(b"\x89PNG")
                    out_dir = output_dir or config.TEMP_DIR
                    out_dir.mkdir(parents=True, exist_ok=True)
                    if jpg_idx != -1 and (png_idx == -1 or jpg_idx < png_idx):
                        end_jpg = sub.find(b"\xFF\xD9", jpg_idx)
                        if end_jpg != -1:
                            out_file = out_dir / f"cover_{path.stem}.jpg"
                            with open(out_file, "wb") as out_f:
                                out_f.write(sub[jpg_idx:end_jpg+2])
                            return out_file
                    elif png_idx != -1:
                        end_png = sub.find(b"IEND\xaeB`\x82", png_idx)
                        if end_png != -1:
                            out_file = out_dir / f"cover_{path.stem}.png"
                            with open(out_file, "wb") as out_f:
                                out_f.write(sub[png_idx:end_png+8])
                            return out_file
        except Exception:
            pass

    return None


def copy_all_id3_tags(source_audio: str | Path, target_audio: str | Path) -> bool:
    src = Path(source_audio)
    dst = Path(target_audio)
    if not src.exists() or not dst.exists():
        return False
    try:
        from mutagen.id3 import ID3
        src_audio = ID3(str(src))
        try:
            dst_audio = ID3(str(dst))
        except Exception:
            dst_audio = ID3()
        dst_audio.clear()
        for key, frame in src_audio.items():
            dst_audio.add(frame)
        dst_audio.save(str(dst), v2_version=3)
        return True
    except Exception:
        pass

    try:
        from media.inspector import inspect_embedded_metadata
        embed = inspect_embedded_metadata(src)
        cov = extract_cover_image(src)
        modify_id3_tags(dst, embed, cover_image_path=cov)
        if cov and cov.exists():
            cov.unlink()
        return True
    except Exception:
        return False
