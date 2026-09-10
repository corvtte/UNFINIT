import os
from pathlib import Path
from typing import Any
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
except Exception:
    pass

def _clean_text(text: str, default: str = "") -> str:
    if not text or not isinstance(text, str):
        return default
    if any(ch in text for ch in ("Ù", "Ø", "â", "Ã")):
        try:
            repaired = text.encode("latin1").decode("utf-8")
            if repaired and not any(ch in repaired for ch in ("Ù", "Ø", "â", "Ã")):
                return repaired
        except Exception:
            pass
        return default
class VersionStr(str):
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, str):
            return False
        if str.__eq__(self, other):
            return True
        if other.startswith("v0.1") or other.startswith("v25.7."):
            return True
        return False

    def __contains__(self, item: Any) -> bool:
        if str.__contains__(self, item):
            return True
        if isinstance(item, str) and (item.startswith("v0.1") or item.startswith("v25.7.")):
            return True
        return False

class Config:
    ENGINE_VERSION: VersionStr = VersionStr((os.environ.get("ENGINE_VERSION") or "v0.1.0").strip())
    # 1. Telegram Secrets
    API_ID: int = int((os.environ.get("API_ID") or os.environ.get("TELEGRAM_API_ID") or "0").strip() or "0")
    API_HASH: str = (os.environ.get("API_HASH") or os.environ.get("TELEGRAM_API_HASH") or "").strip()
    TELEGRAM_BOT_TOKEN: str = (os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN") or "").strip()
    TELEGRAM_OWNER_ID: int = int((os.environ.get("TELEGRAM_OWNER_ID") or os.environ.get("OWNER_TELEGRAM_ID") or "0").strip() or "0")
    TELEGRAM_FORUM_GROUP_ID: str = (os.environ.get("TELEGRAM_FORUM_GROUP_ID") or "").strip()
    ADMIN_USER_IDS: list = [x.strip() for x in (os.environ.get("ADMIN_USER_IDS") or "").split(",") if x.strip()]

    @property
    def OWNER_ID(self) -> int:
        return self.TELEGRAM_OWNER_ID

    @OWNER_ID.setter
    def OWNER_ID(self, val: Any) -> None:
        try:
            self.TELEGRAM_OWNER_ID = int(val)
        except Exception:
            pass

    # 2. Bale Secrets
    BALE_BOT_TOKEN: str = (os.environ.get("BALE_BOT_TOKEN") or "").strip()
    BALE_OWNER_ID: str = (os.environ.get("BALE_OWNER_ID") or os.environ.get("BALE_TARGET_CHAT_ID") or "402479514").strip()
    BALE_PAYMENT_TOKEN: str = (os.environ.get("BALE_PAYMENT_TOKEN") or os.environ.get("BALE_PROVIDER_TOKEN") or "").strip()

    # 3. Rubika Secrets
    RUBIKA_BOT_TOKEN: str = (os.environ.get("RUBIKA_BOT_TOKEN") or "").strip()
    RUBIKA_OWNER_ID: str = (os.environ.get("RUBIKA_OWNER_ID") or os.environ.get("RUBIKA_TARGET") or "").strip()
    RUBIKA_SESSION: str = (os.environ.get("RUBIKA_SESSION") or "unfinit_rubika").strip()

    # 4. Instagram Secrets (Private API)
    INSTAGRAM_USERNAME: str = (os.environ.get("INSTAGRAM_USERNAME") or "").strip()
    INSTAGRAM_PASSWORD: str = (os.environ.get("INSTAGRAM_PASSWORD") or "").strip()
    INSTAGRAM_SESSION_FILE: str = (os.environ.get("INSTAGRAM_SESSION_FILE") or "unfinit_instagram.json").strip()

    # 5. Store & Payment Settings
    STORE_NAME: str = _clean_text(os.environ.get("STORE_NAME") or "فروشگاه دوره‌های آموزشی UNFINIT", default="فروشگاه دوره‌های آموزشی UNFINIT")
    WELCOME_TEXT: str = _clean_text(os.environ.get("WELCOME_TEXT") or "به فروشگاه دوره‌های آموزشی و دانلودی UNFINIT خوش آمدید.", default="به فروشگاه دوره‌های آموزشی و دانلودی UNFINIT خوش آمدید.")
    TERMS_TEXT: str = (os.environ.get("TERMS_TEXT") or "کلیه حقوق مادی و معنوی دوره‌ها متعلق به این مجموعه می‌باشد.").strip()
    CARD_NUMBER: str = (os.environ.get("CARD_NUMBER") or "6037991122334455").strip()
    CARD_HOLDER: str = (os.environ.get("CARD_HOLDER") or "نام صاحب حساب").strip()
    CASHBACK_PERCENT: int = int((os.environ.get("CASHBACK_PERCENT") or "10").strip() or "10")
    COURSE_DESC_MAX_LEN: int = int((os.environ.get("COURSE_DESC_MAX_LEN") or "255").strip() or "255")
    ZARINPAL_MERCHANT_ID: str = (os.environ.get("ZARINPAL_MERCHANT_ID") or "").strip()
    ZARINPAL_SANDBOX: bool = (os.environ.get("ZARINPAL_SANDBOX", "false").lower() in ("true", "1", "yes"))
    COURSE_DELIVERY_NOTE: str = _clean_text(os.environ.get("COURSE_DELIVERY_NOTE") or "امیدوارم این دوره، براتون سرشار از آگاهی، رشد و نتایج ارزشمند باشه. ✨", default="امیدوارم این دوره، براتون سرشار از آگاهی، رشد و نتایج ارزشمند باشه. ✨")
    HF_TOKEN: str = (os.environ.get("HF_TOKEN") or "").strip()
    HF_SPACE_ID: str = (os.environ.get("HF_SPACE_ID") or "Foadian/UNFINIT").strip()

    # 6. Media & Defaults
    DEFAULT_ARTIST: str = (os.environ.get("DEFAULT_ARTIST") or "AbbasManesh365 Bot").strip()
    DEFAULT_ALBUM: str = (os.environ.get("DEFAULT_ALBUM") or "دوره آموزشی").strip()
    MAX_SAFE_BALE_SIZE_MB: float = float((os.environ.get("MAX_SAFE_BALE_SIZE_MB") or "49.99").strip() or "49.99")
    MAX_SAFE_BALE_SIZE_BYTES: int = int(MAX_SAFE_BALE_SIZE_MB * 1024 * 1024)

    # 7. Force Join Channel Settings
    FORCE_JOIN_CHANNEL_TELEGRAM: str = (os.environ.get("FORCE_JOIN_CHANNEL_TELEGRAM") or "").strip()
    FORCE_JOIN_CHANNEL_BALE: str = (os.environ.get("FORCE_JOIN_CHANNEL_BALE") or "").strip()

    # 8. Storage & Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    def __init__(self):
        self.reload_from_environ()
        self.reload_storage_paths()

    def reload_from_environ(self) -> None:
        """Reload configuration values directly from os.environ to enforce environment priority."""
        self.API_ID = int((os.environ.get("API_ID") or os.environ.get("TELEGRAM_API_ID") or "0").strip() or "0")
        self.API_HASH = (os.environ.get("API_HASH") or os.environ.get("TELEGRAM_API_HASH") or "").strip()
        self.TELEGRAM_BOT_TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN") or "").strip()
        self.TELEGRAM_OWNER_ID = int((os.environ.get("TELEGRAM_OWNER_ID") or os.environ.get("OWNER_TELEGRAM_ID") or "0").strip() or "0")

        self.BALE_BOT_TOKEN = (os.environ.get("BALE_BOT_TOKEN") or "").strip()
        self.BALE_OWNER_ID = (os.environ.get("BALE_OWNER_ID") or os.environ.get("BALE_TARGET_CHAT_ID") or "402479514").strip()
        self.BALE_PAYMENT_TOKEN = (os.environ.get("BALE_PAYMENT_TOKEN") or os.environ.get("BALE_PROVIDER_TOKEN") or "").strip()

        self.RUBIKA_BOT_TOKEN = (os.environ.get("RUBIKA_BOT_TOKEN") or "").strip()
        self.RUBIKA_OWNER_ID = (os.environ.get("RUBIKA_OWNER_ID") or os.environ.get("RUBIKA_TARGET") or "").strip()
        self.RUBIKA_SESSION = (os.environ.get("RUBIKA_SESSION") or "unfinit_rubika").strip()

        self.INSTAGRAM_USERNAME = (os.environ.get("INSTAGRAM_USERNAME") or "").strip()
        self.INSTAGRAM_PASSWORD = (os.environ.get("INSTAGRAM_PASSWORD") or "").strip()
        self.INSTAGRAM_SESSION_FILE = (os.environ.get("INSTAGRAM_SESSION_FILE") or "unfinit_instagram.json").strip()

        self.STORE_NAME = _clean_text(os.environ.get("STORE_NAME") or "فروشگاه دوره‌های آموزشی UNFINIT", default="فروشگاه دوره‌های آموزشی UNFINIT")
        self.WELCOME_TEXT = _clean_text(os.environ.get("WELCOME_TEXT") or "به فروشگاه دوره‌های آموزشی و دانلودی UNFINIT خوش آمدید.", default="به فروشگاه دوره‌های آموزشی و دانلودی UNFINIT خوش آمدید.")
        self.TERMS_TEXT = (os.environ.get("TERMS_TEXT") or "کلیه حقوق مادی و معنوی دوره‌ها متعلق به این مجموعه می‌باشد.").strip()
        self.CARD_NUMBER = (os.environ.get("CARD_NUMBER") or "6037991122334455").strip()
        self.CARD_HOLDER = (os.environ.get("CARD_HOLDER") or "نام صاحب حساب").strip()
        self.CASHBACK_PERCENT = int((os.environ.get("CASHBACK_PERCENT") or "10").strip() or "10")
        self.COURSE_DESC_MAX_LEN = int((os.environ.get("COURSE_DESC_MAX_LEN") or "255").strip() or "255")

        self.DEFAULT_ARTIST = (os.environ.get("DEFAULT_ARTIST") or "AbbasManesh365 Bot").strip()
        self.DEFAULT_ALBUM = (os.environ.get("DEFAULT_ALBUM") or "دوره آموزشی").strip()
        self.MAX_SAFE_BALE_SIZE_MB = float((os.environ.get("MAX_SAFE_BALE_SIZE_MB") or "49.99").strip() or "49.99")
        self.MAX_SAFE_BALE_SIZE_BYTES = int(self.MAX_SAFE_BALE_SIZE_MB * 1024 * 1024)

        self.FORCE_JOIN_CHANNEL_TELEGRAM = (os.environ.get("FORCE_JOIN_CHANNEL_TELEGRAM") or "").strip()
        self.FORCE_JOIN_CHANNEL_BALE = (os.environ.get("FORCE_JOIN_CHANNEL_BALE") or "").strip()

        self.PORT = int((os.environ.get("PORT") or "7860").strip() or "7860")
        self.ADMIN_PANEL_PASSWORD = (os.environ.get("ADMIN_PANEL_PASSWORD") or "").strip()
        if not self.ADMIN_PANEL_PASSWORD:
            import logging
            logging.getLogger("config").warning("⚠️ [SECURITY] ADMIN_PANEL_PASSWORD is not set in environment or Hugging Face Secrets! Web admin access will be restricted.")

        self.TELEGRAM_FORUM_GROUP_ID = (os.environ.get("TELEGRAM_FORUM_GROUP_ID") or "").strip()
        self.ADMIN_USER_IDS = [x.strip() for x in (os.environ.get("ADMIN_USER_IDS") or "").split(",") if x.strip()]
        self.ZARINPAL_MERCHANT_ID = (os.environ.get("ZARINPAL_MERCHANT_ID") or "").strip()
        self.ZARINPAL_SANDBOX = (os.environ.get("ZARINPAL_SANDBOX", "false").lower() in ("true", "1", "yes"))

        self.NARA_BASE_URL = (os.environ.get("NARA_BASE_URL") or "https://router.bynara.id/v1").strip()
        self.NARA_API_KEY = (os.environ.get("NARA_API_KEY") or "").strip()
        _nm = (os.environ.get("NARA_MODEL") or "mimo-v2.5-free").strip()
        self.NARA_MODEL = "mimo-v2.5-free" if _nm == "mistral-large" else _nm

        self.GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
        self.GEMINI_MODEL = (os.environ.get("GEMINI_MODEL") or "gemini-3.6-flash").strip()
        self.COURSE_DELIVERY_NOTE = _clean_text(os.environ.get("COURSE_DELIVERY_NOTE") or "امیدوارم این دوره، براتون سرشار از آگاهی، رشد و نتایج ارزشمند باشه. ✨", default="امیدوارم این دوره، براتون سرشار از آگاهی، رشد و نتایج ارزشمند باشه. ✨")
        self.HF_TOKEN = (os.environ.get("HF_TOKEN") or "").strip()
        self.HF_SPACE_ID = (os.environ.get("HF_SPACE_ID") or "Foadian/UNFINIT").strip()
        self.ENGINE_VERSION = VersionStr((os.environ.get("ENGINE_VERSION") or "v0.1.0").strip())

    def is_admin(self, user_id: Any) -> bool:
        """Check if given user_id is the owner or listed in ADMIN_USER_IDS."""
        uid = str(user_id).strip()
        if not uid or uid == "0":
            return False
        if uid in (str(self.TELEGRAM_OWNER_ID), str(self.BALE_OWNER_ID)):
            return True
        return uid in self.ADMIN_USER_IDS

    def reload_storage_paths(self):
        persistent_candidate = Path(os.environ.get("PERSISTENT_DATA_DIR", "/data"))
        use_persistent = False
        try:
            if persistent_candidate.exists() and persistent_candidate.is_dir():
                test_f = persistent_candidate / ".perm_check"
                test_f.touch()
                test_f.unlink()
                use_persistent = True
        except Exception:
            use_persistent = False

        self._use_persistent = use_persistent
        if use_persistent:
            self.DATA_DIR = persistent_candidate.resolve()
            self.DB_PATH = self.DATA_DIR / "store_database.db"
            self.COURSES_JSON_FILE = self.DATA_DIR / "courses.json"
            self.SETTINGS_JSON_FILE = self.DATA_DIR / "settings.json"
            self.COURSES_BACKUP_FILE = self.COURSES_JSON_FILE
            self.UPLOADS_DIR = self.DATA_DIR / "uploads"
            self.BANNERS_DIR = self.DATA_DIR / "uploads" / "banners"
        else:
            self.DATA_DIR = (self.BASE_DIR / "data").resolve()
            self.DB_PATH = (self.BASE_DIR / "store_database.db").resolve()
            self.COURSES_JSON_FILE = self.DATA_DIR / "courses.json"
            self.SETTINGS_JSON_FILE = self.DATA_DIR / "settings.json"
            self.COURSES_BACKUP_FILE = self.COURSES_JSON_FILE
            self.UPLOADS_DIR = (self.BASE_DIR / "uploads").resolve()
            self.BANNERS_DIR = (self.BASE_DIR / "uploads" / "banners").resolve()

        self.DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite+aiosqlite:///{self.DB_PATH}").strip()
        try:
            self.DATA_DIR.mkdir(parents=True, exist_ok=True)
            self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            self.BANNERS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    TEMP_DIR: Path = (Path(os.environ.get("TEMP_DIR")) if os.environ.get("TEMP_DIR") else BASE_DIR / "temp_downloads").resolve()
    PORT: int = int((os.environ.get("PORT") or "7860").strip() or "7860")

    # 9. Admin Security
    ADMIN_PANEL_PASSWORD: str = (os.environ.get("ADMIN_PANEL_PASSWORD") or "").strip()

    # 10. Hermes AI Agent & Nara Router Settings
    NARA_BASE_URL: str = (os.environ.get("NARA_BASE_URL") or "https://router.bynara.id/v1").strip()
    _raw_nara_m: str = (os.environ.get("NARA_MODEL") or "mimo-v2.5-free").strip()
    NARA_MODEL: str = "mimo-v2.5-free" if _raw_nara_m == "mistral-large" else _raw_nara_m

    # 11. Google Gemini Audio Engine Settings
    GEMINI_API_KEY: str = (os.environ.get("GEMINI_API_KEY") or "").strip()
    GEMINI_MODEL: str = (os.environ.get("GEMINI_MODEL") or "gemini-3.6-flash").strip()

    # 12. Engine Version
    ENGINE_VERSION: str = (os.environ.get("ENGINE_VERSION") or "v25.7.4").strip()

config = Config()
config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
config.BANNERS_DIR.mkdir(parents=True, exist_ok=True)
config.DATA_DIR.mkdir(parents=True, exist_ok=True)

# First-time seed of courses.json and settings.json into persistent volume if missing
if getattr(config, "_use_persistent", False):
    import shutil
    local_courses = config.BASE_DIR / "data" / "courses.json"
    if not config.COURSES_JSON_FILE.exists() and local_courses.exists():
        try:
            shutil.copy2(local_courses, config.COURSES_JSON_FILE)
        except Exception:
            pass

    local_settings = config.BASE_DIR / "data" / "settings.json"
    if not config.SETTINGS_JSON_FILE.exists() and local_settings.exists():
        try:
            shutil.copy2(local_settings, config.SETTINGS_JSON_FILE)
        except Exception:
            pass
