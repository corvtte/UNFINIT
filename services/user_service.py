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
        self.phone: str = normalize_phone(data.get("phone", ""))
        self.full_name: str = str(data.get("full_name", "") or "").strip()
        self.telegram_id: Optional[str] = str(data.get("telegram_id")).strip() if data.get("telegram_id") else None
        self.bale_id: Optional[str] = str(data.get("bale_id")).strip() if data.get("bale_id") else None
        self.purchased_courses: List[str] = list(data.get("purchased_courses") or [])
        self.unlocked_gifts: List[str] = list(data.get("unlocked_gifts") or [])
        self.referral_code: str = str(data.get("referral_code") or "").strip()
        self.invited_by: Optional[str] = str(data.get("invited_by")).strip() if data.get("invited_by") else None
        self.successful_invites: int = int(data.get("successful_invites", 0) or 0)
        self.terms_accepted: bool = bool(data.get("terms_accepted", False))
        self.created_at: str = str(data.get("created_at") or get_tehran_now_str())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phone": self.phone,
            "full_name": self.full_name,
            "telegram_id": self.telegram_id,
            "bale_id": self.bale_id,
            "purchased_courses": self.purchased_courses,
            "unlocked_gifts": self.unlocked_gifts,
            "referral_code": self.referral_code,
            "invited_by": self.invited_by,
            "successful_invites": self.successful_invites,
            "terms_accepted": self.terms_accepted,
            "created_at": self.created_at
        }

class UserService:
    _users_cache: Optional[Dict[str, UserModel]] = None

    @classmethod
    def clear_cache(cls) -> None:
        cls._users_cache = None

    @classmethod
    def _get_enc_file(cls) -> Path:
        return getattr(config, "USERS_ENC_FILE", config.DATA_DIR / "users.json.enc")

    @classmethod
    def load_users(cls, force_reload: bool = False) -> Dict[str, UserModel]:
        if cls._users_cache is not None and not force_reload:
            return cls._users_cache

        users: Dict[str, UserModel] = {}
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
                        if norm_p and norm_p not in users:
                            users[norm_p] = UserModel(udict)
                # Securely remove plain users.json to ensure Zero-Git exposure
                try:
                    legacy_file.unlink()
                    logger.info("[user_service] Migrated legacy users.json to encrypted storage and removed plain file.")
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"[user_service] Error reading legacy {legacy_file}: {e}")

        cls._users_cache = users
        return cls._users_cache

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
        return None

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
