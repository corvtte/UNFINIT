---
title: Unfinit Multi Platform Engine
emoji: ⚡
colorFrom: indigo
colorTo: blue
sdk: gradio
app_file: app.py
pinned: false
---

# ⚡ UNFINIT Multi-Platform Media & Store Engine (v0.1.0)

[![Engine Version](https://img.shields.io/badge/version-v0.1.0-blue.svg)](https://github.com/corvtte/UNFINIT)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11-brightgreen.svg)](https://python.org)
[![Hugging Face Spaces](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Spaces-yellow)](https://huggingface.co/spaces/Foadian/UNFINIT)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

هاب جامع، ابری و یکپارچه برای مدیریت فروشگاه دوره‌های آموزشی، پردازش صوت و رسانه با FFmpeg، متصل به پیام‌رسان‌های تلگرام، بله و روبیکا، درگاه‌های پرداخت هوشمند، روتر دوگانه هوش مصنوعی و پنل تحت وب مدرن.

---

## 🌟 ویژگی‌های کلیدی در نگارش v0.1.0

### ۱. سیستم تحویل هوشمند چندلینکی (Smart Multi-Link Delivery Parser)
- استخراج و تفکیک خودکار انواع لینک‌های دسترسی دوره آموزشی از فیلد متنی:
  - 🔵 **کانال / گروه تلگرام** (`t.me/...`)
  - 🟢 **کانال / گروه پیام‌رسان بله** (`ble.ir/...`)
  - 🟣 **کانال / گروه پیام‌رسان روبیکا** (`rubika.ir/...`)
  - 📥 **لینک‌های دانلود مستقیم، گوگل‌درایو، اسپات‌پلیر و وب‌سایت**
- تولید خودکار دکمه‌های شیشه‌ای تعاملی مجزا برای هر پلتفرم در پیام‌رسان‌های تلگرام و بله.
- درج پیام پایانی شخصی‌سازی‌شده و پرانرژی همراه با متغیر `COURSE_DELIVERY_NOTE`:
  > *"امیدوارم این دوره، براتون سرشار از آگاهی، رشد و نتایج ارزشمند باشه. ✨"*

### ۲. مدیریت و ویرایش دوره‌ها از درون ربات (In-Chat Course Management)
- برابری و تطابق کامل امکانات مدیریتی بین **تلگرام** و **بله**:
  - فعال/غیرفعال‌سازی لحظه‌ای دوره‌ها (`Toggle Active`)
  - ویرایش قیمت (`Edit Price`)
  - ویرایش لینک‌های دوره (`Edit Links`)
  - ویرایش توضیحات دوره (`Edit Description`)
  - ویرایش تصویر و بنر با تطبیق و تبدیل خودکار به نسبت استاندارد ۱۶:۹ با Pillow (`Edit Banner`)

### ۳. پایداری روبیکا و بهینه‌سازی Gateway
- پشتیبانی کامل از دکمه استارت اختصاصی روبیکا (`event_type == "button_click"` با `button_id == "start"`).
- مهار خطاهای سنگین Nginx 502/503/504 در چرخه `getUpdates` روبیکا و لاگ تمیز تک‌خطی بدون ایجاد اسپم در کنسول.

### ۴. تفکیک ساختاری پنل تنظیمات و همگام‌سازی ابری (Cloud Secrets Hub)
- تفکیک شفاف تنظیمات پنل وب به دو کارت مجزا و واکنش‌گرا (موبایل و دسکتاپ):
  - 🔐 **سکرت‌ها و کلیدهای محرمانه ابری (Cloud Secrets Hub)**: توکن‌های ربات‌ها، کلیدهای Gemini و Nara Router، توکن و شناسه Hugging Face Space و رمز عبور ادمین.
  - 🛍️ **تنظیمات عمومی فروشگاه و پیام‌رسان‌ها (Store & Messaging Settings)**: شناسه‌های عددی ادمین، متن‌های خوش‌آمدگویی و تحویل، مشخصات کارت بانکی، درگاه پرداخت و محدودیت‌های آپلود رسانه.
- همگام‌سازی خودکار و دوطرفه با Hugging Face Space Secrets بدون ذخیره‌سازی کلیدها در فایل‌های متنی عمومی.

---

## 🏗️ معماری ماژول‌ها و ساختار پروژه

```text
├── app.py                      # نقطه ورود اصلی Gradio / aiohttp و مدیریت لاگ‌ها
├── core/
│   ├── config.py               # ساختار متغیرهای پیکربندی و متدهای ریلود
│   └── database.py             # پایگاه داده داخلی SQLite / مدیریت سفارش‌ها و کاربران
├── platforms/
│   ├── telegram_adapter.py     # درایور تلگرام (مدیریت تعاملی چت و فروشگاه)
│   ├── bale_adapter.py         # درایور پیام‌رسان بله (پشتیبانی کامل فروشگاه و پرداخت)
│   └── rubika_adapter.py       # درایور پیام‌رسان روبیکا (پولینگ هوشمند و هندل استارت)
├── services/
│   ├── store_service.py        # هسته پردازش سفارشات، تراکنش‌ها و پارسر تحویل دوره
│   ├── web_panel.py            # پنل مدیریت و فروشگاه وب مدرن (TailwindCSS)
│   ├── ai_service.py           # روتر هوشمند هوش مصنوعی (Gemini + Nara)
│   └── media_service.py        # موتور پردازش، فشرده‌سازی و تبدیل صوت با FFmpeg
└── tests/                      # مجموعه تست‌های خودکار یکپارچه‌سازی و سرعت
```

---

## 🚀 راه‌اندازی سریع (Quick Start)

### ۱. نیازمندی‌ها
- Python 3.10 یا بالاتر
- FFmpeg (در صورت نیاز به پردازش فایل‌های صوتی)

### ۲. نصب وابستگی‌ها
```bash
# کلون کردن ریپازیتوری
git clone https://github.com/corvtte/UNFINIT.git
cd UNFINIT

# ایجاد و فعال‌سازی محیط مجازی
python -m venv .venv
source .venv/bin/activate  # در ویندوز: .venv\Scripts\activate

# نصب پکیج‌ها
pip install -r requirements.txt
```

### ۳. اجرای برنامه
```bash
python app.py
```
سپس پنل وب در آدرس `http://localhost:7860` در دسترس خواهد بود.

---

## 🧪 اجرای آزمون‌ها (Testing)

پروژه دارای مجموعه تست‌های کامل بدون وابستگی خارجی (Mock Fast Suite) است:

```bash
python -m unittest tests/test_v25_7_0_fast.py tests/test_v25_7_1_fast.py tests/test_v25_7_2_fast.py tests/test_v25_7_3_fast.py tests/test_v25_7_4_fast.py tests/test_v25_7_5_fast.py
```

تمام ۴۵ تست به صورت ۱۰۰٪ پاس می‌شوند.

---

## 📄 لایسنس
این پروژه تحت مجوز MIT منتشر شده است.
