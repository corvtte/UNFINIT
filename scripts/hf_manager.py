#!/usr/bin/env python3
"""
UNFINIT Hugging Face Automation Manager
Provides programmatic control over:
- Space runtime status & live logs
- Space Secrets management (get, add, update, delete)
- Direct synchronization from local repository to Hugging Face Spaces
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_path)
    except Exception:
        pass
    if not os.environ.get("HF_TOKEN"):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("'").strip('"')
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

from huggingface_hub import HfApi

TOKEN = os.environ.get("HF_TOKEN")
REPO_ID = os.environ.get("HF_SPACE_ID", "Foadian/UNFINIT")
ROOT_DIR = Path(__file__).resolve().parent.parent

def get_api() -> HfApi:
    if not TOKEN:
        raise ValueError("HF_TOKEN is not set in environment or .env file!")
    return HfApi(token=TOKEN)

def cmd_status():
    api = get_api()
    user = api.whoami()
    print(f"🔑 Hugging Face User: {user.get('name')} ({user.get('fullname')})")
    print(f"📦 Target Space: {REPO_ID}")
    
    runtime = api.get_space_runtime(repo_id=REPO_ID)
    print(f"🚀 Space Runtime Stage: {runtime.stage}")
    print(f"💻 Hardware: {runtime.hardware}")
    
    commits = list(api.list_repo_commits(repo_id=REPO_ID, repo_type="space"))
    if commits:
        latest = commits[0]
        print(f"📌 Latest Commit: {latest.commit_id[:7]} - {latest.title} ({latest.created_at})")

def cmd_secrets():
    api = get_api()
    print(f"🔒 Space Secrets for {REPO_ID}:")
    secrets = api.get_space_secrets(repo_id=REPO_ID)
    if not secrets:
        print("  (No secrets configured)")
        return
    for k in sorted(secrets.keys()):
        sec = secrets[k]
        print(f"  - {k} (Updated: {sec.updated_at})")

def cmd_set_secret(key: str, val: str):
    api = get_api()
    print(f"⏳ Setting secret '{key}' in Space {REPO_ID}...")
    api.add_space_secret(repo_id=REPO_ID, key=key.strip(), value=str(val).strip())
    print(f"✅ Secret '{key}' successfully saved! Hugging Face Space will restart automatically.")

def cmd_del_secret(key: str):
    api = get_api()
    print(f"⏳ Deleting secret '{key}' from Space {REPO_ID}...")
    api.delete_space_secret(repo_id=REPO_ID, key=key.strip())
    print(f"✅ Secret '{key}' deleted successfully!")

def cmd_push_secrets():
    api = get_api()
    print(f"🔒 Syncing sensitive variables to Hugging Face Space Secrets ({REPO_ID})...")
    
    SECRET_KEYS = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_OWNER_ID",
        "BALE_BOT_TOKEN",
        "BALE_OWNER_ID",
        "BALE_PAYMENT_TOKEN",
        "RUBIKA_BOT_TOKEN",
        "RUBIKA_OWNER_ID",
        "CARD_NUMBER",
        "CARD_HOLDER",
        "GEMINI_API_KEY",
        "NARA_API_KEY",
        "ADMIN_PANEL_PASSWORD",
        "ZARINPAL_MERCHANT_ID",
        "HF_TOKEN",
    ]
    
    synced_count = 0
    for key in SECRET_KEYS:
        val = os.environ.get(key)
        if not val or not str(val).strip():
            continue
        val_str = str(val).strip()
        # Skip placeholders, defaults and masked secrets
        if val_str in ("unfinit2026", "your_strong_secret_password_here"):
            continue
        if "••••" in val_str or "****" in val_str:
            continue
        try:
            api.add_space_secret(repo_id=REPO_ID, key=key, value=val_str)
            print(f"  ✅ Synced secret: {key}")
            synced_count += 1
        except Exception as e:
            print(f"  ⚠️ Failed to sync {key}: {e}")
            
    print(f"✨ Total {synced_count} secrets synced to Space {REPO_ID} successfully.")

def cmd_logs(lines_count: int = 30):
    api = get_api()
    print(f"📋 Fetching last {lines_count} lines of live logs from {REPO_ID}...")
    try:
        all_logs = list(api.fetch_space_logs(repo_id=REPO_ID))
        for line in all_logs[-lines_count:]:
            print(line.strip())
    except Exception as e:
        print(f"❌ Error fetching logs: {e}")

def cmd_sync(message: Optional[str] = None):
    api = get_api()
    msg = message or "deploy: sync update from UNFINIT Store Engine"
    print(f"🚀 Synchronizing local codebase to Hugging Face Space ({REPO_ID})...")
    
    commit_info = api.upload_folder(
        folder_path=str(ROOT_DIR),
        repo_id=REPO_ID,
        repo_type="space",
        commit_message=msg,
        ignore_patterns=[
            ".git*",
            "__pycache__/*",
            "*.pyc",
            ".pytest_cache/*",
            ".coverage",
            "tests/*",
            "tests_archive/*",
            "scripts/*",
            "scratch/*",
            "*.session",
            "*.session-journal",
            "*.rubpy",
            "*.rp",
            "unfinit_instagram.json",
            "unfinit_session_cache.json",
            "sessions/*",
            "*.db",
            "*.sqlite*",
            ".env*"
        ]
    )
    print("✅ Deployment complete!")
    print(f"🌐 Commit URL: {commit_info.commit_url}")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/hf_manager.py status")
        print("  python scripts/hf_manager.py secrets")
        print("  python scripts/hf_manager.py set-secret <KEY> <VALUE>")
        print("  python scripts/hf_manager.py del-secret <KEY>")
        print("  python scripts/hf_manager.py push-secrets")
        print("  python scripts/hf_manager.py logs [lines]")
        print("  python scripts/hf_manager.py sync [message]")
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd == "status":
        cmd_status()
    elif cmd == "secrets":
        cmd_secrets()
    elif cmd == "push-secrets":
        cmd_push_secrets()
    elif cmd == "set-secret":
        if len(sys.argv) < 4:
            print("Error: specify KEY and VALUE")
            sys.exit(1)
        cmd_set_secret(sys.argv[2], sys.argv[3])
    elif cmd == "del-secret":
        if len(sys.argv) < 3:
            print("Error: specify KEY")
            sys.exit(1)
        cmd_del_secret(sys.argv[2])
    elif cmd == "logs":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        cmd_logs(count)
    elif cmd == "sync":
        msg = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_sync(msg)
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()
