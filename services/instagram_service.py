import json
import asyncio
from typing import Dict, Any, List, Optional
from core.logger import get_logger
from core.config import config

logger = get_logger("instagram_service")

# In-Memory & Persistent Keyword Rules for Instagram Direct & Comment Auto-Replies
KEYWORD_RULES = [
    {
        "keyword": "قانون",
        "reply_text": "سلام دوست عزیز! هدیه دوره جامع کشف قوانین زندگی برای شما ارسال شد 🎁",
        "voice_path": "gift_laws.mp3",
        "link": "https://t.me/your_channel"
    },
    {
        "keyword": "ثروت",
        "reply_text": "سلام! اطلاعات دوره روانشناسی ثروت ۱ با تخفیف ویژه خدمت شما 🎓",
        "voice_path": "wealth_intro.mp3",
        "link": "https://t.me/your_channel"
    },
    {
        "keyword": "1",
        "reply_text": "درود بر شما! فایل صوتی جلسه اول رایگان تقدیم نگاه پرمهرتان:",
        "voice_path": "session1.mp3",
        "link": ""
    }
]

class InstagramService:
    @staticmethod
    def match_keyword(text: str) -> Optional[Dict[str, Any]]:
        clean_text = (text or "").strip().lower()
        for rule in KEYWORD_RULES:
            if rule["keyword"].lower() in clean_text:
                return rule
        return None

    @staticmethod
    def get_all_rules() -> List[Dict[str, Any]]:
        return KEYWORD_RULES

    @staticmethod
    def add_rule(keyword: str, reply_text: str, voice_path: str = "", link: str = "") -> None:
        KEYWORD_RULES.append({
            "keyword": keyword.strip(),
            "reply_text": reply_text.strip(),
            "voice_path": voice_path.strip(),
            "link": link.strip()
        })
        logger.info(f"New Instagram keyword rule added: '{keyword}'")
