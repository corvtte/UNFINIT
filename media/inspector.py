import json
import struct
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple
from core.logger import get_logger

logger = get_logger("inspector")

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v", ".ts"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}

def inspect_technical_metadata(file_path: str | Path) -> Dict[str, Any]:
    path = Path(file_path)
    ext = path.suffix.lower()
    is_video = ext in VIDEO_EXTENSIONS
    is_image = ext in IMAGE_EXTENSIONS

    result = {
        "filename": path.name,
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "format": "video/mp4" if is_video else ("image/jpeg" if is_image else "audio/mpeg"),
        "codec": "h264" if is_video else ("jpeg" if is_image else "mp3"),
        "duration_sec": 0,
        "bitrate_kbps": 0,
        "sample_rate": 44100,
        "channels": "Stereo (2 channels)",
        "resolution": None,
        "fps": None,
        "width": 0,
        "height": 0,
        "video_codec": None,
        "audio_codec": None,
        "is_video": is_video,
        "is_image": is_image
    }
    if not path.exists():
        return result

    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
            fmt = data.get("format", {})
            dur = float(fmt.get("duration", 0) or 0)
            result["duration_sec"] = int(dur)
            
            raw_bitrate = fmt.get("bitrate")
            if raw_bitrate:
                result["bitrate_kbps"] = round(int(raw_bitrate) / 1000)
            elif dur > 0 and result["size_bytes"] > 0:
                result["bitrate_kbps"] = round((result["size_bytes"] * 8) / (dur * 1000))
                
            fmt_name = fmt.get("format_name", "")
            if is_video:
                result["format"] = f"video/{ext.replace('.', '')}" if ext else "video/mp4"
            elif is_image:
                result["format"] = f"image/{ext.replace('.', '')}" if ext else "image/jpeg"
            elif "mp3" in fmt_name:
                result["format"] = "audio/mpeg"
            else:
                result["format"] = fmt_name or "media"

            for st in data.get("streams", []):
                ctype = st.get("codec_type")
                if ctype == "video" and not is_image:
                    result["video_codec"] = st.get("codec_name", "h264")
                    w = int(st.get("width", 0) or 0)
                    h = int(st.get("height", 0) or 0)
                    result["width"] = w
                    result["height"] = h
                    if w and h:
                        res_label = f"{w}x{h}"
                        if h == 1080: res_label += " (1080p FHD)"
                        elif h == 720: res_label += " (720p HD)"
                        elif h == 480: res_label += " (480p SD)"
                        elif h == 2160: res_label += " (4K UHD)"
                        result["resolution"] = res_label
                    
                    r_fps = st.get("r_frame_rate", "")
                    if "/" in r_fps:
                        try:
                            num, den = r_fps.split("/")
                            if float(den) > 0:
                                result["fps"] = f"{round(float(num) / float(den))} fps"
                        except Exception:
                            pass
                elif ctype == "audio":
                    result["audio_codec"] = st.get("codec_name", "aac" if is_video else "mp3")
                    if not is_video:
                        result["codec"] = result["audio_codec"]
                    result["sample_rate"] = int(st.get("sample_rate", 44100) or 44100)
                    ch = int(st.get("channels", 2) or 2)
                    result["channels"] = "Stereo (2 channels)" if ch >= 2 else "Mono (1 channel)"
    except Exception as e:
        logger.warning(f"Technical metadata inspection warning: {e}")
    return result

def inspect_audio_stream(file_path: str | Path) -> Dict[str, Any]:
    """
    Detailed extraction of audio stream specs (sample_rate, channels, bitrate) using ffprobe.
    """
    path = Path(file_path)
    result = {
        "sample_rate": 44100,
        "channels": 2,
        "bitrate_kbps": 192,
        "codec": "mp3",
        "duration_sec": 0
    }
    if not path.exists():
        return result
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", "-select_streams", "a:0", str(path)
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
        if p.returncode == 0 and p.stdout:
            data = json.loads(p.stdout)
            streams = data.get("streams", [])
            fmt = data.get("format", {})
            if streams:
                ast = streams[0]
                result["codec"] = ast.get("codec_name", "mp3")
                sr = ast.get("sample_rate")
                if sr and str(sr).isdigit():
                    result["sample_rate"] = int(sr)
                ch = ast.get("channels")
                if ch and str(ch).isdigit():
                    result["channels"] = int(ch)
                br = ast.get("bit_rate")
                if br and str(br).isdigit():
                    result["bitrate_kbps"] = max(64, min(320, round(int(br) / 1000)))
            
            if result["bitrate_kbps"] == 192 and fmt.get("bit_rate"):
                fbr = fmt.get("bit_rate")
                if fbr and str(fbr).isdigit():
                    result["bitrate_kbps"] = max(64, min(320, round(int(fbr) / 1000)))
            
            dur = fmt.get("duration") or (streams[0].get("duration") if streams else None)
            if dur:
                result["duration_sec"] = int(float(dur))
    except Exception as e:
        logger.warning(f"Audio stream inspect error: {e}")
    return result

