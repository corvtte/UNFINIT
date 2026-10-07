import re

def modify_telegram_adapter():
    with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Add "تغییر فرمت" button to the audio menu
    # The audio menu has:
    # InlineKeyboardButton("🧠 دستیار هوش مصنوعی", callback_data=f"smeta:ai_transcribe:{drop_id}")
    # We can add it there or to a new row.
    
    find_str_1 = '''                InlineKeyboardButton("✂️ برش فایل صوتی", callback_data=f"smeta:trim:{drop_id}"),
                InlineKeyboardButton("🧠 دستیار هوش مصنوعی", callback_data=f"smeta:ai_transcribe:{drop_id}")
            ],'''
    replace_str_1 = '''                InlineKeyboardButton("✂️ برش فایل صوتی", callback_data=f"smeta:trim:{drop_id}"),
                InlineKeyboardButton("🧠 دستیار هوش مصنوعی", callback_data=f"smeta:ai_transcribe:{drop_id}")
            ],
            [
                InlineKeyboardButton("🔄 تغییر فرمت", callback_data=f"smeta:format_menu:{drop_id}")
            ],'''
            
    if find_str_1 in text:
        text = text.replace(find_str_1, replace_str_1)
        print("Replaced audio menu.")
    else:
        print("Could not find audio menu injection point.")

    # 2. Handle smeta:format_menu:{drop_id} in handle_smeta_callbacks
    # Look for: elif action == "audio_specs":
    
    find_str_2 = '''            elif action == "audio_specs":
                await ensure_binary()'''
    
    replace_str_2 = '''            elif action == "format_menu":
                rows = [
                    [
                        InlineKeyboardButton("تبدیل به MP3 (استاندارد)", callback_data=f"smeta:fmt_mp3:{drop_id}"),
                        InlineKeyboardButton("تبدیل به OGG (ویس)", callback_data=f"smeta:fmt_ogg:{drop_id}")
                    ],
                    [
                        InlineKeyboardButton("تبدیل به M4A (آیفون)", callback_data=f"smeta:fmt_m4a:{drop_id}"),
                        InlineKeyboardButton("تبدیل به WAV", callback_data=f"smeta:fmt_wav:{drop_id}")
                    ],
                    [
                        InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data=f"smeta:refresh:{drop_id}")
                    ]
                ]
                await callback_query.message.edit_reply_markup(InlineKeyboardMarkup(rows))

            elif action.startswith("fmt_"):
                target_fmt = action.split("_")[1] # mp3, ogg, m4a, wav
                status_msg = await callback_query.message.reply_text(f"⏳ <b>در حال پردازش و تبدیل فرمت فایل به {target_fmt.upper()}...</b>", parse_mode=enums.ParseMode.HTML)
                await ensure_binary()
                try:
                    ok, final_audio = MediaService.convert_audio_format(c_data["working_path"], target_fmt)
                    if ok and final_audio.exists():
                        await status_msg.edit_text(f"✅ <b>تبدیل فرمت به {target_fmt.upper()} با موفقیت انجام شد. در حال ارسال نسخه جدید...</b>", parse_mode=enums.ParseMode.HTML)
                        title = c_data.get("api_meta", {}).get("title") or "Unknown"
                        artist = c_data.get("api_meta", {}).get("artist") or "Unknown"
                        duration = c_data.get("api_meta", {}).get("duration_sec") or 0
                        thumb_p = c_data.get("thumb_path")
                        
                        sent_audio = await self.send_audio(
                            user_id,
                            final_audio,
                            title=title,
                            performer=artist,
                            duration=duration,
                            thumb=thumb_p,
                            caption=f"🎧 <b>فایل صوتی تبدیل‌شده ({target_fmt.upper()}):</b>\\n📁 <code>{escape(final_audio.name)}</code>\\n🎤 خواننده: <b>{escape(artist)}</b>\\n⏳ مدت زمان: <code>{duration} ثانیه</code>"
                        )
                        new_drop_id = uuid.uuid4().hex[:8]
                        new_audio_id = sent_audio.get("message_id")
                        new_data = MediaService.register_incoming_message_meta(
                            new_drop_id, "telegram", user_id, str(new_audio_id), final_audio.name, final_audio.stat().st_size,
                            media_type="audio", api_meta={"filename": final_audio.name, "duration_sec": duration, "title": title, "artist": artist}
                        )
                        new_data["working_path"] = str(final_audio)
                        new_data["is_downloaded_locally"] = True
                        if thumb_p: new_data["thumb_path"] = thumb_p
                        
                        new_card = TelegramFormatter.format_light_card(new_data)
                        new_kb = self.build_media_keyboard(new_drop_id, new_data)
                        c_sent = await self.send_message(user_id, new_card, reply_markup=new_kb)
                        new_data["card_msg_id"] = c_sent.get("message_id")
                        await status_msg.delete()
                    else:
                        await status_msg.edit_text("❌ خطا در عملیات تبدیل فرمت فایل.", parse_mode=enums.ParseMode.HTML)
                except Exception as e_fmt:
                    logger.error(f"Format conversion error: {e_fmt}")
                    await status_msg.edit_text(f"❌ خطای سیستمی: {e_fmt}", parse_mode=enums.ParseMode.HTML)

            elif action == "audio_specs":
                await ensure_binary()'''
                
    if find_str_2 in text:
        text = text.replace(find_str_2, replace_str_2)
        print("Replaced action handlers.")
    else:
        print("Could not find action injection point.")

    with open('platforms/telegram_adapter.py', 'w', encoding='utf-8') as f:
        f.write(text)

modify_telegram_adapter()
