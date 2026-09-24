import os
import json
import csv
import io
import re
import secrets
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timezone, timedelta

from core.config import config
from core.logger import get_logger
from core.security import encrypt_data, decrypt_data

logger = get_logger("user_service")
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def get_tehran_now_str() -> str:
    return datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

def normalize_phone(phone: Any) -> Optional[str]:
    """
    Normalizes Iranian and international mobile phone numbers:
    - Strips spaces, hyphens, parentheses, etc.
    - Converts +98, 0098, 98 to leading 0.
    - Result: 09xxxxxxxxx for Iran, or None if invalid.
    """
    if not phone:
        return None
    s = str(phone).strip()
    
    # Persian & Arabic digit maps
    persian_arabic_digits = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    for k, v in persian_arabic_digits.items():
        s = s.replace(k, v)

    # Strip any non-digit character
    digits = re.sub(r"\D", "", s)

    if not digits:
        return None

    if digits.startswith("0098"):
        digits = "0" + digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    elif digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits

    if not (digits.startswith("09") and len(digits) == 11):
        return None

    return digits

class UserModel:
    def __init__(self, data: Dict[str, Any]):
        self.phone: Optional[str] = normalize_phone(data.get("phone", ""))
        self.username: str = str(data.get("username") or "").strip()
        self.full_name: str = str(data.get("full_name") or data.get("name") or self.username or "").strip()
        self.user_id: Optional[str] = str(data.get("user_id")).strip() if data.get("user_id") else None
        self.platform: str = str(data.get("platform") or "").strip().lower()
        self.telegram_id: Optional[str] = str(data.get("telegram_id")).strip() if data.get("telegram_id") else (self.user_id if "tele" in self.platform else None)
        self.bale_id: Optional[str] = str(data.get("bale_id")).strip() if data.get("bale_id") else (self.user_id if "bale" in self.platform else None)
        self.purchased_courses: List[str] = list(data.get("purchased_courses") or [])
        self.unlocked_gifts: List[str] = list(data.get("unlocked_gifts") or [])
        self.referral_code: str = str(data.get("referral_code") or "").strip()
        self.invited_by: Optional[str] = str(data.get("invited_by") or data.get("referred_by") or "").strip() if (data.get("invited_by") or data.get("referred_by")) else None
        self.successful_invites: int = int(data.get("successful_invites", 0) or 0)
        self.terms_accepted: bool = bool(data.get("terms_accepted", False) or data.get("commitment_signed", False))
        self.wallet_balance: int = int(data.get("wallet_balance", 0) or 0)
        self.vip_until: str = str(data.get("vip_until") or "").strip()
        self.created_at: str = str(data.get("created_at") or get_tehran_now_str())

    def is_vip(self) -> bool:
        """
        بررسی فعال بودن اشتراک ویژه (VIP) کاربر.
        """
        v_str = getattr(self, "vip_until", "")
        if not v_str:
            return False
        try:
            if str(v_str).strip().isdigit():
                return float(v_str) > datetime.now(timezone.utc).timestamp()
            v_clean = str(v_str).strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(v_clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TEHRAN_TZ)
            return dt > datetime.now(TEHRAN_TZ)
        except Exception:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def to_dict(self) -> Dict[str, Any]:
        u_id = self.user_id or self.telegram_id or self.bale_id or self.phone or ""
        plat = self.platform or ("telegram" if self.telegram_id else ("bale" if self.bale_id else "web"))
        uname = self.username or self.full_name or (f"کاربر {u_id}" if u_id else "کاربر")
        fname = self.full_name or self.username or uname
        return {
            "user_id": u_id,
            "platform": plat,
            "username": uname,
            "full_name": fname,
            "name": fname,
            "phone": self.phone,
            "telegram_id": self.telegram_id,
            "bale_id": self.bale_id,
            "purchased_courses": self.purchased_courses,
            "unlocked_gifts": self.unlocked_gifts,
            "referral_code": self.referral_code,
            "invited_by": self.invited_by,
            "referred_by": self.invited_by,
            "successful_invites": self.successful_invites,
            "terms_accepted": self.terms_accepted,
            "commitment_signed": self.terms_accepted,
            "wallet_balance": getattr(self, "wallet_balance", 0),
            "vip_until": getattr(self, "vip_until", ""),
            "vip_until_jalali": self.get_vip_until_jalali(),
            "is_vip": self.is_vip(),
            "created_at": self.created_at
        }

    def get_vip_until_jalali(self) -> str:
        """تبدیل تاریخ انقضای اشتراک کاربر به رشته کامل و زیبای شمسی همراه با روز و ساعت."""
        v_str = getattr(self, "vip_until", "")
        if not v_str:
            return ""
        try:
            from core.jalali import format_jalali_full
            return format_jalali_full(v_str)
        except Exception:
            return str(v_str)[:10]

