# -*- coding: utf-8 -*-
"""
ماژول پل سازگاری متادیتا و تگ‌گذاری (Metadata Tagger Compatibility Bridge)
این ماژول جهت دسترسی یکپارچه به کلیه توابع تگ‌گذاری، استخراج کاور و پاکسازی متادیتا
از طریق بسته core در نگارش v0.4.7 ایجاد شده است.
"""
from media.tagger import (
    modify_id3_tags,
    extract_cover_image,
    generate_video_thumbnail,
    strip_all_metadata,
    inspect_cover_details,
    copy_all_id3_tags,
    build_native_id3v23,
    strip_existing_id3
)
