import re
from typing import Optional, Tuple, Dict, Any, Union
from core.config import config
from core.logger import get_logger
from services.user_service import UserService, UserModel, normalize_phone

logger = get_logger("referral_service")

# Identifier for the viral free course gift
TOHID_AMALI_PACK_ID = "tohid_amali_pack"

# Official 11 episodes metadata for Tohid Amali Audio Series
TOHID_AMALI_EPISODES = [
    {"part": 1, "title": "توحید عملی - قسمت اول (مفهوم بنیادین توحید و شرک)", "duration": 1800, "filename": "Tohid_Amali_Part01.mp3"},
    {"part": 2, "title": "توحید عملی - قسمت دوم (تنها قدرت حاکم بر جهان هستی)", "duration": 1920, "filename": "Tohid_Amali_Part02.mp3"},
    {"part": 3, "title": "توحید عملی - قسمت سوم (بررسی ریشه‌ای عوامل ترس و وابستگی)", "duration": 2100, "filename": "Tohid_Amali_Part03.mp3"},
    {"part": 4, "title": "توحید عملی - قسمت چهارم (اعتماد به رزاقیت بی‌انتهای پروردگار)", "duration": 2040, "filename": "Tohid_Amali_Part04.mp3"},
    {"part": 5, "title": "توحید عملی - قسمت پنجم (شناخت نجواهای ذهنی شیطان و هدایت‌های الهی)", "duration": 1980, "filename": "Tohid_Amali_Part05.mp3"},
    {"part": 6, "title": "توحید عملی - قسمت ششم (تسلیم قلبی و آرامش در مسیر اهداف)", "duration": 2220, "filename": "Tohid_Amali_Part06.mp3"},
    {"part": 7, "title": "توحید عملی - قسمت هفتم (بررسی مصادیق شرک خفی در روابط روزمره)", "duration": 2010, "filename": "Tohid_Amali_Part07.mp3"},
    {"part": 8, "title": "توحید عملی - قسمت هشتم (رهایی از تاییدطلبی و قضاوت دیگران)", "duration": 1950, "filename": "Tohid_Amali_Part08.mp3"},
    {"part": 9, "title": "توحید عملی - قسمت نهم (احساس لیاقت و اتصال به منبع فراوانی)", "duration": 2160, "filename": "Tohid_Amali_Part09.mp3"},
    {"part": 10, "title": "توحید عملی - قسمت دهم (شکرگزاری واقعی و تمرکز بر نکات مثبت)", "duration": 2280, "filename": "Tohid_Amali_Part10.mp3"},
    {"part": 11, "title": "توحید عملی - قسمت یازدهم (تثبیت باورهای توحیدی در عمل)", "duration": 2400, "filename": "Tohid_Amali_Part11.mp3"}
]

