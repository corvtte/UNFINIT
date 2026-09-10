import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

from core.database import (
    db_save_media_session,
    db_get_media_session,
    db_get_all_media_sessions,
    db_delete_media_session,
    db_save_user_action,
    db_get_user_action,
    db_get_all_user_actions,
    db_clear_user_action
)

class SessionManager:
    """
    Persistent SessionManager backed by SQLite disk database (store_database.db).
    Ensures media drop sessions and user actions survive server restarts and redeployments,
    preventing 'Session or local binary not found' errors.
    """
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._user_actions: Dict[str, Dict[str, Any]] = {}
        self.load_from_disk()

    def load_from_disk(self):
        try:
            db_sess = db_get_all_media_sessions()
            if db_sess:
                if os.name != 'nt':
                    filtered = {}
                    for k, v in db_sess.items():
                        v_str = json.dumps(v)
                        if any(w in v_str for w in [":\\", "C:\\", "c:\\", "D:\\", "d:\\", "\\Users\\", "/Users/Sajjad"]):
                            v_clean = dict(v)
                            v_clean["is_downloaded_locally"] = False
                            v_clean["working_path"] = None
                            v_clean["compressed_path"] = None
                            v_clean["original_path"] = None
                            filtered[k] = v_clean
                            try:
                                db_save_media_session(k, v_clean)
                            except Exception:
                                pass
                        else:
                            filtered[k] = v
                    self._sessions.update(filtered)
                else:
                    self._sessions.update(db_sess)
            db_acts = db_get_all_user_actions()
            if db_acts:
                self._user_actions.update(db_acts)
        except Exception:
            pass

    def save_to_disk(self):
        # Kept for backward compatibility; individual actions write-through to SQLite
        try:
            for k, v in list(self._sessions.items()):
                db_save_media_session(k, v)
            for k, v in list(self._user_actions.items()):
                db_save_user_action(k, v.get("action", ""), v.get("drop_id", ""), v.get("extra", {}))
        except Exception:
            pass

    def create_session(self, drop_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        self._sessions[drop_id] = data
        try:
            db_save_media_session(drop_id, data)
        except Exception:
            pass
        return data

    def get_session(self, drop_id: str) -> Optional[Dict[str, Any]]:
        if not drop_id:
            return None
        drop_key = str(drop_id).strip()
        if drop_key in self._sessions:
            return self._sessions[drop_key]
        # Read-through cache from SQLite
        try:
            db_data = db_get_media_session(drop_key)
            if db_data:
                self._sessions[drop_key] = db_data
                return db_data
        except Exception:
            pass
        return None

    def update_session(self, drop_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        session = self.get_session(drop_id)
        if session is not None:
            session.update(updates)
        else:
            session = dict(updates)
            self._sessions[drop_id] = session
        try:
            db_save_media_session(drop_id, session)
        except Exception:
            pass
        return session

    def remove_session(self, drop_id: str) -> bool:
        existed = False
        if drop_id in self._sessions:
            del self._sessions[drop_id]
            existed = True
        try:
            db_res = db_delete_media_session(drop_id)
            if db_res:
                existed = True
        except Exception:
            pass
        return existed

    def set_user_action(self, user_key: str, action: str, drop_id: str, extra: Optional[Dict[str, Any]] = None):
        action_obj = {
            "action": action,
            "drop_id": drop_id,
            "extra": extra or {}
        }
        self._user_actions[user_key] = action_obj
        try:
            db_save_user_action(user_key, action, drop_id, extra or {})
        except Exception:
            pass

    def get_user_action(self, user_key: str) -> Optional[Dict[str, Any]]:
        if user_key in self._user_actions:
            return self._user_actions[user_key]
        try:
            db_act = db_get_user_action(user_key)
            if db_act:
                self._user_actions[user_key] = db_act
                return db_act
        except Exception:
            pass
        return None

    def clear_user_action(self, user_key: str):
        if user_key in self._user_actions:
            del self._user_actions[user_key]
        try:
            db_clear_user_action(user_key)
        except Exception:
            pass

session_manager = SessionManager()
