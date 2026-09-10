from __future__ import annotations

import asyncio
import atexit
from html import escape
import os
import time
from pathlib import Path
from typing import Optional, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from rubpy import Client as RubikaClient

from task_store import (
    DATA_DIR,
    QUEUE_FILE,
    append_completed,
    append_failed,
    append_telegram_event,
    build_status_text,
    clear_cancelled,
    clear_processing,
    clear_worker_pid,
    cleanup_local_file,
    ensure_storage_dirs,
    has_rubika_session,
    human_duration,
    human_speed,
    is_cancelled,
    load_runtime_settings,
    load_processing,
    normalize_runtime_settings,
    normalize_upload_filename,
    pop_first_task,
    queue_size,
    save_worker_pid,
    save_processing,
    safe_filename,
    session_file_candidates,
)
from services.media_service import clean_display_filename

MAX_RETRIES = 5
RETRY_DELAY = 3
ERROR_TEXT_LIMIT = 220
RUBIKA_CONNECT_TIMEOUT = int(os.getenv("RUBIKA_CONNECT_TIMEOUT", "25") or 25)
RUBIKA_FINALIZE_RETRIES = int(os.getenv("RUBIKA_FINALIZE_RETRIES", "3") or 3)
RUBIKA_FINALIZE_RETRY_DELAY = float(os.getenv("RUBIKA_FINALIZE_RETRY_DELAY", "2") or 2)

ensure_storage_dirs()

UPLOAD_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v",
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp",
    ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac",
    ".pdf", ".txt", ".csv", ".json",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v"}


class CancelledTaskError(RuntimeError):
    pass


class RubikaConnectTimeoutError(TimeoutError):
    pass


class MissingRubikaSessionError(RuntimeError):
    pass


def worker_log(message: str) -> None:
    print(f"Rubika worker: {message}", flush=True)


def get_file_duration_sec(file_path: Path | str) -> int:
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(str(file_path))
        if audio and audio.info and getattr(audio.info, "length", None):
            dur = int(round(audio.info.length))
            if dur > 0:
                return dur
    except Exception:
        pass
    return 1


def ensure_session(session_name: str) -> None:
    if has_rubika_session(session_name):
        return
    candidates = ", ".join(str(path) for path in session_file_candidates(session_name))
    raise MissingRubikaSessionError(
        "Rubika account is not set up. Open the Telegram bot and run /start or /set_rubika. "
        f"Checked: {candidates}"
    )


def resolve_task_settings(task: dict) -> dict:
    current_settings = load_runtime_settings()
    return normalize_runtime_settings(
        {
            "rubika_session": task.get("rubika_session") or current_settings["rubika_session"],
            "rubika_target": task.get("rubika_target") or current_settings["rubika_target"],
            "rubika_target_title": (
                task.get("rubika_target_title") or current_settings["rubika_target_title"]
            ),
            "rubika_target_type": (
                task.get("rubika_target_type") or current_settings["rubika_target_type"]
            ),
        }
    )


def format_destination_label(settings: dict) -> str:
    return str(settings.get("rubika_target_title") or "Saved Messages")


def update_telegram_status(
    task: dict,
    stage: str,
    upload_status: str,
    note: str | None = None,
    attempt_text: str | None = None,
    action: str | None = "cancel",
) -> None:
    chat_id = task.get("chat_id")
    status_message_id = task.get("status_message_id")
    if not chat_id or not status_message_id:
        return

    clean_name = clean_display_filename(task.get("file_name", Path(task.get("path", "")).name or "file"))
    payload = {
        "chat_id": chat_id,
        "message_id": status_message_id,
        "text": build_status_text(
            task_id=task.get("task_id", "-"),
            file_name=clean_name,
            file_size=int(task.get("file_size", 0) or 0),
            stage=stage,
            download_percent=100,
            upload_percent=int(task.get("upload_percent", 0) or 0),
            upload_status=upload_status,
            note=note,
            attempt_text=attempt_text or task.get("attempt_text"),
            speed_text=task.get("speed_text"),
            eta_text=task.get("eta_text"),
        ),
        "parse_mode": "HTML",
    }

    task_id = task.get("task_id", "")
    if action and task_id:
        label = "🔁 Retry" if action == "retry" else "🛑 Cancel"
        payload["reply_markup"] = {
            "inline_keyboard": [
                [{"text": label, "callback_data": f"{action}:{task_id}"}]
            ]
        }
    else:
        payload["reply_markup"] = {"inline_keyboard": []}

    append_telegram_event(
        {
            "type": "edit_message_text",
            "task_id": task_id,
            "payload": payload,
        }
    )


