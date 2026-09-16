"""
Multi-Provider AI Service for UNFINIT Store Engine
Supports VyceAI, Nara Router, Google Gemini, and Custom OpenAI-compatible endpoints.
Maintains distinct API keys per provider and strictly prevents fake model badges on fallback.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from pathlib import Path
import aiohttp

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
    Multi-Provider AI Service supporting VyceAI, Nara Router, Google Gemini, and Custom endpoints.
    """
    MODEL_DISPLAY_NAMES = {
        "deepseek-v4.1": "DeepSeek-v4.1",
        "deepseek-v4-flash": "DeepSeek-v4-Flash",
        "claude-sonnet-4-6": "Claude-Sonnet-4.6",
        "claude-sonnet-4.6": "Claude-Sonnet-4.6",
        "agnes-3.0-flash": "Agnes-3.0-Flash",
        "stepfun-3.7-flash": "StepFun-3.7",
        "mimo-v2.5-free": "Mimo-v2.5",
        "qwen2.5-72b": "Qwen-2.5-72B",
        "gemini-3.6-flash": "Gemini-3.6-Flash",
        "gemini-3.8-flash": "Gemini-3.8-Flash",
        "gemini-3.1-pro": "Gemini-3.1-Pro"
    }

    def format_model_badge(self, model: Optional[str] = None) -> str:
        active_model = (model or config.AI_MODEL or "deepseek-v4.1").strip().lower()
        display = self.MODEL_DISPLAY_NAMES.get(active_model)
        if not display:
            for k, v in self.MODEL_DISPLAY_NAMES.items():
                if k in active_model or active_model in k:
                    display = v
                    break
        if not display:
            display = active_model.capitalize()
        return f"\n\n🧠 {display}"

    def get_provider_config(self, override_provider: Optional[str] = None) -> Dict[str, str]:
        """Returns the active provider, base_url, api_key, and default model."""
        provider = (override_provider or getattr(config, "AI_PROVIDER", "vyceai") or "vyceai").strip().lower()
        if provider == "nara":
            base_url = (getattr(config, "NARA_BASE_URL", "") or "https://router.bynara.id/v1").strip().rstrip("/")
            api_key = (getattr(config, "NARA_API_KEY", "") or "").strip()
            model = (getattr(config, "NARA_MODEL", "") or getattr(config, "AI_MODEL", "") or "stepfun-3.7-flash").strip()
        elif provider == "gemini":
            base_url = "https://generativelanguage.googleapis.com/v1beta"
            api_key = (getattr(config, "GEMINI_API_KEY", "") or "").strip()
            model = (getattr(config, "GEMINI_MODEL", "") or getattr(config, "AI_MODEL", "") or "gemini-3.8-flash").strip()
        elif provider == "custom":
            base_url = (getattr(config, "AI_BASE_URL", "") or "").strip().rstrip("/")
            api_key = (getattr(config, "AI_API_KEY", "") or "").strip()
            model = (getattr(config, "AI_MODEL", "") or "default").strip()
        else:
            # vyceai default
            provider = "vyceai"
            base_url = (getattr(config, "AI_BASE_URL", "") or "https://api.vyceai.com/v1").strip().rstrip("/")
            api_key = (getattr(config, "VYCEAI_API_KEY", "") or getattr(config, "AI_API_KEY", "") or "").strip()
            model = (getattr(config, "AI_MODEL", "") or "deepseek-v4.1").strip()

        return {
            "provider": provider,
            "base_url": base_url,
            "api_key": api_key,
            "model": model
        }

    async def chat(
        self,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends a chat completion request to the active provider (VyceAI, Nara, Gemini, Custom).
        """
        cfg = self.get_provider_config(override_provider=provider)
        active_provider = cfg["provider"]
        api_key = cfg["api_key"]
        base_url = cfg["base_url"]
        model_name = (model or cfg["model"]).strip()

        if not api_key:
            return {
                "ok": False,
                "error": f"کلید API سرویس {active_provider} در تنظیمات پنل وارد نشده است.",
                "reply": "",
                "model": model_name
            }

        # Handle Gemini directly
        if active_provider == "gemini":
            try:
                from services.ai_agent_service import ai_agent_service
                return await ai_agent_service.chat_gemini(
                    user_message=user_message,
                    history=history,
                    model=model_name,
                    system_prompt=system_prompt
                )
            except Exception as e:
                logger.warning(f"[ai_service] Gemini chat error: {e}")
                return {
                    "ok": False,
                    "error": str(e),
                    "reply": "",
                    "model": model_name
                }

        # Handle OpenAI-compatible endpoints (VyceAI, Nara, Custom)
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
                        logger.warning(f"[ai_service] {active_provider} HTTP {resp.status}: {err_text[:200]}")
                        return {
                            "ok": False,
                            "error": f"HTTP {resp.status}: {err_text[:150]}",
                            "reply": "",
                            "model": model_name
                        }
        except Exception as e:
            logger.warning(f"[ai_service] {active_provider} request failed: {e}")
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
        Appends the active model badge ONLY when the response is successfully generated.
        NEVER appends fake model badges in fallback / missing key scenarios.
        """
        cfg = self.get_provider_config()
        if not cfg["api_key"]:
            return (
                "⚠️ **کلید دسترسی هوش مصنوعی تنظیم نشده است.**\n"
                f"سرویس فعال فعلی «{cfg['provider'].upper()}» می‌باشد اما کلید API آن در تنظیمات سکرت‌ها ثبت نگردیده است.\n"
                "لطفاً جهت فعال‌سازی پاسخگویی هوشمند، کلید دسترسی مربوطه را در تب سکرت‌ها و توکن‌ها وارد فرمایید."
            )

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

        badge = self.format_model_badge(cfg["model"])

        try:
            res = await self.chat(
                user_message=user_message,
                history=history,
                system_prompt=sys_prompt,
                model=cfg["model"],
                provider=cfg["provider"]
            )
            if res.get("ok") and res.get("reply"):
                # Successfully generated response: attach authentic model badge
                return f"{res['reply'].strip()}{badge}"
            else:
                err_msg = res.get("error") or "خطای نامشخص"
                logger.warning(f"[ai_service] chat_course_support returned error: {err_msg}")
                # Clear error notice WITHOUT fake badge
                return f"⚠️ در پردازش پیام توسط هوش مصنوعی ({cfg['provider'].upper()}) خطایی رخ داد: {err_msg}"
        except Exception as e:
            logger.warning(f"[ai_service] chat_course_support exception: {e}")
            # Clear exception notice WITHOUT fake badge
            return f"⚠️ ارتباط با سرویس هوش مصنوعی برقرار نشد: {str(e)}"

    async def summarize_course_for_bale(self, text: str) -> str:
        """
        Summarizes long course descriptions into concise, compelling Persian text
        strictly under 255 characters suitable for Bale messenger captions and cards.
        """
        clean_text = (text or "").strip()
        if not clean_text:
            return ""
        if len(clean_text) <= 250:
            return clean_text

        cfg = self.get_provider_config()
        sys_prompt = (
            "تو یک دستیار حرفه‌ای نگارش و بازاریابی محتوا هستی.\n"
            "وظیفه تو خلاصه کردن متن توضیحات یک دوره آموزشی به زبانی جذاب، روان و ترغیب‌کننده است.\n"
            "قانون فوق‌العاده مهم و غیرقابل نقض: طول کل پاسخ باید حتماً و اکیداً حداکثر ۲۵۰ کاراکتر باشد.\n"
            "فقط متن نهایی خلاصه را بدون هیچ مقدمه، توضیح اضافی، گیومه، پرانتز یا علامت اضافی بنویس."
        )
        user_msg = f"متن توضیحات دوره:\n{clean_text}\n\nلطفاً در حداکثر ۲۵۰ کاراکتر فارسی جذاب خلاصه کن:"

        try:
            res = await self.chat(
                user_message=user_msg,
                system_prompt=sys_prompt,
                model=cfg["model"],
                provider=cfg["provider"]
            )
            if res.get("ok") and res.get("reply"):
                summary = res["reply"].strip().strip('"').strip("'").strip("«»")
                if len(summary) > 255:
                    summary = summary[:250].rstrip() + "..."
                return summary or clean_text[:250].rstrip() + "..."
        except Exception as e:
            logger.warning(f"[ai_service] summarize_course_for_bale fallback: {e}")

        # Fallback if AI provider is unreachable: truncate gracefully
        return clean_text[:250].rstrip() + "..."


ai_service = AIService()
format_model_badge = ai_service.format_model_badge
get_provider_config = ai_service.get_provider_config
AI_PROVIDERS = ["vyceai", "nara", "gemini", "custom"]

async def generate_ai_response(user_message: str, provider: Optional[str] = None, api_key: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    if api_key is not None and not api_key.strip():
        return {"ok": False, "error": "کلید دسترسی (API Key) تنظیم نشده است."}
    return await ai_service.chat(user_message, provider=provider, model=model)

def format_ai_response_with_badge(res: Dict[str, Any]) -> str:
    if not res.get("ok"):
        return f"❌ {res.get('error', 'خطا در پردازش هوش مصنوعی')}"
    badge = ai_service.format_model_badge(res.get("model"))
    return f"{res.get('reply', '').strip()}{badge}"
