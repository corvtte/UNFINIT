import re

def add_audio_conversion():
    with open('services/media_service.py', 'r', encoding='utf-8') as f:
        text = f.read()

    new_method = """    @staticmethod
    def convert_audio_format(
        audio_path: str | Path,
        target_format: str, # e.g. "mp3", "ogg", "m4a", "wav"
        output_path: Optional[str | Path] = None
    ) -> Tuple[bool, Path]:
        from core.config import config
        from core.utils import inspect_audio_stream
        import subprocess, uuid, logging
        from pathlib import Path
        logger = logging.getLogger(__name__)

        a_path = Path(audio_path).resolve()
        if not a_path.exists():
            raise FileNotFoundError(f"Input audio file not found: {audio_path}")

        target_out = (Path(output_path) if output_path else config.TEMP_DIR / f"{a_path.stem}.{target_format}").resolve()
        target_out.parent.mkdir(parents=True, exist_ok=True)

        if target_out == a_path or target_out.exists():
            target_out = config.TEMP_DIR / f"converted_{a_path.stem}_{uuid.uuid4().hex[:6]}.{target_format}"
        target_out.parent.mkdir(parents=True, exist_ok=True)

        ast_info = inspect_audio_stream(a_path)
        sample_rate = ast_info.get("sample_rate", 44100)
        channels = ast_info.get("channels", 2)
        bitrate_kbps = ast_info.get("bitrate_kbps", 192)

        if target_format == "mp3":
            acodec = "libmp3lame"
        elif target_format == "ogg":
            acodec = "libvorbis"
        elif target_format == "m4a":
            acodec = "aac"
        elif target_format == "wav":
            acodec = "pcm_s16le"
        else:
            acodec = "copy"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(a_path),
            "-vn",
            "-acodec", acodec,
        ]
        
        if target_format != "wav":
            cmd.extend(["-b:a", f"{bitrate_kbps}k"])
        cmd.extend(["-ar", str(sample_rate), "-ac", str(channels), str(target_out)])
        
        logger.info(f"Converting {a_path.name} to {target_format.upper()}: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if res.returncode != 0 or not target_out.exists() or target_out.stat().st_size < 100:
            logger.error(f"FFmpeg audio conversion error: {res.stderr}")
            return False, target_out
            
        return True, target_out

"""

    # Add it right before convert_video_to_mp3
    if 'def convert_audio_format(' not in text:
        text = text.replace('    @classmethod\n    def convert_video_to_mp3(', new_method + '    @classmethod\n    def convert_video_to_mp3(')
        with open('services/media_service.py', 'w', encoding='utf-8') as f:
            f.write(text)
        print("Added convert_audio_format!")
    else:
        print("Already exists.")

add_audio_conversion()