def send_telegram_message(
    chat_id: int,
    text: str,
    reply_to_message_id: int | None = None,
) -> None:
    if not chat_id:
        return
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    append_telegram_event({"type": "send_message", "payload": payload})


def rubika_inline_type(task: dict, file_path: str, file_name: str | None = None) -> str:
    suffix = Path(file_name or file_path).suffix.lower()
    media_type = str(task.get("media_type") or "").lower()
    if media_type == "video" or suffix in VIDEO_EXTENSIONS:
        return "Video"
    if media_type == "photo" or suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
        return "Image"
    if media_type in {"audio", "voice"} or suffix in {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}:
        return "Music"
    return "File"


def build_file_inline_payload(uploaded_file: dict, inline_type: str, duration: int = 1) -> dict:
    payload = dict(uploaded_file)
    payload.update(
        {
            "type": inline_type,
            "time": max(1, duration),
            "width": 200,
            "height": 200,
            "music_performer": "",
            "is_spoil": False,
        }
    )
    return payload


def build_file_inline_variants(uploaded_file: dict, preferred_type: str, duration: int = 1) -> list[tuple[str, dict]]:
    variants = [(preferred_type.lower(), build_file_inline_payload(uploaded_file, preferred_type, duration))]
    if preferred_type != "File":
        variants.append(("file", build_file_inline_payload(uploaded_file, "File", duration)))
    return variants


