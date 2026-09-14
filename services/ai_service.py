"""
Standard OpenAI/VyceAI AI Service for UNFINIT Store Engine
Directly connects to VyceAI (https://api.vyceai.com/v1) using standard OpenAI-compatible API.
Supports deepseek-v4.1, deepseek-v4-flash, claude-sonnet-4-6, agnes-3.0-flash.
"""

import asyncio
import json
import logging
import aiohttp
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from pathlib import Path
from core.config import config

logger = logging.getLogger("ai_service")

@asynccontextmanager
async def ai_typing_action(action_coro_fn, interval: float = 4.0):
    """
    Context manager that calls action_coro_fn() every `interval` seconds
    in a background task until the block finishes, providing continuous typing indicator.
    """
    stop_event = asyncio.Event()

    async def _loop():
        while not stop_event.is_set():
            try:
                await action_coro_fn()
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
            except Exception:
                break

    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


class AIService:
    """
    Standard AI Service connecting to VyceAI (OpenAI-compatible) endpoint.
    """
    ALLOWED_MODELS = [
        "deepseek-v4.1",
        "deepseek-v4-flash",
        "claude-sonnet-4-6",
        "agnes-3.0-flash"
    ]

    MODEL_DISPLAY_NAMES = {
        "deepseek-v4.1": "DeepSeek-v4.1",
        "deepseek-v4-flash": "DeepSeek-v4-Flash",
        "claude-sonnet-4-6": "Claude-Sonnet-4.6",
        "claude-sonnet-4.6": "Claude-Sonnet-4.6",
        "agnes-3.0-flash": "Agnes-3.0-Flash"
    }

    def format_model_badge(self, model: Optional[str] = None) -> str:
        m = (model or config.AI_MODEL or "deepseek-v4.1").strip().lower()
        display = self.MODEL_DISPLAY_NAMES.get(m)
        if not display:
            for k, v in self.MODEL_DISPLAY_NAMES.items():
                if k in m or m in k:
                    display = v
                    break
        if not display:
            display = m.capitalize()
        return f"\n\n🧠 {display}"

    async def chat(
        self,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Sends a chat completion request to the configured VyceAI / OpenAI-compatible endpoint.
        """
        api_key = (config.AI_API_KEY or "").strip()
        base_url = (config.AI_BASE_URL or "https://api.vyceai.com/v1").strip().rstrip("/")
        model_name = (model or config.AI_MODEL or "deepseek-v4.1").strip()

        if not api_key:
            return {
                "ok": False,
                "error": "AI_API_KEY is not set",
                "reply": "",
                "model": model_name
            }

        endpoint = f"{base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for h in history:
                if isinstance(h, dict) and "role" in h and "content" in h:
                    messages.append(h)
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature
        }

        try:
            timeout = aiohttp.ClientTimeout(total=45)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(endpoint, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        choices = data.get("choices") or []
                        if choices:
                            reply = choices[0].get("message", {}).get("content", "")
                            return {
                                "ok": True,
                                "reply": reply.strip(),
                                "model": model_name,
                                "raw": data
                            }
                        return {
                            "ok": False,
                            "error": "No response choices returned by model",
                            "reply": "",
                            "model": model_name
                        }
                    else:
                        err_text = await resp.text()
                        logger.warning(f"[ai_service] VyceAI HTTP {resp.status}: {err_text[:200]}")
                        return {
                            "ok": False,
                            "error": f"HTTP {resp.status}: {err_text[:150]}",
                            "reply": "",
                            "model": model_name
                        }
        except Exception as e:
            logger.warning(f"[ai_service] VyceAI request failed: {e}")
            return {
                "ok": False,
                "error": str(e),
                "reply": "",
                "model": model_name
            }

    async def chat_course_support(
        self,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        AI Sales & Support Copilot:
        Provides inspiring, motivational buying guidance and course consultations.
        Appends the active model badge to the response.
        """
        courses_data = []
        courses_json_path = config.DATA_DIR / "courses.json"
        if courses_json_path.exists():
            try:
                with open(courses_json_path, "r", encoding="utf-8") as f:
                    courses_data = json.load(f)
            except Exception as e:
                logger.warning(f"[ai_service] Failed to read courses.json: {e}")

        if not courses_data:
            courses_data = [
                {
                    "name": "دوره جامع کشف قوانین زندگی",
                    "price": 8800000,
                    "description": "دوره بی‌نظیر کشف قوانین بدون تغییر جهان هستی برای درک مدارها، فرکانس‌ها و ساخت اتفاقات دلخواه زندگی."
                },
                {
                    "name": "دوره روانشناسی ثروت ۱",
                    "price": 8900000,
                    "description": "شناسایی و تغییر ترمزها و باورهای مخرب مالی و دستیابی به استقلال و آزادی مالی پایدار."
                },
                {
                    "name": "دوره جامع عزت‌نفس و خودباوری",
                    "price": 3500000,
                    "description": "ساخت بنیادهای محکم شخصیتی، رهایی از گفتگوهای منفی ذهنی، احساس لیاقت و شجاعت فردی."
                }
            ]

        courses_summary = []
        for i, c in enumerate(courses_data, 1):
            name = c.get("name") or "دوره آموزشی"
            price = c.get("price", 0)
            desc = c.get("description") or ""
            p_str = f"{price:,} تومان" if price > 0 else "رایگان / هدیه"
            courses_summary.append(f"{i}. 🎓 {name} ({p_str})\n   📝 {desc}")

        catalog_text = "\n".join(courses_summary)

        sys_prompt = (
            f"شما «مشاور ارشد و راهنمای هوشمند فروش دوره‌های آموزشی آکادمی UNFINIT» هستید.\n"
            f"کاتالوگ دوره‌های فعال آکادمی:\n"
            f"{catalog_text}\n\n"
            f"دستورالعمل‌ها:\n"
            f"۱. با لحنی بسیار صمیمی، پرانرژی، الهام‌بخش، انگیزشی و صمیمانه با مخاطب صحبت کنید.\n"
            f"۲. متناسب با دغدغه، پرسش یا پیام مخاطب، بهترین دوره را با دلایل ملموس پیشنهاد دهید و ارزش تحول‌آفرین آن را توضیح دهید.\n"
            f"۳. کاربر را با خوش‌رویی به خرید دوره تشویق کنید و راهنمایی کنید که با ارسال /start یا لمس دکمه «📚 دوره‌های آموزشی» می‌تواند فوراً ثبت‌نام کرده و دسترسی آنی دریافت کند.\n"
            f"۴. از بکار بردن کلمات خشک اداری یا پاسخ‌های بیش از حد طولانی پرهیز کنید. از ایموجی‌های مناسب برای جذابیت استفاده کنید.\n"
            f"۵. به پیام‌های احوال‌پرسی یا عمومی با انرژی بسیار بالا و پیام مثبت پاسخ دهید و سپس خدمات آکادمی را با افتخار معرفی نمایید."
        )

        badge = self.format_model_badge(config.AI_MODEL)

        try:
            res = await self.chat(user_message=user_message, history=history, system_prompt=sys_prompt)
            if res.get("ok") and res.get("reply"):
                return f"{res['reply'].strip()}{badge}"
        except Exception as e:
            logger.warning(f"[ai_service] chat_course_support error: {e}")

        # Intelligent polite Persian greeting fallback
        fallback_text = (
            "سلام و درود دوست ارزشمند من! ✨\n\n"
            "بسیار خوشحالم که در مسیر یادگیری، آگاهی و رشد فردی با ما همراه هستید. 🌱\n\n"
            "دوره‌های فعال و تحول‌آفرین آکادمی ما عبارتند از:\n\n"
            f"{catalog_text}\n\n"
            "💎 جهت مشاهده جزئیات بیشتر، ثبت‌نام و دریافت فوری محتوا، کافیست دستور /start را ارسال فرمایید یا دکمه **«📚 لیست دوره‌های آموزشی»** را لمس نمایید.\n"
            "اگر در انتخاب مناسب‌ترین دوره نیاز به مشاوره دارید، با کمال میل راهنمای شما هستم! 🌟"
        )
        return f"{fallback_text}{badge}"


ai_service = AIService()
format_model_badge = ai_service.format_model_badge
