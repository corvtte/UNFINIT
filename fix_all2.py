import re

def fix():
    # Telegram
    with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
        tg = f.read()

    tg_old_loop = r'''                    async with sess.get(url, timeout=aiohttp.ClientTimeout(total=240)) as resp:
                        if resp.status == 200:
                            total_size = int(resp.headers.get('content-length', 0))
                            downloaded = 0
                            last_prog_text = ""
                            with open(target_path, "wb") as f_out:
                                async for chunk in resp.content.iter_chunked(128 * 1024):
                                    f_out.write(chunk)
                                    downloaded += len(chunk)
                                    if total_size > 0:
                                        pct = (downloaded / total_size) * 100
                                        if int(pct) % 5 == 0:
                                            prog_text = f"⏳ <b>در حال دریافت فایل درخواستی شما از سرور...</b>\n\n✨ <b>{escape(ep.get('title', ''))}</b>\n\n⬇️ <b>پیشرفت:</b> <code>{pct:.1f}%</code>"
                                            if prog_text != last_prog_text:
                                                last_prog_text = prog_text
                                                try: await status_msg.edit_text(prog_text, parse_mode=enums.ParseMode.HTML)
                                                except Exception: pass
                        else:
                            await status_msg.edit_text("❌ خطا در دریافت فایل از سرور مرجع.")
                            return'''
    
    tg_new_loop = r'''                    async with sess.get(url, timeout=aiohttp.ClientTimeout(total=3600, connect=30)) as resp:
                        if resp.status == 200:
                            total_size = int(resp.headers.get('content-length', 0))
                            downloaded = 0
                            last_prog_text = ""
                            import time
                            last_vid_upd = 0
                            with open(target_path, "wb") as f_out:
                                async for chunk in resp.content.iter_chunked(128 * 1024):
                                    f_out.write(chunk)
                                    downloaded += len(chunk)
                                    if total_size > 0:
                                        pct = (downloaded / total_size) * 100
                                        now = time.time()
                                        if now - last_vid_upd > 3.0:
                                            last_vid_upd = now
                                            bar_length = 10
                                            filled = int(bar_length * pct // 100)
                                            bar = "█" * filled + "░" * (bar_length - filled)
                                            prog_text = f"⏳ <b>در حال دریافت فایل درخواستی شما از سرور...</b>\n\n✨ <b>{escape(ep.get('title', ''))}</b>\n\n⬇️ <b>پیشرفت:</b> <code>[{bar}] {pct:.1f}%</code>"
                                            if prog_text != last_prog_text:
                                                last_prog_text = prog_text
                                                try: await status_msg.edit_text(prog_text, parse_mode=enums.ParseMode.HTML)
                                                except Exception: pass
                        else:
                            await status_msg.edit_text("❌ خطا در دریافت فایل از سرور. ممکن است لینک منقضی شده باشد.")
                            return'''
    
    if tg_old_loop in tg:
        tg = tg.replace(tg_old_loop, tg_new_loop)
    else:
        print("TG old loop not found exactly.")

    tg_old_id3 = r'''                if media_type == "audio":
                    reader_tag = await get_system_setting("sign_reader_tag", "abasmanesh365")
                    perf_val = f"@{reader_tag.lstrip('@')}" if reader_tag else None
                    sent = await client.send_audio('''

    tg_new_id3 = r'''                if media_type == "audio":
                    reader_tag = await get_system_setting("sign_reader_tag", "abasmanesh365")
                    perf_val = f"@{reader_tag.lstrip('@')}" if reader_tag else None
                    
                    try:
                        from core.media_service import modify_id3_tags
                        await status_msg.edit_text("⏳ <b>در حال پاکسازی متادیتا و تنظیمات نهایی فایل...</b>", parse_mode=enums.ParseMode.HTML)
                        modify_id3_tags(
                            target_path,
                            {
                                "title": ep.get("title", "فایل صوتی"),
                                "artist": perf_val,
                                "album": perf_val
                            },
                            remove_cover=True
                        )
                    except Exception as e_meta:
                        import logging
                        logging.getLogger().error(f"Failed to modify ID3 tags for VIP tg download: {e_meta}")
                        
                    await status_msg.edit_text("⏳ <b>در حال ارسال فایل به تلگرام...</b>\n\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.", parse_mode=enums.ParseMode.HTML)
                    sent = await client.send_audio('''
    
    tg = tg.replace(tg_old_id3, tg_new_id3)

    tg = tg.replace(
r'''                else:
                    sent = await client.send_video(''', 
r'''                else:
                    await status_msg.edit_text("⏳ <b>در حال ارسال ویدیو به تلگرام...</b>\n\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.", parse_mode=enums.ParseMode.HTML)
                    sent = await client.send_video(''')

    with open('platforms/telegram_adapter.py', 'w', encoding='utf-8') as f:
        f.write(tg)


    # Bale
    with open('platforms/bale_adapter.py', 'r', encoding='utf-8') as f:
        bale = f.read()

    bale_old_loop = r'''                                                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=240)) as resp:
                                                    if resp.status == 200:
                                                        total_size = int(resp.headers.get('content-length', 0))
                                                        downloaded = 0
                                                        last_prog_text = ""
                                                        with open(target_path, "wb") as f_out:
                                                            async for chunk in resp.content.iter_chunked(128 * 1024):
                                                                f_out.write(chunk)
                                                                downloaded += len(chunk)
                                                                if total_size > 0:
                                                                    pct = (downloaded / total_size) * 100
                                                                    if int(pct) % 5 == 0:
                                                                        prog_text = f"⏳ <b>در حال دریافت فایل درخواستی شما از سرور...</b>\n\n✨ <b>{escape(ep.get('title', ''))}</b>\n\n⬇️ <b>پیشرفت:</b> <code>{pct:.1f}%</code>"
                                                                        if prog_text != last_prog_text:
                                                                            last_prog_text = prog_text
                                                                            try: await bale.edit_message_text(chat_id, status_msg.id, prog_text)
                                                                            except Exception: pass
                                                    else:
                                                        await bale.edit_message_text(chat_id, status_msg.id, "❌ خطا در دریافت فایل از سرور مرجع.")
                                                        return'''

    bale_new_loop = r'''                                                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=3600, connect=30)) as resp:
                                                    if resp.status == 200:
                                                        total_size = int(resp.headers.get('content-length', 0))
                                                        downloaded = 0
                                                        last_prog_text = ""
                                                        import time
                                                        last_vid_upd = 0
                                                        with open(target_path, "wb") as f_out:
                                                            async for chunk in resp.content.iter_chunked(128 * 1024):
                                                                f_out.write(chunk)
                                                                downloaded += len(chunk)
                                                                if total_size > 0:
                                                                    pct = (downloaded / total_size) * 100
                                                                    now = time.time()
                                                                    if now - last_vid_upd > 3.0:
                                                                        last_vid_upd = now
                                                                        bar_length = 10
                                                                        filled = int(bar_length * pct // 100)
                                                                        bar = "█" * filled + "░" * (bar_length - filled)
                                                                        prog_text = f"⏳ <b>در حال دریافت فایل درخواستی شما از سرور...</b>\n\n✨ <b>{escape(ep.get('title', ''))}</b>\n\n⬇️ <b>پیشرفت:</b> <code>[{bar}] {pct:.1f}%</code>"
                                                                        if prog_text != last_prog_text:
                                                                            last_prog_text = prog_text
                                                                            try: await bale.edit_message_text(chat_id, status_msg.id, prog_text)
                                                                            except Exception: pass
                                                    else:
                                                        await bale.edit_message_text(chat_id, status_msg.id, "❌ خطا در دریافت فایل از سرور. ممکن است لینک منقضی شده باشد.")
                                                        return'''
    if bale_old_loop in bale:
        bale = bale.replace(bale_old_loop, bale_new_loop)
    else:
        print("Bale old loop not found exactly.")

    bale_old_id3 = r'''                                if media_type == "audio":
                                    reader_tag = await get_system_setting("sign_reader_tag", "abasmanesh365")
                                    perf_val = f"@{reader_tag.lstrip('@')}" if reader_tag else None
                                    sent = await bale.send_audio('''

    bale_new_id3 = r'''                                if media_type == "audio":
                                    reader_tag = await get_system_setting("sign_reader_tag", "abasmanesh365")
                                    perf_val = f"@{reader_tag.lstrip('@')}" if reader_tag else None
                                    
                                    try:
                                        from core.media_service import modify_id3_tags
                                        await bale.edit_message_text(chat_id, status_msg.id, "⏳ <b>در حال پاکسازی متادیتا و تنظیمات نهایی فایل...</b>")
                                        modify_id3_tags(
                                            target_path,
                                            {
                                                "title": ep.get("title", "فایل صوتی"),
                                                "artist": perf_val,
                                                "album": perf_val
                                            },
                                            remove_cover=True
                                        )
                                    except Exception as e_meta:
                                        import logging
                                        logging.getLogger().error(f"Failed to modify ID3 tags for VIP bale download: {e_meta}")
                                        
                                    await bale.edit_message_text(chat_id, status_msg.id, "⏳ <b>در حال ارسال فایل به بله...</b>\n\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.")
                                    sent = await bale.send_audio('''
    bale = bale.replace(bale_old_id3, bale_new_id3)

    bale = bale.replace(
r'''                                else:
                                    sent = await bale.send_video(''',
r'''                                else:
                                    await bale.edit_message_text(chat_id, status_msg.id, "⏳ <b>در حال ارسال ویدیو به بله...</b>\n\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.")
                                    sent = await bale.send_video(''')

    with open('platforms/bale_adapter.py', 'w', encoding='utf-8') as f:
        f.write(bale)

fix()
