import re
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from core.config import config
from core.logger import get_logger
from services.media_service import clean_display_filename

logger = get_logger("url_service")

class UrlService:
    @staticmethod
    async def probe_url(url: str) -> Dict[str, Any]:
        """
        Extracts metadata from direct HTTP/HTTPS URL via HEAD and GET range requests.
        """
        clean_url = url.strip()
        result = {
            "url": clean_url,
            "filename": "downloaded_file.bin",
            "file_size": 0,
            "content_type": "",
            "is_valid": True,
            "media_type": "document"
        }

        # Extract filename fallback from URL path
        parsed = urllib.parse.urlparse(clean_url)
        path_name = Path(urllib.parse.unquote(parsed.path)).name
        if path_name and "." in path_name:
            result["filename"] = clean_display_filename(path_name)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=15, connect=10)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.head(clean_url, allow_redirects=True) as resp:
                    if resp.status in (200, 206):
                        result["is_valid"] = True
                        result["file_size"] = int(resp.headers.get("Content-Length", 0) or 0)
                        result["content_type"] = resp.headers.get("Content-Type", "")
                        
                        cd = resp.headers.get("Content-Disposition", "")
                        if cd and "filename=" in cd:
                            match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)["\']?', cd, re.IGNORECASE)
                            if match:
                                result["filename"] = clean_display_filename(urllib.parse.unquote(match.group(1).strip()))

                if result["file_size"] == 0:
                    range_headers = {**headers, "Range": "bytes=0-10"}
                    async with session.get(clean_url, headers=range_headers, allow_redirects=True) as g_resp:
                        if g_resp.status in (200, 206):
                            cr = g_resp.headers.get("Content-Range", "")
                            if cr and "/" in cr:
                                total_str = cr.split("/")[1]
                                if total_str.isdigit():
                                    result["file_size"] = int(total_str)
                            if result["file_size"] == 0:
                                result["file_size"] = int(g_resp.headers.get("Content-Length", 0) or 0)
                            
                            cd = g_resp.headers.get("Content-Disposition", "")
                            if cd and "filename=" in cd:
                                match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)["\']?', cd, re.IGNORECASE)
                                if match:
                                    result["filename"] = clean_display_filename(urllib.parse.unquote(match.group(1).strip()))

        except Exception as e:
            logger.warning(f"URL probe notice for {clean_url}: {e}")

        fn_lower = result["filename"].lower()
        if fn_lower.endswith((".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac", ".opus")):
            result["media_type"] = "audio"
        elif fn_lower.endswith((".mp4", ".mkv", ".avi", ".mov", ".webm")):
            result["media_type"] = "video"
        else:
            result["media_type"] = "document"

        return result

    @staticmethod
    async def download_file_stream(
        url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Streams download of direct URL to destination disk path with progress reporting.
        """
        import aiohttp
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dest = dest_path.with_suffix(dest_path.suffix + ".part")

        try:
            timeout = aiohttp.ClientTimeout(total=1800, connect=20)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status not in (200, 206):
                        logger.error(f"URL download failed with status {resp.status}")
                        return False

                    total_size = int(resp.headers.get("Content-Length", 0) or 0)
                    downloaded = 0
                    chunk_size = 256 * 1024

                    with open(temp_dest, "wb") as f:
                        while True:
                            chunk = await resp.content.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size > 0:
                                progress_callback(downloaded, total_size)

                    temp_dest.replace(dest_path)
                    return True
        except Exception as e:
            logger.error(f"URL download streaming error: {e}")
            if temp_dest.exists():
                temp_dest.unlink()
            return False