async def send_document(
    session_name: str,
    target: str,
    file_path: str,
    caption: str = "",
    callback=None,
    file_name: str | None = None,
    task: dict | None = None,
):
    client = RubikaClient(name=session_name)
    entered = False
    task = task or {}
    task_id = task.get("task_id", "")
    upload_name = clean_display_filename(file_name or Path(file_path).name)
    duration = get_file_duration_sec(file_path)

    try:
        from platforms.rubika_adapter import setup_rubika_client
        client = await setup_rubika_client(client, timeout=RUBIKA_CONNECT_TIMEOUT)
        entered = True
    except asyncio.TimeoutError as exc:
        raise RubikaConnectTimeoutError(
            f"Rubika connection timed out after {RUBIKA_CONNECT_TIMEOUT}s."
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Error establishing Rubika connection: {exc}") from exc

    if not getattr(client, "auth", None):
        try:
            await client.disconnect()
        except Exception:
            pass
        raise MissingRubikaSessionError("Rubika account is not authorized in session file.")

    try:
        uploaded = await client.upload(
            file_path,
            callback=callback,
            file_name=upload_name,
        )
        if is_cancelled(task_id):
            raise CancelledTaskError("Cancelled by user.")

        if isinstance(uploaded, dict):
            file_inline = dict(uploaded)
        elif callable(getattr(uploaded, "to_dict", None)):
            res = uploaded.to_dict()
            file_inline = dict(res) if isinstance(res, dict) else {}
        elif hasattr(uploaded, "to_dict") and isinstance(uploaded.to_dict, dict):
            file_inline = dict(uploaded.to_dict)
        else:
            file_inline = dict(uploaded) if hasattr(uploaded, "__iter__") else dict(getattr(uploaded, "__dict__", {}))
        inline_type = rubika_inline_type(task, file_path, upload_name)
        finalize_variants = build_file_inline_variants(file_inline, inline_type, duration=duration)

        dest_target = client.guid if (not target or target == "me") else target
        last_error = None
        for strategy, candidate_file_inline in finalize_variants:
            for attempt in range(1, RUBIKA_FINALIZE_RETRIES + 1):
                if is_cancelled(task_id):
                    raise CancelledTaskError("Cancelled by user.")
                try:
                    result = await client.send_message(
                        object_guid=dest_target,
                        text=caption.strip() if caption and caption.strip() else None,
                        file_inline=candidate_file_inline,
                    )
                    return result
                except Exception as error:
                    last_error = error
                    await asyncio.sleep(RUBIKA_FINALIZE_RETRY_DELAY * attempt)
        raise last_error if last_error else RuntimeError("Rubika finalization failed.")
    finally:
        if entered:
            try:
                await client.disconnect()
            except Exception:
                pass


def process_rubika_task(task: dict) -> None:
    task_id = task.get("task_id", "")
    caption = task.get("caption", "")
    original_path = Path(task.get("path", ""))
    if not original_path.exists():
        worker_log(f"Local file not found for task {task_id}: {original_path}. Skipping.")
        append_failed(task, "Local file not found.")
        clear_cancelled(task_id)
        return

    settings = resolve_task_settings(task)
    send_name = clean_display_filename(task.get("file_name") or original_path.name)

    try:
        if is_cancelled(task_id):
            raise CancelledTaskError("Cancelled before upload started.")

        ensure_session(settings["rubika_session"])
        update_telegram_status(
            task,
            stage="⏳ آماده‌سازی فایل",
            upload_status=f"در حال آماده‌سازی فایل جهت انتقال به {format_destination_label(settings)}...",
        )

        task["file_name"] = send_name
        save_processing(task)

        # Progress callback wrapper strictly clamped to 100%
        last_tick = [0.0]
        def progress_cb(a, b):
            now = time.time()
            if now - last_tick[0] >= 1.5 or a == b:
                last_tick[0] = now
                # In rubpy: callback(file_size, uploaded_bytes) -> total, current
                # Support both (current, total) and (total, current)
                if a >= b and b >= 0:
                    total, current = a, b
                else:
                    current, total = a, b
                if total > 0:
                    pct = min(100, max(0, int((current / total) * 100)))
                    task["upload_percent"] = pct
                    mb_cur = current / (1024 * 1024)
                    mb_tot = total / (1024 * 1024)
                    update_telegram_status(
                        task,
                        stage="📤 در حال آپلود به روبیکا",
                        upload_status=f"در حال آپلود: {pct}% ({mb_cur:.1f} MB از {mb_tot:.1f} MB)",
                    )

        asyncio.run(
            send_document(
                settings["rubika_session"],
                settings["rubika_target"],
                str(original_path),
                caption,
                callback=progress_cb,
                file_name=send_name,
                task=task,
            )
        )
    except CancelledTaskError:
        cleanup_local_file(str(original_path))
        clear_cancelled(task_id)
        update_telegram_status(task, stage="🛑 لغو شده", upload_status="فرآیند انتقال متوقف گردید.", action=None)
        return
    except Exception:
        cleanup_local_file(str(original_path))
        clear_cancelled(task_id)
        raise
    finally:
        cleanup_local_file(str(original_path))

    clear_cancelled(task_id)
    task["upload_percent"] = 100
    save_processing(task)
    append_completed(task)
    update_telegram_status(
        task,
        stage="✅ ارسال با موفقیت انجام شد",
        upload_status=f"فایل با موفقیت به {format_destination_label(settings)} منتقل گردید.",
        action=None,
    )
    send_telegram_message(
        int(task.get("chat_id")),
        f"<b>✅ انتقال فایل به روبیکا تکمیل شد</b>\n📄 <b>فایل:</b> <code>{escape(send_name)}</code>\n📬 <b>مقصد:</b> <code>{escape(format_destination_label(settings))}</code>",
        reply_to_message_id=task.get("status_message_id"),
    )


async def run_rubika_worker_async(telegram_adapter=None) -> None:
    worker_log("Rubika async task queue worker loop active.")
    while True:
        try:
            task = pop_first_task(destination="rubika")
            if not task:
                await asyncio.sleep(0.5)
                continue

            worker_log(f"picked Rubika task id={task.get('task_id', '-')}")
            save_processing(task)
            try:
                await asyncio.to_thread(process_rubika_task, task)
                worker_log(f"completed Rubika task id={task.get('task_id', '-')}")
            except Exception as e:
                worker_log(f"failed Rubika task id={task.get('task_id', '-')} error={e}")
                append_failed(task, str(e))
            finally:
                clear_processing()

        except Exception as e:
            worker_log(f"worker loop error: {e}")
            await asyncio.sleep(2.0)


def rubika_worker_loop() -> None:
    worker_log("Rubika worker started.")
    while True:
        task = pop_first_task(destination="rubika")
        if not task:
            time.sleep(0.5)
            continue
        worker_log(f"picked Rubika task id={task.get('task_id', '-')}")
        save_processing(task)
        try:
            process_rubika_task(task)
            worker_log(f"completed Rubika task id={task.get('task_id', '-')}")
        except Exception as e:
            worker_log(f"failed Rubika task id={task.get('task_id', '-')} error={e}")
            append_failed(task, str(e))
        finally:
            clear_processing()


if __name__ == "__main__":
    rubika_worker_loop()
