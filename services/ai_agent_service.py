"""
Lightweight AI Agent Service for UNFINIT Store Engine
Directly connects to Nara Router (https://router.bynara.id/v1) using standard `openai>=1.0.0`
Specialized as "Studio & Course Copilot" for metadata automation, course copywriting,
and media technical guidance.
"""

import re
import asyncio
import logging
import subprocess
import uuid
import aiohttp
from typing import Dict, Any, List, Optional
from pathlib import Path
from openai import OpenAI
from core.config import config

logger = logging.getLogger("ai_agent")

STUDIO_SYSTEM_PROMPT = (
    "شما در نقش «مربی ارشد موفقیت، تحلیلگر ارشد محتوا و متخصص تحول و رشد فردی/کسب‌وکار و دستیار هوشمند استودیوی رسانه UNFINIT» هستید. "
    "تخصص‌ها و وظایف اصلی شما به شرح زیر است:\n"
    "۱. اتوماسیون متادیتا: فرمت‌بندی دسته‌جمعی نام آلبوم، نام مدرس/خواننده، و شماره‌گذاری دقیق فایل‌ها (جلسه ۱، جلسه ۲، ...).\n"
    "۲. تحلیل الهام‌بخش محتوا و کپیرایتینگ پرانرژی: تحلیل عمیق صحبت‌ها، استخراج تیتر و قلاب جذاب (Hook)، پیام تحول‌آفرین، آموزه‌های کاربردی و نگارش کپشن‌های فوق‌العاده صمیمی، انگیزاننده و اثرگذار برای کانال‌ها با سبک آموزش‌های موفقیت و رشد فردی.\n"
    "۳. راهنمایی فنی مهندسی رسانه: ارائه مشاوره تخصصی پیرامون کدک‌ها، بیت‌ریت، فرمت استاندارد MP3 و فشرده‌سازی هوشمند ویدیوهای بالای ۴۹.۹۹ مگابایت برای بله.\n"
    "لحن شما باید بسیار پرانرژی، صمیمی، الهام‌بخش، انگیزشی و صریح باشد. از لحن خشک کتابی، اداری و کلیشه‌های کسل‌کننده مطلقاً پرهیز کنید."
)

