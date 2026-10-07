import re

def fix_tg():
    with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
        tg = f.read()
    
    # 1. Update the download loop and timeout
    tg_loop_pattern = r'''                    async with sess\.get\(url, timeout=aiohttp\.ClientTimeout\(total=240\)\) as resp:
                        if resp\.status == 200:
                            total_size = int\(resp\.headers\.get\('content-length', 0\)\)
                            downloaded = 0
                            last_prog_text = ""
                            with open\(target_path, "wb"\) as f_out:
                                async for chunk in resp\.content\.iter_chunked\(128 \* 1024\):
                                    f_out\.write\(chunk\)
                                    downloaded \+= len\(chunk\)
                                    if total_size > 0:
                                        pct = \(downloaded / total_size\) \* 100
                                        if int\(pct\) % 5 == 0:
                                            prog_text = f"⏳ <b>در حال دریافت فایل درخواستی شما از سرور\.\.\.</b>\n\n✨ <b>\{escape\(ep\.get\('title', ''\)\)\}</b>\n\n⬇️ <b>پیشرفت:</b> <code>\{pct:\.1f\}%</code>"
                                            if prog_text != last_prog_text:
                                                last_prog_text = prog_text
                                                try: await status_msg\.edit_text\(prog_text, parse_mode=enums\.ParseMode\.HTML\)
                                                except Exception: pass
                        else:
                            await status_msg\.edit_text\("❌ خطا در دریافت فایل از سرور مرجع\."\)
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
    
    if re.search(tg_loop_pattern, tg):
        tg = re.sub(tg_loop_pattern, tg_new_loop.replace('\\', '\\\\'), tg)
    else:
        # try simple replace
        tg = tg.replace(tg_loop_pattern.replace('\\', ''), tg_new_loop)

    # 2. Update ID3 modifying
    tg_id3_pattern = r'''                if media_type == "audio":
                    reader_tag = await get_system_setting\("sign_reader_tag", "abasmanesh365"\)
                    perf_val = f"@{reader_tag\.lstrip\('@'\)}" if reader_tag else None
                    sent = await client\.send_audio\('''
                    
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
                    
    if re.search(tg_id3_pattern, tg):
        tg = re.sub(tg_id3_pattern, tg_new_id3.replace('\\', '\\\\'), tg)
    else:
        tg = tg.replace(tg_id3_pattern.replace('\\', ''), tg_new_id3)

    # 3. Update Video send
    tg = tg.replace(
r'''                else:
                    sent = await client.send_video(''', 
r'''                else:
                    await status_msg.edit_text("⏳ <b>در حال ارسال ویدیو به تلگرام...</b>\n\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.", parse_mode=enums.ParseMode.HTML)
                    sent = await client.send_video(''')

    with open('platforms/telegram_adapter.py', 'w', encoding='utf-8') as f:
        f.write(tg)

def fix_bale():
    with open('platforms/bale_adapter.py', 'r', encoding='utf-8') as f:
        bale = f.read()

    bale_loop_pattern = r'''                                                async with sess\.get\(url, timeout=aiohttp\.ClientTimeout\(total=240\)\) as resp:
                                                    if resp\.status == 200:
                                                        with open\(target_path, "wb"\) as f_out:
                                                            async for chunk in resp\.content\.iter_chunked\(128 \* 1024\):
                                                                f_out\.write\(chunk\)
                                                    else:
                                                        await bale\.send_message\(chat_id, "❌ خطا در دریافت فایل از سرور نامعتبر\."\)
                                                        continue'''

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
                                                        await bale.send_message(chat_id, "❌ خطا در دریافت فایل از سرور نامعتبر.")
                                                        continue'''
    
    if re.search(bale_loop_pattern, bale):
        bale = re.sub(bale_loop_pattern, bale_new_loop.replace('\\', '\\\\'), bale)
    else:
        bale = bale.replace(bale_loop_pattern.replace('\\', ''), bale_new_loop)

    bale_id3_pattern = r'''                                            if media_type == "audio":
                                                reader_tag = await get_system_setting\("sign_reader_tag", "abasmanesh365"\)
                                                perf_val = f"@{reader_tag\.lstrip\('@'\)}" if reader_tag else None
                                                sent = await bale\.send_audio\('''

    bale_new_id3 = r'''                                            if media_type == "audio":
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

    if re.search(bale_id3_pattern, bale):
        bale = re.sub(bale_id3_pattern, bale_new_id3.replace('\\', '\\\\'), bale)
    else:
        bale = bale.replace(bale_id3_pattern.replace('\\', ''), bale_new_id3)

    bale = bale.replace(
r'''                                            else:
                                                sent = await bale.send_video(''',
r'''                                            else:
                                                await bale.edit_message_text(chat_id, status_msg.id, "⏳ <b>در حال ارسال ویدیو به بله...</b>\n\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.")
                                                sent = await bale.send_video(''')

    with open('platforms/bale_adapter.py', 'w', encoding='utf-8') as f:
        f.write(bale)

fix_tg()
fix_bale()