class UserService:
    _users: Dict[str, UserModel] = {}
    _users_cache: Optional[Dict[str, UserModel]] = None

    @classmethod
    def clear_cache(cls) -> None:
        cls._users_cache = None
        cls._users = {}

    @classmethod
    def _get_enc_file(cls) -> Path:
        return getattr(config, "USERS_ENC_FILE", config.DATA_DIR / "users.json.enc")

    @classmethod
    def load_users(cls, force_reload: bool = False) -> Dict[str, UserModel]:
        if cls._users_cache is not None and not force_reload:
            cls._users = cls._users_cache
            return cls._users_cache

        users: Dict[str, UserModel] = dict(cls._users)
        enc_file = cls._get_enc_file()

        # 1. Check if encrypted users file exists
        if enc_file.exists():
            try:
                raw_enc = enc_file.read_bytes()
                if raw_enc:
                    decrypted_text = decrypt_data(raw_enc)
                    data = json.loads(decrypted_text)
                    if isinstance(data, dict):
                        for phone, udict in data.items():
                            norm_p = normalize_phone(phone)
                            if norm_p:
                                users[norm_p] = UserModel(udict)
                            else:
                                users[str(phone)] = UserModel(udict)
            except Exception as e:
                logger.error(f"[user_service] Error decrypting {enc_file}: {e}")

        # 2. Check if legacy unencrypted users.json exists
        legacy_file = config.DATA_DIR / "users.json"
        if legacy_file.exists():
            try:
                with open(legacy_file, "r", encoding="utf-8") as f:
                    legacy_data = json.load(f)
                if isinstance(legacy_data, dict):
                    for phone, udict in legacy_data.items():
                        norm_p = normalize_phone(phone)
                        k = norm_p if norm_p else str(phone)
                        if k not in users:
                            users[k] = UserModel(udict)
                # Securely remove plain users.json to ensure Zero-Git exposure
                try:
                    legacy_file.unlink()
                    logger.info("[user_service] Migrated legacy users.json to encrypted storage and removed plain file.")
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"[user_service] Error reading legacy {legacy_file}: {e}")

        cls._users = users
        cls._users_cache = users
        return cls._users_cache

    @classmethod
    def delete_user(cls, identifier: str) -> bool:
        users = cls.load_users()
        found = False
        target_keys = []
        clean_id = str(identifier).strip()
        for key, u in list(users.items()):
            u_ident = getattr(u, 'user_id', None)
            if clean_id in (key, u.phone, u.telegram_id, u.bale_id, u_ident):
                target_keys.append(key)
                found = True
        for k in target_keys:
            users.pop(k, None)
            if hasattr(cls, '_users') and isinstance(cls._users, dict):
                cls._users.pop(k, None)
        if found:
            cls.save_users()
        return found

    @classmethod
    def purge_test_users(cls) -> int:
        users = cls.load_users()
        to_del = []
        for k, u in list(users.items()):
            fn = (u.full_name or "").lower()
            un = (getattr(u, 'username', '') or "").lower()
            ph = (u.phone or "")
            uid = str(u.telegram_id or u.bale_id or getattr(u, 'user_id', '') or "").lower()
            if any(t in fn for t in ["test", "تست", "demo", "کاربر تستی"]) or any(t in un for t in ["test", "تست", "demo", "fake"]) or ph.startswith("0900") or ph.startswith("09999") or "test" in uid or "fake" in uid or "demo" in uid or "fake" in k.lower():
                to_del.append(k)
        for k in to_del:
            users.pop(k, None)
            if hasattr(cls, '_users') and isinstance(cls._users, dict):
                cls._users.pop(k, None)
        if to_del:
            cls.save_users()
        return len(to_del)

    @classmethod
    def save_users(cls) -> None:
        if cls._users_cache is None:
            return
        enc_file = cls._get_enc_file()
        try:
            enc_file.parent.mkdir(parents=True, exist_ok=True)
            data_dict = {p: u.to_dict() for p, u in cls._users_cache.items()}
            raw_json = json.dumps(data_dict, ensure_ascii=False, indent=2)
            enc_bytes = encrypt_data(raw_json)
            enc_file.write_bytes(enc_bytes)
        except Exception as e:
            logger.error(f"[user_service] Failed to save encrypted users: {e}")

    @classmethod
    def generate_referral_code(cls, prefix: str = "ref_") -> str:
        return secrets.token_hex(4)

    @classmethod
    def get_user_by_phone(cls, phone: str) -> Optional[UserModel]:
        norm_p = normalize_phone(phone)
        if not norm_p:
            return None
        users = cls.load_users()
        return users.get(norm_p)

    @classmethod
    def get_user_by_platform_id(cls, platform: str, platform_user_id: Union[str, int]) -> Optional[UserModel]:
        pid = str(platform_user_id).strip()
        if not pid or pid == "0":
            return None
        platform = platform.lower().strip()
        users = cls.load_users()
        for u in users.values():
            if platform == "telegram" and u.telegram_id == pid:
                return u
            elif platform == "bale" and u.bale_id == pid:
                return u
        return None

    @classmethod
    def get_user_by_referral_code(cls, code: str) -> Optional[UserModel]:
        c = str(code).strip()
        if not c:
            return None
        # Support both 'ref_abc' and 'abc'
        if c.startswith("ref_"):
            clean_c = c[4:]
        else:
            clean_c = c
        users = cls.load_users()
        for u in users.values():
            if u.referral_code == clean_c or u.referral_code == c:
                return u
            # Also allow referral by telegram_id or bale_id
            if u.telegram_id and u.telegram_id == clean_c:
                return u
            if u.bale_id and u.bale_id == clean_c:
                return u
    @classmethod
    def get_user_by_any_id(cls, identifier: Union[str, int]) -> Optional[UserModel]:
        """
        یافتن کاربر بر اساس هر یک از شناسه‌ها (شماره تلفن، شناسه تلگرام، شناسه بله، یا شناسه عمومی).
        """
        ident = str(identifier).strip()
        if not ident:
            return None
        users = cls.load_users()
        norm_p = normalize_phone(ident)
        if norm_p and norm_p in users:
            return users[norm_p]
        for u in users.values():
            if ident in (u.phone, u.telegram_id, u.bale_id, u.user_id):
                return u
        return None

    @classmethod
    def set_user_vip(cls, identifier: Union[str, int], days: int = 30) -> bool:
        """
        فعال‌سازی یا تمدید اشتراک ویژه پریمیوم (VIP) برای کاربر به مدت روزهای مشخص‌شده.

        ورودی‌ها:
            identifier: شناسه کاربری، تلفن، تلگرام یا بله
            days: مدت اعتبار به روز (پیش‌فرض ۳۰ روز)
        خروجی:
            bool: موفقیت‌آمیز بودن ثبت اشتراک
        """
        user = cls.get_user_by_any_id(identifier)
        if not user:
            return False
        now_ts = datetime.now(timezone.utc).timestamp()
        current_vip_until = 0.0
        if getattr(user, "vip_until", None):
            try:
                v_str = str(user.vip_until).strip()
                if v_str.isdigit():
                    current_vip_until = float(v_str)
                else:
                    current_vip_until = datetime.fromisoformat(v_str.replace("Z", "+00:00")).timestamp()
            except Exception:
                current_vip_until = 0.0
        start_ts = max(now_ts, current_vip_until)
        new_vip_ts = start_ts + (days * 86400)
        user.vip_until = str(int(new_vip_ts))
        cls.save_users()
        return True

    @classmethod
    def is_user_vip(cls, identifier: Union[str, int]) -> bool:
        """
        بررسی آنی اینکه آیا کاربر مورد نظر دارای اشتراک فعال پریمیوم (VIP) است یا خیر.
        """
        user = cls.get_user_by_any_id(identifier)
        return user.is_vip() if user else False

    @classmethod
    def link_platform_user(
        cls,
        arg1: Any = None,
        arg2: Any = None,
        arg3: Any = None,
        full_name: str = "",
        invited_by: Optional[str] = None,
        platform: Optional[str] = None,
        platform_id: Optional[Union[str, int]] = None,
        platform_user_id: Optional[Union[str, int]] = None,
        phone: Optional[str] = None,
        **kwargs
    ) -> UserModel:
        """
        Creates or links an account based on phone number:
        - If the user already exists (e.g. registered in Bale), attaches their Telegram ID (or vice versa).
        - Preserves all purchased courses and unlocked gifts across both platforms.
        """
        target_platform = platform or ""
        target_p_uid = platform_id if platform_id is not None else platform_user_id
        target_phone = phone or ""

        pos_args = [a for a in (arg1, arg2, arg3) if a is not None]

        for a in pos_args:
            str_a = str(a).strip()
            if str_a.lower() in ("telegram", "bale", "rubika"):
                target_platform = str_a.lower()
            elif normalize_phone(str_a) is not None:
                target_phone = str_a
            elif target_p_uid is None:
                target_p_uid = a

        if not target_phone and pos_args:
            for a in pos_args:
                if a != target_platform and a != target_p_uid:
                    target_phone = str(a)
                    break

        norm_p = normalize_phone(target_phone)
        if not norm_p:
            raise ValueError("شماره موبایل وارد شده معتبر نمی‌باشد.")

        users = cls.load_users()
        target_platform = (target_platform or "").lower().strip()
        p_uid = str(target_p_uid).strip() if target_p_uid is not None else ""

        user = users.get(norm_p)
        if user:
            # Update platform ID
            if target_platform == "telegram" and p_uid:
                user.telegram_id = p_uid
            elif target_platform == "bale" and p_uid:
                user.bale_id = p_uid
            if full_name and not user.full_name:
                user.full_name = full_name.strip()
            if not user.referral_code:
                user.referral_code = cls.generate_referral_code()
            if invited_by and not user.invited_by:
                user.invited_by = str(invited_by).strip()
        else:
            # Create new user
            u_dict = {
                "phone": norm_p,
                "full_name": full_name.strip(),
                "telegram_id": p_uid if target_platform == "telegram" else None,
                "bale_id": p_uid if target_platform == "bale" else None,
                "purchased_courses": [],
                "unlocked_gifts": [],
                "referral_code": cls.generate_referral_code(),
                "invited_by": str(invited_by).strip() if invited_by else None,
                "successful_invites": 0,
                "terms_accepted": False,
                "created_at": get_tehran_now_str()
            }
            user = UserModel(u_dict)
            users[norm_p] = user

        cls.save_users()
        return user

    @classmethod
    def accept_terms(cls, phone_or_uid: Union[str, int], platform: Optional[str] = None) -> Optional[UserModel]:
        p_str = str(phone_or_uid).strip()
        user = None
        if platform:
            user = cls.get_user_by_platform_id(platform, p_str)
        if not user:
            user = cls.get_user_by_phone(p_str)
        if user:
            user.terms_accepted = True
            cls.save_users()
            logger.info(f"[user_service] Terms accepted for user {user.phone}")
        return user

    @classmethod
    def accept_terms_by_platform(cls, platform: str, platform_id: Union[str, int]) -> Optional[UserModel]:
        return cls.accept_terms(platform_id, platform=platform)

    @classmethod
    def unlock_gift_by_platform(cls, platform: str, platform_id: Union[str, int], gift_id: str) -> bool:
        return cls.unlock_gift(str(platform_id), gift_id, platform=platform)

    @classmethod
    def is_gift_unlocked_by_platform(cls, platform: str, platform_id: Union[str, int], gift_id: str) -> bool:
        user = cls.get_user_by_platform_id(platform, str(platform_id))
        if not user:
            return False
        return str(gift_id).strip() in user.unlocked_gifts

    @classmethod
    def unlock_course(cls, phone_or_uid: str, course_id: str, platform: Optional[str] = None) -> bool:
        cid = str(course_id).strip()
        if not cid:
            return False
        user = None
        if platform:
            user = cls.get_user_by_platform_id(platform, phone_or_uid)
        if not user:
            user = cls.get_user_by_phone(phone_or_uid)
        if not user:
            return False

        if cid not in user.purchased_courses:
            user.purchased_courses.append(cid)
            cls.save_users()
            logger.info(f"[user_service] Unlocked course {cid} for user {user.phone}")
        return True

    @classmethod
    def unlock_gift(cls, phone_or_uid: str, gift_id: str, platform: Optional[str] = None) -> bool:
        gid = str(gift_id).strip()
        if not gid:
            return False
        user = None
        if platform:
            user = cls.get_user_by_platform_id(platform, phone_or_uid)
        if not user:
            user = cls.get_user_by_phone(phone_or_uid)
        if not user:
            return False

        if gid not in user.unlocked_gifts:
            user.unlocked_gifts.append(gid)
            cls.save_users()
            logger.info(f"[user_service] Unlocked gift {gid} for user {user.phone}")
        return True

    @classmethod
    def has_course_access(cls, user_or_phone: Union[str, UserModel], course_id: str) -> bool:
        cid = str(course_id).strip()
        if isinstance(user_or_phone, UserModel):
            return cid in user_or_phone.purchased_courses
        u = cls.get_user_by_phone(str(user_or_phone))
        return bool(u and cid in u.purchased_courses)

    @classmethod
    def has_gift_access(cls, user_or_phone: Union[str, UserModel], gift_id: str) -> bool:
        gid = str(gift_id).strip()
        if isinstance(user_or_phone, UserModel):
            return gid in user_or_phone.unlocked_gifts
        u = cls.get_user_by_phone(str(user_or_phone))
        return bool(u and gid in u.unlocked_gifts)

    @classmethod
    def get_user_by_any_id(cls, identifier: str) -> Optional[UserModel]:
        """
        یافتن کاربر بر اساس هرگونه شناسه یکتا (شماره موبایل، شناسه تلگرام، شناسه بله یا user_id).
        
        ورودی:
            identifier: رشته شناسه جستجو
        خروجی:
            شیء UserModel در صورت یافتن، یا None در صورت عدم وجود
        """
        clean_id = str(identifier).strip()
        if not clean_id:
            return None
        users = cls.load_users()
        norm_p = normalize_phone(clean_id)
        if norm_p and norm_p in users:
            return users[norm_p]
        for u in users.values():
            if clean_id in (u.phone, u.telegram_id, u.bale_id, getattr(u, 'user_id', None)):
                return u
        return None

    @classmethod
    def grant_vip(cls, identifier: str, days: int = 30) -> Optional[UserModel]:
        """
        اعطا یا تمدید اشتراک ویژه (VIP) کاربر به تعداد روزهای مشخص.
        اگر کاربر از قبل دارای اشتراک معتبر باشد، روزهای جدید به پایان اشتراک قبلی اضافه می‌شود.
        
        ورودی:
            identifier: شناسه یکتای کاربر (موبایل یا آیدی پلتفرم)
            days: تعداد روزهای اضافه شونده به اشتراک (پیش‌فرض ۳۰ روز)
        خروجی:
            شیء UserModel به‌روزرسانی شده یا None در صورت نیافتن کاربر
        """
        user = cls.get_user_by_any_id(identifier)
        if not user:
            # اگر هنوز کاربری ثبت نشده باشد بر مبنای شناسه کاربری جدید ثبت می‌گردد
            clean_id = str(identifier).strip()
            plat = "bale" if clean_id.isdigit() else "telegram"
            norm_p = normalize_phone(clean_id)
            user_data = {
                "user_id": clean_id,
                "platform": plat,
                "bale_id": clean_id if plat == "bale" else None,
                "telegram_id": clean_id if plat == "telegram" else None,
                "phone": norm_p,
                "full_name": f"کاربر {clean_id}",
                "referral_code": cls.generate_referral_code()
            }
            user = UserModel(user_data)
            key = norm_p if norm_p else clean_id
            users = cls.load_users()
            users[key] = user
            cls._users[key] = user
            if cls._users_cache is not None:
                cls._users_cache[key] = user
        
        now = datetime.now(TEHRAN_TZ)
        base_date = now
        if user.vip_until:
            try:
                v_clean = str(user.vip_until).strip().replace("Z", "+00:00")
                current_until = datetime.fromisoformat(v_clean)
                if current_until.tzinfo is None:
                    current_until = current_until.replace(tzinfo=TEHRAN_TZ)
                if current_until > now:
                    base_date = current_until
            except Exception:
                base_date = now
        
        new_until = base_date + timedelta(days=int(days))
        user.vip_until = new_until.strftime("%Y-%m-%d %H:%M:%S")
        cls.save_users()
        logger.info(f"[user_service] VIP granted to {identifier} until {user.vip_until} (+{days} days)")
        return user

    @classmethod
    def revoke_vip(cls, identifier: str) -> Optional[UserModel]:
        """
        لغو فوری اشتراک ویژه (VIP) کاربر.
        
        ورودی:
            identifier: شناسه یکتای کاربر
        خروجی:
            شیء UserModel به‌روزرسانی شده یا None
        """
        user = cls.get_user_by_any_id(identifier)
        if not user:
            return None
        user.vip_until = ""
        cls.save_users()
        logger.info(f"[user_service] VIP revoked for {identifier}")
        return user

    @classmethod
    def set_terms_accepted(cls, phone_or_uid: str, accepted: bool = True, platform: Optional[str] = None) -> bool:
        user = None
        if platform:
            user = cls.get_user_by_platform_id(platform, phone_or_uid)
        if not user:
            user = cls.get_user_by_phone(phone_or_uid)
        if not user:
            return False
        user.terms_accepted = accepted
        cls.save_users()
        return True

    @classmethod
    def export_contacts_csv(cls) -> str:
        """
        Exports all decrypted user contacts as a UTF-8 CSV with BOM for Excel compatibility.
        Only executed in memory on admin demand.
        """
        users = cls.load_users(force_reload=True)
        output = io.StringIO()
        output.write("\ufeff")  # UTF-8 BOM
        writer = csv.writer(output)
        writer.writerow([
            "شماره موبایل",
            "نام و نام خانوادگی",
            "شناسه تلگرام",
            "شناسه بله",
            "دوره‌های خریداری شده",
            "تعداد دوره‌ها",
            "هدایای فعال",
            "کد دعوت",
            "دعوت شده توسط",
            "تعداد دعوت موفق",
            "پذیرش قوانین",
            "تاریخ عضویت"
        ])
        for u in users.values():
            writer.writerow([
                u.phone,
                u.full_name or "---",
                u.telegram_id or "---",
                u.bale_id or "---",
                ", ".join(u.purchased_courses) if u.purchased_courses else "---",
                len(u.purchased_courses),
                ", ".join(u.unlocked_gifts) if u.unlocked_gifts else "---",
                u.referral_code or "---",
                u.invited_by or "---",
                u.successful_invites,
                "بله" if u.terms_accepted else "خیر",
                u.created_at
            ])
        return output.getvalue()