def inspect_embedded_metadata(file_path: str | Path) -> Dict[str, Any]:
    path = Path(file_path)
    ext = path.suffix.lower()
    is_video = ext in VIDEO_EXTENSIONS
    is_image = ext in IMAGE_EXTENSIONS

    res = {
        "title": None, "artist": None, "album": None, "album_artist": None,
        "genre": None, "year": None, "track_number": None, "disc_number": None,
        "composer": None, "comment": None, "description": None, "subtitle": None,
        "category": None, "copyright": None, "encoder": None, "has_cover": False,
        "cover_mime": None, "cover_size_bytes": 0
    }
    if not path.exists():
        return res

    # 1. Deep Video & Image Inspection (FFprobe format & stream tags + QuickTime atoms)
    if is_video or is_image:
        try:
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
            if p.returncode == 0 and p.stdout:
                data = json.loads(p.stdout)
                all_tags = {}
                for k, v in data.get("format", {}).get("tags", {}).items():
                    all_tags[k.lower()] = str(v)
                for st in data.get("streams", []):
                    for k, v in st.get("tags", {}).items():
                        all_tags[k.lower()] = str(v)

                res["title"] = all_tags.get("title") or all_tags.get("name") or all_tags.get("xptitle")
                res["comment"] = all_tags.get("comment") or all_tags.get("usercomment") or all_tags.get("imagedescription") or all_tags.get("xpcomment")
                res["subtitle"] = all_tags.get("subtitle") or all_tags.get("description") or all_tags.get("synopsis")
                res["category"] = all_tags.get("category") or all_tags.get("genre")
                res["genre"] = res["category"]
                res["description"] = all_tags.get("description") or res["subtitle"]
                res["artist"] = all_tags.get("artist") or all_tags.get("author") or all_tags.get("xpauthor")
                res["album"] = all_tags.get("album")
                res["encoder"] = all_tags.get("encoder") or all_tags.get("software")
                res["year"] = all_tags.get("date") or all_tags.get("creation_time") or all_tags.get("year")
                res["copyright"] = all_tags.get("copyright")
        except Exception:
            pass
        return res

    # 2. Audio Inspection via Mutagen ID3 / MP4
    try:
        from mutagen.id3 import ID3
        audio = ID3(str(path))
        res["title"] = str(audio["TIT2"]) if "TIT2" in audio else None
        res["artist"] = str(audio["TPE1"]) if "TPE1" in audio else None
        res["album"] = str(audio["TALB"]) if "TALB" in audio else None
        res["album_artist"] = str(audio["TPE2"]) if "TPE2" in audio else None
        res["genre"] = str(audio["TCON"]) if "TCON" in audio else None
        res["year"] = str(audio["TYER"]) if "TYER" in audio else (str(audio["TDRC"]) if "TDRC" in audio else None)
        res["track_number"] = str(audio["TRCK"]) if "TRCK" in audio else None
        res["disc_number"] = str(audio["TPOS"]) if "TPOS" in audio else None
        res["composer"] = str(audio["TCOM"]) if "TCOM" in audio else None
        res["copyright"] = str(audio["TCOP"]) if "TCOP" in audio else None
        
        comm_key = [k for k in audio.keys() if k.startswith("COMM")]
        if comm_key:
            res["comment"] = str(audio[comm_key[0]])
            
        apic_keys = [k for k in audio.keys() if k.startswith("APIC")]
        if apic_keys:
            apic = audio[apic_keys[0]]
            res["has_cover"] = True
            res["cover_mime"] = getattr(apic, "mime", "image/jpeg")
            res["cover_size_bytes"] = len(getattr(apic, "data", b""))
        return res
    except Exception:
        pass

    # 3. Audio Inspection via FFprobe fallback
    try:
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
        if p.returncode == 0 and p.stdout:
            data = json.loads(p.stdout)
            all_tags = {}
            for k, v in data.get("format", {}).get("tags", {}).items():
                all_tags[k.lower()] = str(v)
            for st in data.get("streams", []):
                for k, v in st.get("tags", {}).items():
                    all_tags[k.lower()] = str(v)

            res["title"] = all_tags.get("title") or all_tags.get("name")
            res["artist"] = all_tags.get("artist") or all_tags.get("author") or all_tags.get("performer")
            res["album"] = all_tags.get("album")
            res["album_artist"] = all_tags.get("album_artist")
            res["genre"] = all_tags.get("genre")
            res["year"] = all_tags.get("date") or all_tags.get("year")
            res["comment"] = all_tags.get("comment")
    except Exception:
        pass
    return res

def inspect_all_metadata(file_path: str | Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    return inspect_technical_metadata(file_path), inspect_embedded_metadata(file_path)
