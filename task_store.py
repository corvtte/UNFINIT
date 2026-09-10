from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from html import escape
from pathlib import Path
from typing import Callable, Optional, List

BASE_DIR = Path(__file__).resolve().parent

def default_data_dir() -> Path:
    configured = os.getenv("WALRUS_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if Path("/data").exists() and os.access("/data", os.W_OK):
        return Path("/data/walrus")
    return BASE_DIR / "data"

DATA_DIR = default_data_dir()
SESSION_DIR = DATA_DIR / "sessions"
DOWNLOAD_DIR = DATA_DIR / "downloads"
QUEUE_DIR = DATA_DIR / "queue"
QUEUE_FILE = QUEUE_DIR / "tasks.jsonl"
PROCESSING_FILE = QUEUE_DIR / "processing.json"
FAILED_FILE = QUEUE_DIR / "failed.jsonl"
COMPLETED_FILE = QUEUE_DIR / "completed.jsonl"
CANCEL_DIR = QUEUE_DIR / "cancelled"
SETTINGS_FILE = QUEUE_DIR / "settings.json"
TELEGRAM_EVENTS_FILE = QUEUE_DIR / "telegram_events.jsonl"
PROCESSING_ACTIVE_HEARTBEAT_SECONDS = int(os.getenv("WALRUS_PROCESSING_HEARTBEAT_SECONDS", "120"))
LRM = "\u200e"

def ensure_storage_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    CANCEL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from core.config import config
        config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        config.BANNERS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

def runtime_path(name_or_path: str | Path, base_dir: Path = SESSION_DIR) -> Path:
    path = Path(str(name_or_path)).expanduser()
    if path.is_absolute():
        return path
    return base_dir / path

def session_base_name(session_name: str | Path) -> str:
    path = runtime_path(session_name, SESSION_DIR)
    if path.suffix in {".rp", ".session", ".sqlite", ".rubpy"}:
        path = path.with_suffix("")
    return str(path)

def session_file_candidates(session_name: str) -> list[Path]:
    pure_name = Path(session_name).name
    if Path(pure_name).suffix in {".rp", ".session", ".sqlite", ".rubpy"}:
        pure_name = Path(pure_name).stem

    candidates: list[Path] = []
    
    # 1. Check in root/working dir
    for ext in ("", ".rubpy", ".session", ".rp", ".sqlite"):
        candidates.append(Path(f"{pure_name}{ext}"))
        candidates.append(BASE_DIR / f"{pure_name}{ext}")

    # 2. Check in SESSION_DIR
    for ext in ("", ".rubpy", ".session", ".rp", ".sqlite"):
        candidates.append(SESSION_DIR / f"{pure_name}{ext}")

    # 3. Check in standard /tmp and /data paths
    for base_p in (Path("/tmp/walrus/sessions"), Path("/data/walrus/sessions"), Path("/tmp")):
        for ext in ("", ".rubpy", ".session", ".rp", ".sqlite"):
            candidates.append(base_p / f"{pure_name}{ext}")

    unique_candidates: list[Path] = []
    for c in candidates:
        if c not in unique_candidates:
            unique_candidates.append(c)
    return unique_candidates

def _is_valid_rubika_session_file(p: Path) -> bool:
    if not p.exists() or not p.is_file() or p.stat().st_size == 0:
        return False
    try:
        import sqlite3
        with sqlite3.connect(str(p)) as con:
            res = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session'").fetchone()
            if res:
                rows = con.execute("SELECT auth FROM session WHERE auth IS NOT NULL AND length(auth) > 0").fetchall()
                if rows and rows[0][0]:
                    return True
    except Exception:
        pass
    return False

def find_existing_session_file(session_name: Optional[str] = None) -> Optional[Path]:
    names_to_try: list[str] = []
    if session_name:
        clean = Path(str(session_name)).stem.strip()
        if clean:
            names_to_try.append(clean)

    env_sess = os.getenv("RUBIKA_SESSION", "").strip()
    if env_sess:
        clean = Path(env_sess).stem.strip()
        if clean and clean not in names_to_try:
            names_to_try.append(clean)

    for fallback_name in ("unfinit_rubika", "rubika_user", "session", "user_session"):
        if fallback_name not in names_to_try:
            names_to_try.append(fallback_name)

    # 1. Try candidate paths for all possible names
    for name in names_to_try:
        for p in session_file_candidates(name):
            if _is_valid_rubika_session_file(p):
                return p

    # 2. Universal directory scan for any valid session file
    search_dirs = [
        BASE_DIR,
        SESSION_DIR,
        DATA_DIR,
        Path("."),
        Path("/tmp/walrus/sessions"),
        Path("/data/walrus/sessions"),
        Path("/tmp")
    ]
    for sdir in search_dirs:
        if sdir.exists() and sdir.is_dir():
            try:
                for ext in ("*.rp", "*.rubpy", "*.session", "*.sqlite"):
                    for fp in sdir.glob(ext):
                        if _is_valid_rubika_session_file(fp):
                            return fp
            except Exception:
                pass

    return None

def has_rubika_session(session_name: Optional[str] = None) -> bool:
    return find_existing_session_file(session_name) is not None

def safe_filename(name: Optional[str], default: str = "file.bin") -> str:
    normalized = unicodedata.normalize("NFKC", (name or "").strip())
    path = Path(normalized.replace("\\", "/")).name
    stem = Path(path).stem or "file"
    suffix = Path(path).suffix.lower() or Path(default).suffix.lower() or ".bin"
    return f"{stem[:100]}{suffix}"

def normalize_upload_filename(name: Optional[str], default: str = "file.bin") -> str:
    return safe_filename(name, default)

def split_name(filename: str) -> tuple[str, str]:
    path = Path(filename)
    return path.stem, path.suffix

def human_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    val = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if val < 1024.0 or unit == "TB":
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{size_bytes} B"

def human_speed(bytes_per_second: float | int | None) -> str:
    speed = float(bytes_per_second or 0)
    if speed <= 0:
        return "0 B/s"
    return f"{human_size(int(speed))}/s"

def human_duration(seconds: float | int | None) -> str:
    s = max(0, int(seconds or 0))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {sec}s"
    return f"{sec}s"

def progress_meter(percent: int, width: int = 10) -> str:
    percent = max(0, min(100, percent))
    filled = round((percent / 100) * width)
    filled = min(width, max(0, filled))
    return f"{'▰' * filled}{'▱' * (width - filled)}"

def truncate_middle(text: str, max_length: int = 42) -> str:
    text = (text or "").strip()
    if len(text) <= max_length:
        return text
    keep_left = max(8, (max_length - 3) // 2)
    keep_right = max(8, max_length - keep_left - 3)
    return f"{text[:keep_left]}...{text[-keep_right:]}"

def ltr_code(text: str) -> str:
    return f"<code>{LRM}{escape(text)}{LRM}</code>"

def build_status_text(
    *,
    task_id: str,
    file_name: str,
    file_size: int,
    stage: str,
    download_percent: int,
    upload_percent: int,
    upload_status: str,
    queue_position: int | None = None,
    note: str | None = None,
    attempt_text: str | None = None,
    speed_text: str | None = None,
    eta_text: str | None = None,
) -> str:
    safe_task_id = task_id or "-"
    safe_file_name = truncate_middle(file_name or "file")
    safe_stage = escape(stage)
    safe_upload_status = escape(upload_status)
    download_value = max(0, min(100, download_percent))
    upload_value = max(0, min(100, upload_percent))
    safe_size = human_size(file_size)

    lines = [
        "<b>⚡️ UNFINIT Multi-Platform Media Bridge</b>",
        f"📍 <b>وضعیت:</b> {safe_stage}",
        f"📝 <b>پیام:</b> {safe_upload_status}",
        "",
        f"📄 <b>فایل:</b> {ltr_code(safe_file_name)}",
        f"📦 <b>حجم:</b> {ltr_code(safe_size)}",
        f"🆔 <b>شناسه:</b> {ltr_code(safe_task_id)}",
        "",
        f"🚀 <b>پیشرفت ارسال:</b> <code>{progress_meter(upload_value)}</code> <b>{upload_value}%</b>",
    ]

    if attempt_text:
        lines.append(f"🔁 <b>تلاش:</b> {ltr_code(attempt_text)}")
    if speed_text:
        lines.append(f"⚡️ <b>سرعت:</b> {ltr_code(speed_text)}")
    if eta_text:
        lines.append(f"⏱ <b>زمان تقریبی:</b> {ltr_code(eta_text)}")
    if queue_position is not None:
        lines.append(f"⏳ <b>نوبت در صف:</b> {ltr_code(str(queue_position))}")
    if note:
        lines.append(escape(note))

    return "\n".join(lines)

def env_runtime_settings() -> dict:
    default_session = os.getenv("RUBIKA_SESSION", "unfinit_rubika").strip() or "unfinit_rubika"
    default_phone = os.getenv("RUBIKA_PHONE", "").strip()
    default_target = os.getenv("RUBIKA_TARGET", "me").strip() or "me"
    default_target_title = os.getenv("RUBIKA_TARGET_TITLE", "پیام‌های ذخیره‌شده (Saved Messages)").strip()
    default_bale_token = os.getenv("BALE_BOT_TOKEN", "").strip()
    default_bale_target = os.getenv("BALE_TARGET_CHAT_ID", "").strip()
    return {
        "rubika_session": default_session,
        "rubika_phone": default_phone,
        "rubika_target": default_target,
        "rubika_target_title": default_target_title,
        "rubika_target_type": "saved" if default_target == "me" else "custom",
        "bale_token": default_bale_token,
        "bale_target": default_bale_target,
    }

def normalize_runtime_settings(settings: Optional[dict] = None) -> dict:
    settings = settings or {}
    defaults = env_runtime_settings()
    return {
        "rubika_session": str(settings.get("rubika_session") or defaults["rubika_session"]).strip(),
        "rubika_phone": str(settings.get("rubika_phone") or defaults["rubika_phone"]).strip(),
        "rubika_target": str(settings.get("rubika_target") or defaults["rubika_target"]).strip(),
        "rubika_target_title": str(settings.get("rubika_target_title") or defaults["rubika_target_title"]).strip(),
        "rubika_target_type": str(settings.get("rubika_target_type") or defaults["rubika_target_type"]).strip(),
        "bale_token": str(settings.get("bale_token") or defaults["bale_token"]).strip(),
        "bale_target": str(settings.get("bale_target") or defaults["bale_target"]).strip(),
    }

def load_runtime_settings() -> dict:
    ensure_storage_dirs()
    if not SETTINGS_FILE.exists():
        return normalize_runtime_settings()
    try:
        return normalize_runtime_settings(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except Exception:
        return normalize_runtime_settings()

def save_runtime_settings(settings: dict) -> dict:
    ensure_storage_dirs()
    normalized = normalize_runtime_settings(settings)
    temp_path = SETTINGS_FILE.with_suffix(".tmp")
    temp_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(SETTINGS_FILE)
    return normalized

def apply_runtime_settings(task: dict, settings: Optional[dict] = None) -> dict:
    runtime_settings = normalize_runtime_settings(settings or load_runtime_settings())
    task["rubika_session"] = runtime_settings["rubika_session"]
    task["rubika_target"] = runtime_settings["rubika_target"]
    task["rubika_target_title"] = runtime_settings["rubika_target_title"]
    task["rubika_target_type"] = runtime_settings["rubika_target_type"]
    if runtime_settings.get("bale_token") and not task.get("bale_token"):
        task["bale_token"] = runtime_settings["bale_token"]
    if runtime_settings.get("bale_target") and not task.get("bale_target"):
        task["bale_target"] = runtime_settings["bale_target"]
    return task

def append_task(task: dict) -> None:
    ensure_storage_dirs()
    with open(QUEUE_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(task, ensure_ascii=False) + "\n")
        file.flush()
        os.fsync(file.fileno())

def append_telegram_event(event: dict) -> None:
    ensure_storage_dirs()
    payload = {"created_at": time.time(), **event}
    with open(TELEGRAM_EVENTS_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        file.flush()
        os.fsync(file.fileno())

def pop_telegram_events() -> list[dict]:
    if not TELEGRAM_EVENTS_FILE.exists():
        return []
    drain_path = TELEGRAM_EVENTS_FILE.with_name(f"{TELEGRAM_EVENTS_FILE.name}.{os.getpid()}.{time.time_ns()}.drain")
    try:
        TELEGRAM_EVENTS_FILE.replace(drain_path)
    except FileNotFoundError:
        return []
    events = []
    try:
        with open(drain_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    finally:
        try:
            drain_path.unlink()
        except OSError:
            pass
    return events

def read_queue_tasks() -> list[dict]:
    if not QUEUE_FILE.exists():
        return []
    tasks = []
    with open(QUEUE_FILE, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                try:
                    tasks.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return tasks

def write_queue_tasks(tasks: list[dict]) -> None:
    ensure_storage_dirs()
    temp_path = QUEUE_FILE.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as file:
        for task in tasks:
            file.write(json.dumps(task, ensure_ascii=False) + "\n")
    temp_path.replace(QUEUE_FILE)

def queue_size() -> int:
    return len(read_queue_tasks())

def find_queued_task(matcher: Callable[[dict], bool]) -> Optional[dict]:
    for task in read_queue_tasks():
        if matcher(task):
            return task
    return None

def remove_queued_task(task_id: str) -> Optional[dict]:
    tasks = read_queue_tasks()
    remaining = []
    removed = None
    for task in tasks:
        if removed is None and task.get("task_id") == task_id:
            removed = task
            continue
        remaining.append(task)
    if removed is not None:
        write_queue_tasks(remaining)
    return removed

def pop_first_task(destination: str | None = None) -> Optional[dict]:
    tasks = read_queue_tasks()
    if not tasks:
        return None
    if destination:
        for i, t in enumerate(tasks):
            t_dest = t.get("destination") or "rubika"
            if t_dest == destination:
                write_queue_tasks(tasks[:i] + tasks[i+1:])
                return t
        return None
    first_task = tasks[0]
    write_queue_tasks(tasks[1:])
    return first_task

def save_processing(task: dict) -> None:
    ensure_storage_dirs()
    task["processing_updated_at"] = time.time()
    temp_path = PROCESSING_FILE.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(task, file, ensure_ascii=False, indent=2)
    temp_path.replace(PROCESSING_FILE)

def load_processing() -> Optional[dict]:
    if not PROCESSING_FILE.exists():
        return None
    try:
        with open(PROCESSING_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None

def clear_processing() -> None:
    if PROCESSING_FILE.exists():
        try:
            PROCESSING_FILE.unlink()
        except OSError:
            pass

def append_failed(task: dict, error: str) -> None:
    ensure_storage_dirs()
    payload = {"task": task, "error": error, "failed_at": time.time()}
    with open(FAILED_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")

def append_completed(task: dict) -> None:
    ensure_storage_dirs()
    payload = {"task": task, "completed_at": time.time()}
    with open(COMPLETED_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")

def read_failed_entries() -> list[dict]:
    if not FAILED_FILE.exists():
        return []
    entries = []
    with open(FAILED_FILE, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries

def read_completed_entries() -> list[dict]:
    if not COMPLETED_FILE.exists():
        return []
    entries = []
    with open(COMPLETED_FILE, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries

def cancel_path(task_id: str) -> Path:
    return CANCEL_DIR / f"{task_id}.cancel"

def mark_cancelled(task_id: str) -> None:
    ensure_storage_dirs()
    cancel_path(task_id).write_text("cancelled", encoding="utf-8")

def is_cancelled(task_id: str) -> bool:
    return cancel_path(task_id).exists()

def clear_cancelled(task_id: str) -> None:
    p = cancel_path(task_id)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass

def cleanup_local_file(path_like: str | Path | None) -> None:
    if not path_like:
        return
    p = Path(path_like)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass

def processing_task_is_active(task: dict | None) -> bool:
    if not task:
        return False
    updated_at = float(task.get("processing_updated_at") or 0)
    if updated_at <= 0:
        return False
    if time.time() - updated_at > PROCESSING_ACTIVE_HEARTBEAT_SECONDS:
        return False
    return True

WORKER_PID_FILE = QUEUE_DIR / "worker.pid"

def save_worker_pid(pid: int) -> None:
    ensure_storage_dirs()
    WORKER_PID_FILE.write_text(str(pid), encoding="utf-8")

def load_worker_pid() -> Optional[int]:
    if not WORKER_PID_FILE.exists():
        return None
    try:
        return int(WORKER_PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        return None

def clear_worker_pid() -> None:
    if WORKER_PID_FILE.exists():
        try:
            WORKER_PID_FILE.unlink()
        except OSError:
            pass

def find_failed_entry(task_id: str) -> Optional[dict]:
    for entry in reversed(read_failed_entries()):
        task = entry.get("task") or {}
        if task.get("task_id") == task_id:
            return entry
    return None
