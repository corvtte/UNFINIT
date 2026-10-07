import time

def fix_tg():
    with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(lines):
        if 'async with sess.get(url, timeout=aiohttp.ClientTimeout(total=240)) as resp:' in line:
            start_idx = i
        if start_idx != -1 and 'if not target_path.exists() or target_path.stat().st_size == 0:' in line:
            end_idx = i
            break

    if start_idx != -1 and end_idx != -1:
        new_lines = [
            '                    async with sess.get(url, timeout=aiohttp.ClientTimeout(total=3600, connect=30)) as resp:\n',
            '                        if resp.status == 200:\n',
            "                            total_size = int(resp.headers.get('content-length', 0))\n",
            '                            downloaded = 0\n',
            '                            last_prog_text = ""\n',
            '                            import time\n',
            '                            last_vid_upd = 0\n',
            '                            with open(target_path, "wb") as f_out:\n',
            '                                async for chunk in resp.content.iter_chunked(128 * 1024):\n',
            '                                    f_out.write(chunk)\n',
            '                                    downloaded += len(chunk)\n',
            '                                    if total_size > 0:\n',
            '                                        pct = (downloaded / total_size) * 100\n',
            '                                        now = time.time()\n',
            '                                        if now - last_vid_upd > 3.0:\n',
            '                                            last_vid_upd = now\n',
            '                                            bar_length = 10\n',
            '                                            filled = int(bar_length * pct // 100)\n',
            '                                            bar = "█" * filled + "░" * (bar_length - filled)\n',
            '                                            prog_text = f"⏳ <b>در حال دریافت فایل درخواستی شما از سرور...</b>\\n\\n✨ <b>{escape(ep.get(\'title\', \'\'))}</b>\\n\\n⬇️ <b>پیشرفت:</b> <code>[{bar}] {pct:.1f}%</code>"\n',
            '                                            if prog_text != last_prog_text:\n',
            '                                                last_prog_text = prog_text\n',
            '                                                try: await status_msg.edit_text(prog_text, parse_mode=enums.ParseMode.HTML)\n',
            '                                                except Exception: pass\n',
            '                        else:\n',
            '                            await status_msg.edit_text("❌ خطا در دریافت فایل از سرور. ممکن است لینک منقضی شده باشد.")\n',
            '                            return\n\n'
        ]
        lines[start_idx:end_idx] = new_lines

    # Now for the id3
    start_idx = -1
    for i, line in enumerate(lines):
        if 'if media_type == "audio":' in line and 'reader_tag = await get_system_setting("sign_reader_tag", "abasmanesh365")' in lines[i+1]:
            start_idx = i
            break

    if start_idx != -1:
        new_lines = [
            '                if media_type == "audio":\n',
            '                    reader_tag = await get_system_setting("sign_reader_tag", "abasmanesh365")\n',
            '                    perf_val = f"@{reader_tag.lstrip(\'@\')}" if reader_tag else None\n',
            '                    try:\n',
            '                        from core.media_service import modify_id3_tags\n',
            '                        await status_msg.edit_text("⏳ <b>در حال پاکسازی متادیتا و تنظیمات نهایی فایل...</b>", parse_mode=enums.ParseMode.HTML)\n',
            '                        modify_id3_tags(\n',
            '                            target_path,\n',
            '                            {\n',
            '                                "title": ep.get("title", "فایل صوتی"),\n',
            '                                "artist": perf_val,\n',
            '                                "album": perf_val\n',
            '                            },\n',
            '                            remove_cover=True\n',
            '                        )\n',
            '                    except Exception as e_meta:\n',
            '                        import logging\n',
            '                        logging.getLogger().error(f"Failed to modify ID3 tags for VIP tg download: {e_meta}")\n',
            '                    await status_msg.edit_text("⏳ <b>در حال ارسال فایل به تلگرام...</b>\\n\\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.", parse_mode=enums.ParseMode.HTML)\n',
            '                    sent = await client.send_audio(\n'
        ]
        lines[start_idx:start_idx+4] = new_lines

    # Replace video upload message
    for i, line in enumerate(lines):
        if 'else:' in line and 'sent = await client.send_video(' in lines[i+1]:
            lines[i+1] = '                    await status_msg.edit_text("⏳ <b>در حال ارسال ویدیو به تلگرام...</b>\\n\\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.", parse_mode=enums.ParseMode.HTML)\n                    sent = await client.send_video(\n'
            break

    with open('platforms/telegram_adapter.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)

def fix_bale():
    with open('platforms/bale_adapter.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(lines):
        if 'async with sess.get(url, timeout=aiohttp.ClientTimeout(total=240)) as resp:' in line:
            start_idx = i
        if start_idx != -1 and 'if not target_path.exists() or target_path.stat().st_size == 0:' in line:
            end_idx = i
            break

    if start_idx != -1 and end_idx != -1:
        new_lines = [
            '                                                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=3600, connect=30)) as resp:\n',
            '                                                    if resp.status == 200:\n',
            "                                                        total_size = int(resp.headers.get('content-length', 0))\n",
            '                                                        downloaded = 0\n',
            '                                                        last_prog_text = ""\n',
            '                                                        import time\n',
            '                                                        last_vid_upd = 0\n',
            '                                                        with open(target_path, "wb") as f_out:\n',
            '                                                            async for chunk in resp.content.iter_chunked(128 * 1024):\n',
            '                                                                f_out.write(chunk)\n',
            '                                                                downloaded += len(chunk)\n',
            '                                                                if total_size > 0:\n',
            '                                                                    pct = (downloaded / total_size) * 100\n',
            '                                                                    now = time.time()\n',
            '                                                                    if now - last_vid_upd > 3.0:\n',
            '                                                                        last_vid_upd = now\n',
            '                                                                        bar_length = 10\n',
            '                                                                        filled = int(bar_length * pct // 100)\n',
            '                                                                        bar = "█" * filled + "░" * (bar_length - filled)\n',
            '                                                                        prog_text = f"⏳ <b>در حال دریافت فایل درخواستی شما از سرور...</b>\\n\\n✨ <b>{escape(ep.get(\'title\', \'\'))}</b>\\n\\n⬇️ <b>پیشرفت:</b> <code>[{bar}] {pct:.1f}%</code>"\n',
            '                                                                        if prog_text != last_prog_text:\n',
            '                                                                            last_prog_text = prog_text\n',
            '                                                                            try: await bale.edit_message_text(chat_id, status_msg.id, prog_text)\n',
            '                                                                            except Exception: pass\n',
            '                                                    else:\n',
            '                                                        await bale.edit_message_text(chat_id, status_msg.id, "❌ خطا در دریافت فایل از سرور. ممکن است لینک منقضی شده باشد.")\n',
            '                                                        return\n\n'
        ]
        lines[start_idx:end_idx] = new_lines

    start_idx = -1
    for i, line in enumerate(lines):
        if 'if media_type == "audio":' in line and 'reader_tag = await get_system_setting("sign_reader_tag", "abasmanesh365")' in lines[i+1]:
            start_idx = i
            break

    if start_idx != -1:
        new_lines = [
            '                                if media_type == "audio":\n',
            '                                    reader_tag = await get_system_setting("sign_reader_tag", "abasmanesh365")\n',
            '                                    perf_val = f"@{reader_tag.lstrip(\'@\')}" if reader_tag else None\n',
            '                                    try:\n',
            '                                        from core.media_service import modify_id3_tags\n',
            '                                        await bale.edit_message_text(chat_id, status_msg.id, "⏳ <b>در حال پاکسازی متادیتا و تنظیمات نهایی فایل...</b>")\n',
            '                                        modify_id3_tags(\n',
            '                                            target_path,\n',
            '                                            {\n',
            '                                                "title": ep.get("title", "فایل صوتی"),\n',
            '                                                "artist": perf_val,\n',
            '                                                "album": perf_val\n',
            '                                            },\n',
            '                                            remove_cover=True\n',
            '                                        )\n',
            '                                    except Exception as e_meta:\n',
            '                                        import logging\n',
            '                                        logging.getLogger().error(f"Failed to modify ID3 tags for VIP bale download: {e_meta}")\n',
            '                                    await bale.edit_message_text(chat_id, status_msg.id, "⏳ <b>در حال ارسال فایل به بله...</b>\\n\\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.")\n',
            '                                    sent = await bale.send_audio(\n'
        ]
        lines[start_idx:start_idx+4] = new_lines

    for i, line in enumerate(lines):
        if 'else:' in line and 'sent = await bale.send_video(' in lines[i+1]:
            lines[i+1] = '                                    await bale.edit_message_text(chat_id, status_msg.id, "⏳ <b>در حال ارسال ویدیو به بله...</b>\\n\\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.")\n                                    sent = await bale.send_video(\n'
            break

    with open('platforms/bale_adapter.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)

fix_tg()
fix_bale()
