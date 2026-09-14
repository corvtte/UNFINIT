---
title: Unfinit Multi Platform Engine
emoji: ⚡
colorFrom: indigo
colorTo: blue
sdk: gradio
app_file: app.py
pinned: false
---

# ⚡ هاب چندپلتفرمه و موتور رسانه‌ای و فروشگاهی UNFINIT (v0.2.3)

[![Engine Version](https://img.shields.io/badge/version-v0.2.3-blue.svg)](https://github.com/corvtte/UNFINIT)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11-brightgreen.svg)](https://python.org)
[![Hugging Face Spaces](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Spaces-yellow)](https://huggingface.co/spaces/Foadian/UNFINIT)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

هاب جامع، ابری و یکپارچه برای مدیریت استودیوی وب رسانه و صوت (Web Mp3tag Studio)، فروشگاه دوره‌های تخصصی، سیستم هوش مصنوعی دوموتوره (Google Gemini و Nara Router)، و هماهنگی کامل بین پیام‌رسان‌های تلگرام، بله و روبیکا با معماری ماژولار و ضدگلوله جاوااسکریپت.

---

## 🌟 قابلیت‌های برجسته در نگارش v0.2.3

### ۱. معماری ماژولار و ضدگلوله جاوااسکریپت (Sandboxed JavaScript Architecture)
- تفکیک کدهای کلاینت وب‌پنل به ۴ بلوک خوداجرا (IIFE) و مجزا همراه با بلوک‌های ایزوله try...catch:
  1. **ماژول ناوبری و سوئیچ تب‌ها (Navigation Module)** با مکانیزم Event Delegation و حذف وابستگی‌های آسیب‌پذیر inline onclick
  2. **ماژول استودیوی رسانه و ویرایشگر متادیتا (Studio & Media Hub Module)**
  3. **ماژول فروشگاه، سفارشات، کوپن‌ها و دیسپچ (Store & Orders Module)**
  4. **ماژول هوش مصنوعی، تنظیمات و لاگ‌های زنده (AI & Settings Module)**
- مدیریت سوئیچ تب‌ها با اتریبیوت‌های استاندارد data-tab و همگام‌سازی کامل در لود صفحه با ذخیره‌سازی وضعیت در localStorage.

### ۲. رابط کاربری مدرن با اسکرول‌بار داینامیک و پشتیبانی از تم‌های محبوب
- اتصال مستقیم رنگ اسکرول‌بار به متغیرهای CSS تم.
- پالایش کامل رنگ‌های هاردکد شده و هماهنگی بی‌نقص با انواع تم‌ها: UNFINIT Classic، Catppuccin، Dracula، Tokyo Night، Vesper، Solarized Dark، Monokai و One Dark Pro.
- طراحی کاملاً واکنش‌گرا (Responsive) سازگار با انواع ابعاد نمایشگرها، تبلت و موبایل.

### ۳. پردازش و آپلودر هوشمند لینک‌های مستقیم در تلگرام (URL Sniffer Gate)
- پشتیبانی از تشخیص هوشمند انواع لینک‌های مستقیم دانلود با الگوهای پیشرفته Regex.
- احراز هویت ادمین به صورت Type-safe و بررسی ترکیبی ADMIN_USER_IDS و TELEGRAM_OWNER_ID.
- منوی شیشه‌ای کامل تعاملی:
  - ⚡️ شروع و تبدیل خودکار به فایل تلگرام
  - 🎥 دریافت در حالت ویدیو (پخش استریم در تلگرام)
  - 📁 دریافت در حالت فایل و سند
  - 🎵 استخراج هوشمند صوت ویدیو و تبدیل به MP3
  - ❌ انصراف از عملیات

### ۴. استودیوی رسانه و صوت تحت وب (Web Mp3tag Studio)
- ویرایشگر آنلاین تگ‌های ID3، عنوان، خواننده، آلبوم و کاور آرت با Mutagen و FFmpeg.
- موج‌نگار زنده صوتی (Live Waveform) مبتنی بر Wavesurfer.js نسخه ۷.
- برش هوشمند و دقیق فایل‌های صوتی (Audio Trimmer) بدون افت کیفیت.
- فشرده‌سازی خودکار و هوشمند فایل‌ها متناسب با سقف آپلود پیام‌رسان بله (۴۹.۹۹ مگابایت).
- پشتیبانی از سشن کاربری روبیکا برای انتقال امن فایل‌های تا سقف ۲ گیگابایت به Saved Messages.

### ۵. هوش مصنوعی دوموتوره و روتر نارا
- **Google Gemini مستقیم:** پشتیبانی از مدل‌های gemini-3.8-flash (پیش‌فرض)، gemini-3.7-flash، gemini-3.6-flash و gemini-3.1-pro.
- **Nara Router (طرح رایگان):** مدل‌های رایگان و پرسرعت مانند nemotron-3.5-lightning-free جهت مکالمات آنی و پاسخ‌های فوری.

---

## 🏗️ ساختار ماژولار پروژه

```text
├── app.py                      # نقطه ورود اصلی سیستم، سرور وب و شنوندگان پیام‌رسان‌ها
├── core/
│   ├── config.py               # متغیرهای سیستمی، نگارش انجین و تنظیمات امنیتی
│   └── database.py             # پایگاه‌داده SQLite، مدیریت تراکنش‌ها، کوپن‌ها و رسانه‌ها
├── platforms/
│   ├── telegram_adapter.py     # درایور پیشرفته تلگرام (Pyrogram MTProto v2)
│   ├── bale_adapter.py         # درایور پیام‌رسان بله (Bot API + درگاه پرداخت بانکی)
│   └── rubika_adapter.py       # درایور سشن کاربری روبیکا (انتقال رسانه به Saved Messages)
├── services/
│   ├── web_panel.py            # وب‌پنل مدرن TailwindCSS با معماری ۴ ماژوله Sandboxed JS
│   ├── ai_agent_service.py     # دستیار هوشمند، تشخیص قصد (Intent) و مدیریت مکالمات
│   ├── media_service.py        # پردازش صوت و تصویر، استخراج تگ و ترنسکد با FFmpeg
│   ├── store_service.py        # هسته مدیریت دوره‌ها، صدور فاکتور و اعتبارسنجی پرداخت
│   └── url_service.py          # دانلود و استریمینگ پرسرعت لینک‌های اینترنتی
├── scripts/
│   └── hf_manager.py           # همگام‌ساز خودکار با ریپازیتوری Hugging Face Spaces
└── tests/                      # سوئیت جامع تست‌های خودکار و بدون وابستگی
```

---

## 🚀 راه‌اندازی سریع (Quick Start)

### ۱. نصب پیش‌نیازها
- Python 3.10 یا بالاتر
- FFmpeg (جهت پردازش و ترنسکدینگ فایل‌های چندرسانه‌ای)

### ۲. راه‌اندازی محیط و نصب وابستگی‌ها
```bash
git clone https://github.com/corvtte/UNFINIT.git
cd UNFINIT

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### ۳. اجرای برنامه
```bash
python app.py
```
پنل وب به صورت پیش‌فرض روی آدرس `http://localhost:7860` در دسترس خواهد بود.

---

## 🧪 اجرای آزمون‌ها (Testing)

برای اجرای سوئیت تست‌های سریع:
```bash
python -m unittest discover -s tests -p "test_*_fast.py"
```

---

## 📄 لایسنس
این پروژه تحت مجوز MIT توسعه یافته و منتشر شده است.
