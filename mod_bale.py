import re

def modify_bale_adapter():
    with open('platforms/bale_adapter.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Add "تغییر فرمت" button to Bale audio menu
    find_str_1 = '''        [
            {"text": "✂️ برش فایل صوتی", "callback_data": f"bmeta:trim:{drop_id}"},
            {"text": "🧠 دستیار هوش مصنوعی", "callback_data": f"bmeta:ai_transcribe:{drop_id}"}
        ],'''
    replace_str_1 = '''        [
            {"text": "✂️ برش فایل صوتی", "callback_data": f"bmeta:trim:{drop_id}"},
            {"text": "🧠 دستیار هوش مصنوعی", "callback_data": f"bmeta:ai_transcribe:{drop_id}"}
        ],
        [
            {"text": "🔄 تغییر فرمت", "callback_data": f"bmeta:format_menu:{drop_id}"}
        ],'''

    if find_str_1 in text:
        text = text.replace(find_str_1, replace_str_1)
        print("Replaced Bale audio menu.")
    else:
        print("Could not find Bale audio menu injection point.")

    # 2. Add handler logic
    find_str_2 = '''            elif action == "audio_specs":
                await ensure_bale_binary()'''
    
    replace_str_2 = '''            elif action == "format_menu":
                rows = [
                    [
                        {"text": "تبدیل به MP3 (استاندارد)", "callback_data": f"bmeta:fmt_mp3:{drop_id}"},
                        {"text": "تبدیل به OGG (ویس)", "callback_data": f"bmeta:fmt_ogg:{drop_id}"}
                    ],
                    [
                        {"text": "تبدیل به M4A (آیفون)", "callback_data": f"bmeta:fmt_m4a:{drop_id}"},
                        {"text": "تبدیل به WAV", "callback_data": f"bmeta:fmt_wav:{drop_id}"}
                    ],
                    [
                        {"text": "🔙 بازگشت به منوی اصلی", "callback_data": f"bmeta:refresh:{drop_id}"}
                    ]
                ]
                await bale.edit_message_reply_markup(chat_id, msg_id, {"inline_keyboard": rows})

            elif action.startswith("fmt_"):
                target_fmt = action.split("_")[1]
                status_msg = await bale.send_message(chat_id, f"⏳ <b>در حال پردازش و تبدیل فرمت فایل به {target_fmt.upper()}...</b>")
                await ensure_bale_binary()
                try:
                    ok, final_audio = MediaService.convert_audio_format(drop["working_path"], target_fmt)
                    if ok and final_audio.exists():
                        await bale.edit_message_text(chat_id, status_msg["message_id"], f"✅ <b>تبدیل فرمت به {target_fmt.upper()} با موفقیت انجام شد. در حال ارسال نسخه جدید...</b>")
                        title = drop.get("api_meta", {}).get("title") or "Unknown"
                        artist = drop.get("api_meta", {}).get("artist") or "Unknown"
                        duration = drop.get("api_meta", {}).get("duration_sec") or 0
                        thumb_p = drop.get("thumb_path")
                        
                        sent_audio = await bale.send_audio(
                            chat_id,
                            final_audio,
                            title=title,
                            performer=artist,
                            duration=duration,
                            thumb=thumb_p,
                            caption=f"🎧 <b>فایل صوتی تبدیل‌شده ({target_fmt.upper()}):</b>\\n📁 <code>{final_audio.name}</code>\\n🎤 خواننده: <b>{artist}</b>\\n⏳ مدت زمان: <code>{duration} ثانیه</code>"
                        )
                        new_drop_id = __import__('uuid').uuid4().hex[:8]
                        new_audio_id = sent_audio.get("message_id")
                        new_data = MediaService.register_incoming_message_meta(
                            new_drop_id, "bale", chat_id, str(new_audio_id), final_audio.name, final_audio.stat().st_size,
                            media_type="audio", api_meta={"filename": final_audio.name, "duration_sec": duration, "title": title, "artist": artist}
                        )
                        new_data["working_path"] = str(final_audio)
                        new_data["is_downloaded_locally"] = True
                        if thumb_p: new_data["thumb_path"] = thumb_p
                        
                        from core.formatters import TelegramFormatter
                        new_card = TelegramFormatter.format_light_card(new_data)
                        new_kb = build_bale_media_keyboard(new_drop_id, new_data)
                        c_sent = await bale.send_message(chat_id, new_card, reply_markup=new_kb)
                        new_data["card_msg_id"] = c_sent.get("message_id")
                        await bale.delete_message(chat_id, status_msg["message_id"])
                    else:
                        await bale.edit_message_text(chat_id, status_msg["message_id"], "❌ خطا در عملیات تبدیل فرمت فایل.")
                except Exception as e_fmt:
                    logger.error(f"Format conversion error: {e_fmt}")
                    await bale.edit_message_text(chat_id, status_msg["message_id"], f"❌ خطای سیستمی: {e_fmt}")

            elif action == "audio_specs":
                await ensure_bale_binary()'''
                
    if find_str_2 in text:
        text = text.replace(find_str_2, replace_str_2)
        print("Replaced Bale action handlers.")
    else:
        print("Could not find Bale action injection point.")

    with open('platforms/bale_adapter.py', 'w', encoding='utf-8') as f:
        f.write(text)

modify_bale_adapter()