class ReferralService:
    @staticmethod
    def get_referral_link(
        user_identifier_or_platform: Union[str, int],
        platform_or_identifier: Optional[Union[str, int]] = "telegram",
        bot_username: str = ""
    ) -> str:
        """
        Generates platform-specific viral invitation link based on numerical user ID.
        - Telegram: https://t.me/<bot_username>?start=ref_<user_id>
        - Bale: https://ble.ir/<bot_username>?start=ref_<user_id>
        """
        arg1_str = str(user_identifier_or_platform).strip()
        arg2_str = str(platform_or_identifier or "telegram").strip()

        if arg1_str.lower() in ("telegram", "bale", "rubika"):
            platform = arg1_str.lower()
            clean_id = arg2_str
        else:
            clean_id = arg1_str
            platform = arg2_str.lower()

        # Remove any leading 'ref_' from user ID to guarantee pure ref_{user_id} format
        if clean_id.startswith("ref_"):
            clean_id = clean_id[4:]

        clean_bot = str(bot_username).strip().lstrip("@")
        if not clean_bot:
            if platform == "telegram":
                clean_bot = getattr(config, "TELEGRAM_BOT_USERNAME", "") or "unfinit_store_bot"
            elif platform == "bale":
                clean_bot = getattr(config, "BALE_BOT_USERNAME", "") or "unfinit_bot"

        if platform == "telegram":
            return f"https://t.me/{clean_bot}?start=ref_{clean_id}"
        elif platform == "bale":
            return f"https://ble.ir/{clean_bot}?start=ref_{clean_id}"
        return f"ref_{clean_id}"

    @staticmethod
    def parse_referral_code(text: str) -> Optional[str]:
        """
        Parses referral code from deep link parameters, /start text, or direct code.
        Example: '/start ref_12345' -> '12345'
        'ref_abcdef' -> 'abcdef'
        """
        if not text:
            return None
        s = str(text).strip()
        
        # Match 'ref_<code/id>'
        m = re.search(r"ref_([a-zA-Z0-9_\-]+)", s)
        if m:
            return m.group(1).strip()

        # If sent as start=<code/id>
        m = re.search(r"start=([a-zA-Z0-9_\-]+)", s)
        if m:
            val = m.group(1).strip()
            if val.startswith("ref_"):
                return val[4:].strip()
            return val

        # Direct alphanumeric code (4-16 chars)
        if re.fullmatch(r"[a-zA-Z0-9_\-]{4,16}", s) and not s.startswith("/"):
            return s

        return None

    @classmethod
    def record_referral(
        cls,
        inviter_code_or_id: Optional[str] = None,
        new_user_phone: Optional[str] = None,
        platform: Optional[str] = None,
        platform_user_id: Optional[Union[str, int]] = None,
        inviter_code: Optional[str] = None,
        invited_phone: Optional[str] = None,
        invited_platform: Optional[str] = None,
        invited_platform_id: Optional[Union[str, int]] = None,
        **kwargs
    ) -> Tuple[Optional[str], bool]:
        """
        Processes a referral when a new user registers their phone:
        - Validates inviter.
        - Prevents self-referral.
        - Tracks successful invite.
        - Unlocks 'tohid_amali_pack' upon 1st successful invite.
        Returns: (inviter_phone: Optional[str], newly_unlocked: bool)
        """
        target_inviter_code = inviter_code or inviter_code_or_id or ""
        target_phone = invited_phone or new_user_phone or ""
        target_platform = (invited_platform or platform or "").lower().strip()
        target_p_uid = invited_platform_id if invited_platform_id is not None else platform_user_id

        if not target_inviter_code:
            return None, False

        norm_p = normalize_phone(target_phone)
        if not norm_p:
            return None, False

        inviter = UserService.get_user_by_referral_code(target_inviter_code)
        if not inviter:
            inviter = UserService.get_user_by_platform_id(target_platform, target_inviter_code)
        if not inviter:
            inviter = UserService.get_user_by_platform_id("telegram", target_inviter_code) or UserService.get_user_by_platform_id("bale", target_inviter_code)

        if not inviter:
            logger.info(f"[referral_service] Inviter not found for code: {target_inviter_code}")
            return None, False

        # Anti-fraud: prevent self-referral
        p_uid = str(target_p_uid).strip() if target_p_uid is not None else ""
        if inviter.phone == norm_p:
            return None, False
        if target_platform == "telegram" and inviter.telegram_id and inviter.telegram_id == p_uid:
            return None, False
        if target_platform == "bale" and inviter.bale_id and inviter.bale_id == p_uid:
            return None, False

        # Check existing new user record
        existing_user = UserService.get_user_by_phone(norm_p)
        if existing_user and existing_user.invited_by:
            return None, False

        # Record invitation
        if existing_user:
            existing_user.invited_by = inviter.referral_code or inviter.phone
        inviter.successful_invites += 1

        unlocked_now = False
        if inviter.successful_invites >= 1 and TOHID_AMALI_PACK_ID not in inviter.unlocked_gifts:
            inviter.unlocked_gifts.append(TOHID_AMALI_PACK_ID)
            unlocked_now = True
            logger.info(f"[referral_service] Unlocked {TOHID_AMALI_PACK_ID} for inviter {inviter.phone} (invites: {inviter.successful_invites})")

        UserService.save_users()
        return inviter.phone, unlocked_now

    @classmethod
    def get_congratulations_message(cls, platform: str = "telegram") -> str:
        """
        Message sent to the inviter when their referral goal is accomplished.
        """
        return (
            "🎉 <b>تبریک فراوان!</b>\n\n"
            "یکی از دوستان شما با لینک دعوت اختصاصی شما در ربات ثبت‌نام نمود.\n\n"
            "🎁 <b>قفل پکیج هدیه اختصاصی برای شما باز شد!</b>\n\n"
            "جهت دسترسی و دانلود، دکمه <b>«🎁 فایل‌های هدیه»</b> را در منوی اصلی انتخاب فرمایید."
        )

    @classmethod
    def get_congratulation_message(cls, inviter: Any = None) -> str:
        return cls.get_congratulations_message()

    @classmethod
    def get_invite_share_message(cls, user_id: str, platform: str, bot_username: str = "") -> str:
        """
        Message with unique referral link for the user to share with friends.
        """
        link = cls.get_referral_link(user_id, platform, bot_username)
        return (
            "🌟 <b>دعوت از دوستان و دریافت پکیج هدیه توحید عملی</b>\n\n"
            "با ارسال لینک زیر به دوستان خود، به محض ورود و ثبت‌نام ۱ نفر از طریق لینک شما، "
            "<b>قفل دوره ۱۱ قسمتی «توحید عملی» به ارزش ۱,۲۰۰,۰۰۰ تومان به صورت ۱۰۰٪ رایگان</b> برای شما باز خواهد شد!\n\n"
            f"🔗 <b>لینک اختصاصی دعوت شما:</b>\n<code>{link}</code>\n\n"
            "این پیام را برای دوستان و گروه‌های خود فوروارد کنید! 🚀"
        )