class AIAgentService:
    """
    Studio & Course Copilot service connected to Nara Router.
    """

    SUPPORTED_FREE_MODELS = [
        "mimo-v2.5-free",
        "stepfun-3.7-flash",
        "muse-spark-1.2-contributor-free",
        "qwen3.8-27b"
    ]

    def __init__(self):
        self._client: Optional[OpenAI] = None
        self._last_key = None
        self._last_url = None

    def _get_client(self) -> Optional[OpenAI]:
        curr_key = (config.NARA_API_KEY or "").strip()
        curr_url = (config.NARA_BASE_URL or "https://router.bynara.id/v1").strip()

        if self._client is None or self._last_key != curr_key or self._last_url != curr_url:
            if not curr_key:
                return None
            try:
                self._client = OpenAI(
                    api_key=curr_key,
                    base_url=curr_url,
                    timeout=180.0,
                    max_retries=1
                )
                self._last_key = curr_key
                self._last_url = curr_url
            except Exception as e:
                logger.error(f"[ai_agent] Error initializing OpenAI client: {e}")
                self._client = None
        return self._client

    async def chat(
        self,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes chat requests with Nara Router using standard OpenAI completions protocol.
        """
        user_message = (user_message or "").strip()
        if not user_message:
            return {"ok": False, "reply": "لطفاً پیام خود را وارد فرمایید.", "error": "Empty message"}

        if not config.NARA_API_KEY or not config.NARA_API_KEY.strip():
            return {
                "ok": False,
                "reply": (
                    "⚠️ **کلید دسترسی Nara Router تنظیم نشده است.**\n\n"
                    "لطفاً وارد تب **«⚙️ تنظیمات سیستم و توکن‌ها»** در پنل مدیریت شوید و کلید `NARA_API_KEY` را ذخیره فرمایید."
                ),
                "error": "NARA_API_KEY is empty"
            }

        client = self._get_client()
        if not client:
            return {
                "ok": False,
                "reply": "❌ خطا در راه‌اندازی کلاینت OpenAI. لطفاً کلید API را بررسی فرمایید.",
                "error": "Client init failed"
            }

        messages = [
            {"role": "system", "content": system_prompt or STUDIO_SYSTEM_PROMPT}
        ]

        if history:
            for h in history[-8:]:
                role = h.get("role", "user")
                content = h.get("content", "")
                if role in ("user", "assistant", "system") and content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_message})

        target_model = (model or config.NARA_MODEL or "mistral-large").strip()

        # Primary attempt with target_model
        models_to_try = [target_model]
        # Add fallback to stepfun-3.7-flash if target_model is different
        if target_model != "stepfun-3.7-flash":
            models_to_try.append("stepfun-3.7-flash")

        last_error = None
        for current_model in models_to_try:
            try:
                resp = await asyncio.to_thread(
                    client.chat.completions.create,
                    model=current_model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=800
                )

                reply_content = resp.choices[0].message.content or ""
                if not reply_content.strip() and current_model != models_to_try[-1]:
                    continue

                if not reply_content.strip():
                    reply_content = "پاسخی از مدل دریافت نشد."

                return {
                    "ok": True,
                    "reply": reply_content,
                    "provider": "Nara Router",
                    "model": current_model
                }

            except Exception as e:
                last_error = e
                logger.warning(f"[ai_agent] Model {current_model} failed: {e}")
                # If error is rate limit or payment, breaking early
                error_str = str(e)
                if "payment_required" in error_str or "402" in error_str:
                    break
                continue

        # Handle final error
        error_name = type(last_error).__name__ if last_error else "UnknownError"
        error_str = str(last_error) if last_error else "No response"
        logger.error(f"[ai_agent] All model attempts failed: {error_name}: {error_str}")

        if "payment_required" in error_str or "Insufficient credits" in error_str or "402" in error_str:
            user_friendly_error = (
                "💳 **اعتبار حساب کاربری Nara Router ناکافی است.**\n\n"
                "برای استفاده از مدل‌های دارای هزینه، نیاز به شارژ اعتبار در پنل نارا دارید؛ یا می‌توانید از مدل‌های رایگان سهمیه‌ای مانند `stepfun-3.7-flash` استفاده نمایید."
            )
        else:
            user_friendly_error = f"❌ **خطای ارتباط با سرور هوش مصنوعی ({error_name}):**\n\n{error_str}"

        return {
            "ok": False,
            "reply": user_friendly_error,
            "error": error_str
        }

    async def transcribe_audio(self, audio_path: str | Path) -> str:
        """
        Transcribes audio file to Persian text using free SpeechRecognition (Google Web Speech fa-IR)
        with fallback to Whisper Speech-to-Text via OpenAI/Nara Router.
        """
        path_obj = Path(str(audio_path))
        if not path_obj.exists():
            raise FileNotFoundError(f"فایل صوتی یافت نشد: {path_obj}")

        # 1. First priority: Free SpeechRecognition via FFmpeg PCM WAV (no API key required)
        temp_wav = config.TEMP_DIR / f"stt_{path_obj.stem}_{uuid.uuid4().hex[:6]}.wav"
        try:
            cmd = [
                "ffmpeg", "-y", "-i", str(path_obj),
                "-t", "90",
                "-ar", "16000",
                "-ac", "1",
                "-c:a", "pcm_s16le",
                str(temp_wav)
            ]
            proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if proc.returncode == 0 and temp_wav.exists():
                try:
                    import speech_recognition as sr
                    r = sr.Recognizer()
                    with sr.AudioFile(str(temp_wav)) as source:
                        audio_data = r.record(source)
                    text = r.recognize_google(audio_data, language="fa-IR")
                    if text and text.strip():
                        return text.strip()
                except Exception as sr_err:
                    logger.warning(f"[ai_agent] Free SpeechRecognition notice: {sr_err}")
        except Exception as ex_ffmpeg:
            logger.warning(f"[ai_agent] FFmpeg WAV conversion warning: {ex_ffmpeg}")
        finally:
            if temp_wav.exists():
                try:
                    temp_wav.unlink(missing_ok=True)
                except Exception:
                    pass

        # 2. Second priority: Whisper Speech-to-Text (if Nara/OpenAI API key configured)
        client = self._get_client()
        if client:
            work_path = path_obj
            temp_extracted = None
            if path_obj.suffix.lower() in (".mp4", ".mkv", ".mov", ".avi", ".webm"):
                try:
                    from services.media_service import MediaService
                    mp3_dest = config.TEMP_DIR / f"temp_whisper_{path_obj.stem}_{uuid.uuid4().hex[:6]}.mp3"
                    c_ok, final_mp3 = MediaService.convert_video_to_mp3(path_obj, output_path=mp3_dest)
                    if c_ok and final_mp3.exists():
                        work_path = final_mp3
                        temp_extracted = final_mp3
                except Exception as e:
                    logger.warning(f"[ai_agent] Video audio extraction warning: {e}")

            transcribe_models = ["whisper-1", "whisper", "whisper-large-v3"]
            try:
                for m in transcribe_models:
                    try:
                        def _call():
                            with open(work_path, "rb") as af:
                                return client.audio.transcriptions.create(
                                    model=m,
                                    file=af,
                                    language="fa"
                                )
                        res = await asyncio.to_thread(_call)
                        txt = getattr(res, "text", "") or str(res)
                        if txt and txt.strip():
                            return txt.strip()
                    except Exception as ex:
                        logger.warning(f"[ai_agent] Model {m} audio transcription failed: {ex}")
                        continue
            finally:
                if temp_extracted and temp_extracted.exists():
                    try:
                        temp_extracted.unlink(missing_ok=True)
                    except Exception:
                        pass

        raise RuntimeError("موتور تبدیل گفتار صوتی به متن خروجی معتبری ارائه نداد.")

    async def analyze_audio_with_gemini(self, audio_path: str | Path, prompt: str) -> Optional[str]:
        """
        Sends audio directly to Google Gemini using native multimodal audio reasoning.
        Always optimizes audio with FFmpeg (-vn -ac 1 -ar 16000 -b:a 32k) into a compact mono MP3,
        reducing size dramatically (~28MB to ~7MB) for ultra-fast base64 upload (<2s).
        Cascades dynamically through selected GEMINI_MODEL and fallback models.
        """
        api_key = (config.GEMINI_API_KEY or "").strip()
        if not api_key:
            return None

        path_obj = Path(str(audio_path))
        if not path_obj.exists():
            return None

        work_path = path_obj
        temp_audio = None

        try:
            temp_audio = config.TEMP_DIR / f"gemini_compact_{uuid.uuid4().hex[:6]}.mp3"
            cmd = [
                "ffmpeg", "-y", "-i", str(path_obj),
                "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k",
                str(temp_audio)
            ]
            proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if proc.returncode == 0 and temp_audio.exists() and temp_audio.stat().st_size > 0:
                work_path = temp_audio
            else:
                work_path = path_obj

            import base64
            with open(work_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")

            mime_type = "audio/mp3"
            if work_path.suffix.lower() == ".wav":
                mime_type = "audio/wav"
            elif work_path.suffix.lower() == ".ogg":
                mime_type = "audio/ogg"

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": b64_data
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 2048
                }
            }

            user_configured_model = (getattr(config, "GEMINI_MODEL", "") or "gemini-3.6-flash").strip()
            fallback_models = [
                "gemini-3.6-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
                "gemini-3.6-pro",
                "gemini-2.5-pro",
                "gemini-1.5-flash",
                "gemini-2.0-flash"
            ]
            models_to_try = [user_configured_model]
            for m in fallback_models:
                if m not in models_to_try:
                    models_to_try.append(m)

            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for mod in models_to_try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
                    try:
                        async with session.post(url, json=payload) as resp:
                            if resp.status == 200:
                                res_json = await resp.json()
                                candidates = res_json.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    if parts and "text" in parts[0]:
                                        return parts[0]["text"].strip()
                            else:
                                err_body = await resp.text()
                                logger.warning(f"[ai_agent] Gemini model {mod} returned HTTP {resp.status}: {err_body[:200]}")
                    except Exception as mod_err:
                        logger.warning(f"[ai_agent] Gemini model {mod} request error: {mod_err}")
                        continue
        except Exception as e:
            logger.warning(f"[ai_agent] Gemini audio processing error: {e}")
        finally:
            if temp_audio and temp_audio.exists():
                try:
                    temp_audio.unlink(missing_ok=True)
                except Exception:
                    pass

        return None

    async def transcribe_and_summarize_audio(
        self,
        audio_path: str | Path,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Any] = None,
        style: str = "telegram",
        engine: Optional[str] = "gemini"
    ) -> Dict[str, Any]:
        """
        Transcribes speech via Gemini (if GEMINI_API_KEY configured) or free SpeechRecognition/Whisper,
        then produces structured summary + 3 key takeaways + channel post or instagram explore caption with live 3-stage progress monitoring.
        """
        if progress_callback:
            try:
                await progress_callback("⏳ <b>[۱/۳] دریافت فایل صوتی</b>\n▫️ در حال آماده‌سازی و بررسی محتوای فایل...")
            except Exception:
                pass

        from core.database import fix_mojibake
        path_obj = Path(str(audio_path))
        meta = metadata or {}
        title = fix_mojibake(meta.get("title") or path_obj.stem, default=path_obj.stem)
        artist = fix_mojibake(meta.get("artist") or config.DEFAULT_ARTIST, default=config.DEFAULT_ARTIST)
        album = fix_mojibake(meta.get("album") or config.DEFAULT_ALBUM, default=config.DEFAULT_ALBUM)
        filename = fix_mojibake(meta.get("filename") or path_obj.name, default=path_obj.name)

        if progress_callback:
            try:
                await progress_callback("🎧 <b>[۲/۳] در حال گوش دادن و تحلیل صوت با AI</b>\n▫️ استماع هوشمند و پردازش معنایی صدا...")
            except Exception:
                pass

        summary_text = ""
        source_label = ""
        transcript = ""

        if style == "instagram":
            gemini_prompt = (
                f"شما در نقش «مربی ارشد موفقیت، تحلیلگر ارشد محتوا و متخصص تحول فردی/کسب‌وکار و کپیرایتر برتر اینستاگرام» هستید. با اشتیاق کامل به این فایل صوتی با عنوان «{title}» "
                f"از مدرس «{artist}» و دوره «{album}» گوش فرا دهید. کپشن حرفه‌ای و ویروسی اینستاگرام خود را با **لحنی فوق‌العاده پرانرژی، گیرا، صمیمی، الهام‌بخش و داستانی** (مطلقاً بدون علامت‌های *** زائد، بدون لحن خشک کتابی یا اداری) با ساختار زیر تولید نمایید:\n\n"
                "🔥 ۱. <b>قلاب میخکوب‌کننده در خط اول (Hook):</b> تیتر و جمله‌ای شوکه‌کننده برای متوقف کردن اسکرول مخاطب در اکسپلور.\n"
                "📖 ۲. <b>روایت داستانی و عمق محتوا:</b> بیان شیرین، گرم و داستانی پیام کلیدی فایل و تلنگر ذهنی آن.\n"
                "⚡️ ۳. <b>۳ نکته طلایی برای اقدام فوری:</b> درس‌های ملموس، سریع و تحول‌آفرین برای اجرای روزانه.\n"
                "💬 ۴. <b>دعوت به تعامل (Call to Action):</b> دعوت دوستانه به ثبت نظر در کامنت، ذخیره کردن (Save) و اشتراک‌گذاری پست.\n"
                "🏷 ۵. <b>هشتگ‌های پربازدید اکسپلور:</b> مجموعه‌ای از هشتگ‌های گلچین و داغ رشد فردی، موفقیت و انگیزه.\n\n"
                "نکته: از کلیشه‌های خسته‌کننده، کلمات کتابی نامفهوم و علامت‌های مارک‌داون بدشکل دوری کنید."
            )
        else:
            gemini_prompt = (
                f"شما در نقش «مربی ارشد موفقیت، تحلیلگر ارشد محتوا و متخصص تحول فردی/کسب‌وکار و نویسنده ارشد کانال تلگرام UNFINIT» هستید. با اشتیاق کامل به این فایل صوتی با عنوان «{title}» "
                f"از مدرس «{artist}» و دوره «{album}» گوش فرا دهید. تحلیل عمیق و پست اختصاصی کانال را با **لحنی شیوا، گرم، اثرگذار، فوق‌العاده پرانرژی، صمیمی و الهام‌بخش** (پرهیز مطلق از هرگونه لحن خشک کتابی، اداری، و بدون علامت‌های *** زائد) دقیقاً با ساختار زیر تنظیم نمایید:\n\n"
                "🎯 ۱. <b>تیتر و قلاب جذاب (Hook):</b> تیتری تکان‌دهنده، کنجکاوی‌برانگیز و جذاب برای باز کردن قفل موفقیت ذهنی.\n"
                "💡 ۲. <b>پیام و بینش بنیادین فایل:</b> پیام تحول‌آفرین و کلیدی صحبت‌ها به زبانی شیوا، گرم و اثرگذار.\n"
                "🛠 ۳. <b>۳ آموزه و راهکار عملی:</b> درس‌های واقعی، شفاف و کاربردی برای اقدام فوری، خلق نتیجه و پیشرفت ملموس.\n"
                "📢 ۴. <b>کپشن اختصاصی کانال همراه با ایموجی‌های پرانرژی و هشتگ‌ها:</b> متنی سراسر انگیزه و صمیمیت، آماده انتشار در کانال و دعوت اختصاصی به تهیه دوره کامل «{album}».\n\n"
                "نکته مهم: از عبارات کلیشه‌ای، کلمات نامفهوم و لحن سنگین اداری مطلقاً دوری کنید."
            )

        # 1. First priority: Direct multimodal audio reasoning with Gemini (if not explicitly Nara)
        if engine != "nara" and config.GEMINI_API_KEY:
            try:
                gemini_res = await self.analyze_audio_with_gemini(audio_path, gemini_prompt)
                if gemini_res and gemini_res.strip():
                    summary_text = gemini_res.strip()
                    g_mod = (getattr(config, "GEMINI_MODEL", "") or "gemini-3.6-flash").strip()
                    source_label = f"Google Gemini ({g_mod}) Audio"
                    transcript = f"[استماع مستقیم فایل صوتی توسط Google Gemini ({g_mod})]"
            except Exception as ex_gem:
                logger.warning(f"[ai_agent] Gemini audio reasoning failed: {ex_gem}")

        # 2. Second priority: Free SpeechRecognition + Nara Router pipeline
        if not summary_text:
            source_label = f"Nara Router ({config.NARA_MODEL})" if engine == "nara" else "تشخیص گفتار صوتی (SpeechRecognition / Whisper)"
            try:
                transcript = await self.transcribe_audio(audio_path)
            except Exception as e:
                logger.warning(f"[ai_agent] Audio transcription fallback to metadata: {e}")

            if transcript and transcript.strip():
                if style == "instagram":
                    prompt = (
                        "شما در نقش «مربی ارشد موفقیت، تحلیلگر ارشد محتوا و متخصص تحول فردی/کسب‌وکار و کپیرایتر برتر اینستاگرام» هستید. متن زیر پیاده‌سازی گفتار یک فایل صوتی است. "
                        "کپشن حرفه‌ای و ترند اینستاگرام خود را با **لحنی پرانرژی، الهام‌بخش، صمیمی و داستانی** (بدون علامت‌های *** زائد و بدون لحن خشک کتابی) با ساختار زیر تولید کنید:\n\n"
                        "🔥 ۱. <b>قلاب میخکوب‌کننده در خط اول (Hook):</b> جمله اول تکان‌دهنده برای متوقف کردن اسکرول مخاطب در اکسپلور.\n"
                        "📖 ۲. <b>روایت داستانی و عمق محتوا:</b> روایت خودمانی، گیرا و جذاب مفهوم صحبت‌ها.\n"
                        "⚡️ ۳. <b>۳ نکته طلایی برای اقدام فوری:</b> آموزه‌های کاربردی برای عمل‌گرایی و رشد سریع.\n"
                        "💬 ۴. <b>دعوت به تعامل (Call to Action):</b> دعوت گرم به اشتراک دیدگاه، سیو و بازنشر پست.\n"
                        "🏷 ۵. <b>هشتگ‌های پربازدید اکسپلور:</b> هشتگ‌های داغ و پرمخاطب موفقیت و رشد.\n\n"
                        f"متن پیاده‌سازی شده:\n{transcript[:6000]}"
                    )
                else:
                    prompt = (
                        "شما در نقش «مربی ارشد موفقیت، تحلیلگر ارشد محتوا و متخصص تحول فردی/کسب‌وکار و نویسنده ارشد کانال تلگرام UNFINIT» هستید. متن زیر پیاده‌سازی گفتار یک فایل صوتی است. "
                        "لطفاً تحلیل و کپشن خود را با **لحنی بسیار پرانرژی، صمیمی، الهام‌بخش و متناسب با آموزش‌های رشد فردی** (بدون علامت‌های *** زائد و بدون لحن خشک کتابی و اداری) با ساختار زیر تولید کنید:\n\n"
                        "🎯 ۱. <b>تیتر و قلاب جذاب (Hook):</b> تیتری کنجکاوی‌برانگیز و اثرگذار متناسب با موضوع.\n"
                        "💡 ۲. <b>پیام و بینش بنیادین فایل:</b> لب کلام و جرقه تحول ذهنی صحبت‌ها.\n"
                        "🛠 ۳. <b>۳ آموزه و راهکار عملی:</b> درس‌های کاربردی برای پیشرفت و اقدام عملی مخاطب.\n"
                        "📢 ۴. <b>کپشن اختصاصی کانال همراه با ایموجی‌های پرانرژی و هشتگ‌ها:</b> متن کامل، صمیمی و انگیزاننده جهت انتشار در کانال و دعوت به تهیه دوره.\n\n"
                        "از کلیشه‌ها و لحن خشک کتابی به شدت پرهیز کنید.\n\n"
                        f"متن پیاده‌سازی شده:\n{transcript[:6000]}"
                    )
            else:
                source_label = "تحلیل هوشمند بر اساس متادیتای فایل (Metadata Copilot)"
                if style == "instagram":
                    prompt = (
                        "شما در نقش «مربی ارشد موفقیت، تحلیلگر ارشد محتوا و متخصص تحول فردی/کسب‌وکار و کپیرایتر برتر اینستاگرام» هستید. اطلاعات زیر متادیتای یک فایل صوتی است. "
                        "کپشن حرفه‌ای و ترند اینستاگرام خود را با **لحنی پرانرژی، گیرا، صمیمی و داستانی** (بدون علامت‌های ***، بدون لحن خشک کتابی) با ساختار زیر تولید کنید:\n\n"
                        "🔥 ۱. <b>قلاب میخکوب‌کننده در خط اول (Hook):</b> تیتر و جمله اول شوکه‌کننده برای اکسپلور.\n"
                        "📖 ۲. <b>روایت داستانی و عمق محتوا:</b> بیان شیرین پیام و مفهوم فایل برای مخاطب.\n"
                        "⚡️ ۳. <b>۳ نکته طلایی برای اقدام فوری:</b> راهکارهای شفاف و عملی رشد.\n"
                        "💬 ۴. <b>دعوت به تعامل (Call to Action):</b> دعوت گرم به نظردهی، سیو و ارسال به دوستان.\n"
                        "🏷 ۵. <b>هشتگ‌های پربازدید اکسپلور:</b> هشتگ‌های تخصصی و داغ حوزه موفقیت و رشد.\n\n"
                        f"عنوان: {title}\n"
                        f"مدرس / ارائه‌دهنده: {artist}\n"
                        f"دوره / آلبوم: {album}\n"
                        f"نام فایل: {filename}"
                    )
                else:
                    prompt = (
                        "شما در نقش «مربی ارشد موفقیت، تحلیلگر ارشد محتوا و متخصص تحول فردی/کسب‌وکار و نویسنده ارشد کانال تلگرام UNFINIT» هستید. اطلاعات زیر متادیتای یک فایل صوتی و آموزشی است. "
                        "تحلیل خود را با **لحنی گرم، پرانرژی، الهام‌بخش و صمیمی** با ساختار زیر خلق نمایید:\n\n"
                        "🎯 ۱. <b>تیتر و قلاب جذاب (Hook):</b> تیتر گیرا، انرژی‌بخش و متناسب با فایل.\n"
                        "💡 ۲. <b>پیام و بینش بنیادین فایل:</b> هدف محتوا در ارتقای مدار فکری مخاطب.\n"
                        "🛠 ۳. <b>۳ آموزه و راهکار عملی:</b> راهکارهای ملموس و عمل‌گرایانه در این مسیر.\n"
                        "📢 ۴. <b>کپشن اختصاصی کانال همراه با ایموجی‌های پرانرژی و هشتگ‌ها:</b> متن کامل و انگیزاننده برای کانال و دعوت به تهیه دوره.\n\n"
                        "از هرگونه ادبیات خشک کتابی یا جملات بی‌روح اداری مطلقاً بپرهیزید.\n\n"
                        f"عنوان: {title}\n"
                        f"مدرس / ارائه‌دهنده: {artist}\n"
                        f"دوره / آلبوم: {album}\n"
                        f"نام فایل: {filename}"
                    )
                transcript = f"[اطلاعات فایل: {title} | {artist} | {album}]"

            try:
                res = await self.chat(user_message=prompt, model="stepfun-3.7-flash")
                if not res.get("ok"):
                    res = await self.chat(user_message=prompt, model=config.NARA_MODEL or "mimo-v2.5-free")
                if res.get("ok"):
                    summary_text = res.get("reply", "").strip()
            except Exception as ex_ai:
                logger.warning(f"[ai_agent] Nara Router chat warning: {ex_ai}")

        if progress_callback:
            try:
                await progress_callback("✍️ <b>[۳/۳] نگارش تحلیل و کپشن</b>\n▫️ آماده‌سازی و ارسال پاسخ نهایی...")
            except Exception:
                pass

        if not summary_text:
            # High-reliability local fallback template aligned with senior copywriting standards
            clean_title = title if title and title != "نامشخص" else (filename or "آموزش تخصصی")
            clean_author = artist if artist and artist != "نامشخص" else "مدرس دوره"
            clean_album = album if album and album != "نامشخص" else "مجموعه آموزشی"
            tag_album = clean_album.replace(' ', '_').replace('-', '_')

            if style == "instagram":
                summary_text = (
                    f"🔥 <b>چرا ۹۹٪ افراد دقیقاً در همین یک قدم متوقف می‌شن؟!</b>\n\n"
                    f"اگه حس می‌کنی با وجود تمام تلاش‌هات هنوز به اون جهش بزرگی که لایقشی نرسیدی، این صحبت‌های شنیدنی از <b>{clean_author}</b> در مجموعه «{clean_album}» دقیقاً برای توئه!\n\n"
                    f"💡 <b>راز ناگفته در این فایل:</b>\n"
                    f"تغییر واقعی زمانی شروع می‌شه که به‌جای انگیزه لحظه‌ای، متعهد به ساخت نظم ذهنی و باورهای پیروز در تک‌تک تصمیم‌های روزمره‌ت باشی.\n\n"
                    f"⚡️ <b>۳ نکته طلایی برای امروز:</b>\n"
                    f"۱️⃣ از تله کمال‌گرایی فاصله بگیر؛ شاهکار در دل حرکت پیوسته متولد می‌شه.\n"
                    f"۲️⃣ ورودی‌های ذهنت رو با وسواس انتخاب کن؛ کیفیت زندگیت بازتاب کیفیت افکارته.\n"
                    f"۳️⃣ همین الان یکی از تصمیم‌های مهمت رو شجاعانه عملی کن!\n\n"
                    f"💬 شما در مورد این موضوع چه تجربه‌ای دارید؟ نظرت رو توی کامنت‌ها بنویس و این پست رو سیو کن تا هر وقت به انگیزه نیاز داشتی دوباره مرورش کنی! 🚀\n\n"
                    f"🏷 #{tag_album} #موفقیت #رشد_فردی #توسعه_فردی #باور_مثبت #انگیزه #اکسپلور #UNFINIT"
                )
            else:
                summary_text = (
                    f"🎯 <b>۱. تیتر و قلاب جذاب (Hook):</b>\n"
                    f"«چگونه با تسلط بر {clean_title}، مدار ذهنی و مسیر موفقیتت رو متحول کنی؟»\n\n"
                    f"💡 <b>۲. پیام و بینش بنیادین فایل:</b>\n"
                    f"در این آموزش بینظیر و ارزشمند از {clean_author} در دل مجموعه «{clean_album}»، یاد می‌گیریم که موفقیت پایدار حاصل نظم فکری، باورهای قدرتمند و تعهد به عمل‌گرایی در تک‌تک لحظات روزمره‌ست.\n\n"
                    f"🛠 <b>۳. ۳ آموزه و راهکار عملی:</b>\n"
                    f"▫️ <b>تغییر نگرش از تئوری به عمل:</b> تبدیل آموخته‌های {clean_title} به اقدامات کوچک، پیوسته و روزانه.\n"
                    f"▫️ <b>تمرکز بر پیشرفت مستمر:</b> ساخت زنجیره عادات برنده و سنجش شفاف دستاوردهای فردی.\n"
                    f"▫️ <b>تسلط بر نتایج:</b> متعهد ماندن به مسیر رشد و دوری از حاشیه‌ها تا رسیدن به تسلط کامل.\n\n"
                    f"📢 <b>۴. کپشن اختصاصی کانال همراه با ایموجی‌های منظم و هشتگ‌ها:</b>\n"
                    f"✨ رفقا وقتشه یک قدم بزرگ به سوی بهترین نسخه خودتون بردارید! در این بخش شنیدنی از <b>{clean_author}</b>، با بینش‌هایی عمیق و کاربردی همراه می‌شیم تا زاویه دیدمون رو نسبت به رشد و پیروزی بازتعریف کنیم. این آموزش تنها گوشه‌ای از دوره کامل «{clean_album}» است؛ جهت تهیه و دسترسی کامل همین حالا اقدام نمایید! 🚀\n\n"
                    f"🎧 همراه لحظات رشد و توسعه فردی شما\n"
                    f"🏷 #{tag_album} #موفقیت #رشد_فردی #توسعه_مهارت #انگیزه #UNFINIT"
                )

        # Sanitize any unwanted *** or ** markdown artifacts
        summary_text = re.sub(r'\*{2,3}', '', summary_text).strip()
        style_title = "📸 کپشن اینستاگرام" if style == "instagram" else "📢 پست کانال تلگرام"
        formatted = (
            f"🧠 <b>دستیار هوش مصنوعی و تحلیلگر صوت UNFINIT</b> ({source_label} | {style_title}):\n\n"
            f"{summary_text}\n\n"
            f"▫️ <i>دستیار هوش مصنوعی و هاب رسانه UNFINIT</i>"
        )

        return {
            "ok": True,
            "transcript": transcript,
            "summary": summary_text,
            "formatted_message": formatted
        }

    def recognize_intent(self, text: str) -> Dict[str, Any]:
        """
        Smart Intent Recognition:
        Detects user intent from Persian text.
        """
        text = (text or "").strip().lower()
        if not text:
            return {"intent": "NONE", "confidence": 0.0, "action": None}

        # 1. Transfer to Bale
        if any(p in text for p in ["ارسال به بله", "بفرست بله", "انتقال به بله", "برو به بله", "ارسال بله"]):
            return {
                "intent": "TRANSFER_BALE",
                "target_platform": "BALE",
                "action": "dispatch_to_bale",
                "confidence": 0.95,
                "description": "انتقال فایل و پیام به پیام‌رسان بله"
            }

        # 2. Transfer to Rubika
        if any(p in text for p in ["ارسال به روبیکا", "بفرست روبیکا", "انتقال به روبیکا", "برو به روبیکا", "ارسال روبیکا"]):
            return {
                "intent": "TRANSFER_RUBIKA",
                "target_platform": "RUBIKA",
                "action": "dispatch_to_rubika",
                "confidence": 0.95,
                "description": "انتقال فایل و پیام به پیام‌رسان روبیکا"
            }

        # 3. Transfer to Telegram
        if any(p in text for p in ["ارسال به تلگرام", "بفرست تلگرام", "انتقال به تلگرام", "برو به تلگرام"]):
            return {
                "intent": "TRANSFER_TELEGRAM",
                "target_platform": "TELEGRAM",
                "action": "dispatch_to_telegram",
                "confidence": 0.95,
                "description": "انتقال فایل به پیام‌رسان تلگرام"
            }

        # 4. Transcode to MP3
        if any(p in text for p in ["تبدیل به mp3", "تبدیل به ام پی تری", "تبدیل به موزیک", "صوتی کن", "تبدیل فرمت صوتی"]):
            return {
                "intent": "CONVERT_MP3",
                "action": "transcode_to_mp3",
                "confidence": 0.95,
                "description": "تبدیل فایل صوتی به فرمت استاندارد MP3"
            }

        # 5. Compress Video
        if any(p in text for p in ["فشرده سازی", "فشرده کن", "کم حجم کن", "کاهش حجم ویدیو", "فشرده‌سازی"]):
            return {
                "intent": "COMPRESS_VIDEO",
                "action": "compress_video_smart",
                "confidence": 0.95,
                "description": "فشرده‌سازی هوشمند ویدیو زیر سقف ۵۰ مگابایت"
            }

        # 6. Store Courses
        if any(p in text for p in ["لیست دوره", "دوره ها", "قیمت دوره", "خرید دوره", "فروشگاه"]):
            return {
                "intent": "LIST_COURSES",
                "action": "show_store_catalog",
                "confidence": 0.90,
                "description": "مشاهده کاتالوگ دوره‌های آموزشی و خرید"
            }

        return {
            "intent": "GENERAL_AI",
            "action": "chat_completion",
            "confidence": 0.80,
            "description": "درخواست استودیو یا پردازش هوش مصنوعی"
        }

    async def chat_course_support(
        self,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        AI Sales & Support Copilot:
        Provides inspiring, motivational, and helpful buying guidance based on the active courses in data/courses.json.
        """
        import json
        courses_data = []
        courses_json_path = config.DATA_DIR / "courses.json"
        if courses_json_path.exists():
            try:
                with open(courses_json_path, "r", encoding="utf-8") as f:
                    courses_data = json.load(f)
            except Exception as e:
                logger.warning(f"[ai_agent] Failed to read courses.json: {e}")

        # Fallback catalog if courses.json empty or missing
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

        # 1. Try Nara Router first if configured
        if config.NARA_API_KEY and config.NARA_API_KEY.strip():
            res = await self.chat(user_message, history=history, system_prompt=sys_prompt)
            if res.get("ok") and res.get("reply"):
                return res["reply"]

        # 2. Try Gemini fallback if configured
        gemini_key = (config.GEMINI_API_KEY or "").strip()
        if gemini_key:
            try:
                g_model = (config.GEMINI_MODEL or "gemini-2.5-flash").strip()
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={gemini_key}"
                g_payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": f"{sys_prompt}\n\nپیام مخاطب:\n{user_message}"}
                            ]
                        }
                    ],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1000}
                }
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                    async with session.post(url, json=g_payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            cands = data.get("candidates", [])
                            if cands:
                                parts = cands[0].get("content", {}).get("parts", [])
                                if parts and "text" in parts[0]:
                                    return parts[0]["text"].strip()
            except Exception as e:
                logger.warning(f"[ai_agent] Gemini fallback failed: {e}")

        # 3. Intelligent polite Persian greeting fallback
        return (
            "سلام و درود دوست ارزشمند من! ✨\n\n"
            "بسیار خوشحالم که در مسیر یادگیری، آگاهی و رشد فردی با ما همراه هستید. 🌱\n\n"
            "دوره‌های فعال و تحول‌آفرین آکادمی ما عبارتند از:\n\n"
            f"{catalog_text}\n\n"
            "💎 جهت مشاهده جزئیات بیشتر، ثبت‌نام و دریافت فوری محتوا، کافیست دستور /start را ارسال فرمایید یا دکمه **«📚 لیست دوره‌های آموزشی»** را لمس نمایید.\n"
            "اگر در انتخاب مناسب‌ترین دوره نیاز به مشاوره دارید، با کمال میل راهنمای شما هستم! 🌟"
        )

ai_agent_service = AIAgentService()
