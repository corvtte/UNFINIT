import re

def fix_tg():
    with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
        text = f.read()
        
    pattern = re.compile(r'async with sess\.get\(url, timeout=aiohttp\.ClientTimeout\(total=240\)\) as resp:.*?else:\s+await status_msg\.edit_text\("❌ خطا در دریافت فایل از سرور مرجع\."\)\s+return', re.DOTALL)

    new_loop = '''async with sess.get(url, timeout=aiohttp.ClientTimeout(total=3600, connect=30)) as resp:
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
                                            prog_text = f"⏳ <b>در حال دریافت فایل درخواستی شما از سرور...</b>\\n\\n✨ <b>{escape(ep.get('title', ''))}</b>\\n\\n⬇️ <b>پیشرفت:</b> <code>[{bar}] {pct:.1f}%</code>"
                                            if prog_text != last_prog_text:
                                                last_prog_text = prog_text
                                                try: await status_msg.edit_text(prog_text, parse_mode=enums.ParseMode.HTML)
                                                except Exception: pass
                        else:
                            await status_msg.edit_text("❌ خطا در دریافت فایل از سرور. ممکن است لینک منقضی شده باشد.")
                            return'''

    if pattern.search(text):
        text = pattern.sub(new_loop, text)
        print('Replaced TG loop')
    else:
        print('TG loop not found')

    id3_pattern = re.compile(r'(if media_type == "audio":\s+reader_tag = await get_system_setting\("sign_reader_tag", "abasmanesh365"\)\s+perf_val = f"@{reader_tag\.lstrip\(\'@\'\)}" if reader_tag else None)', re.DOTALL)
    id3_inject = '''\\1
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
                        # Re-calculate size and hash? No need, we just send target_path.
                        # Wait, we need to add the "Uploading" message for telegram!
                        await status_msg.edit_text("⏳ <b>در حال ارسال فایل به تلگرام...</b>\\n\\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.", parse_mode=enums.ParseMode.HTML)
                    except Exception as e_meta:
                        import logging
                        logging.getLogger().error(f"Failed to modify ID3 tags for VIP tg download: {e_meta}")
'''
    if id3_pattern.search(text):
        text = id3_pattern.sub(id3_inject, text)
        print('Replaced TG id3')
    else:
        print('TG id3 not found')

    # Add the uploading message for video too
    video_inject = '''                else:
                    await status_msg.edit_text("⏳ <b>در حال ارسال ویدیو به تلگرام...</b>\\n\\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.", parse_mode=enums.ParseMode.HTML)
                    sent = await client.send_video('''
    text = text.replace('                else:\n                    sent = await client.send_video(', video_inject)

    with open('platforms/telegram_adapter.py', 'w', encoding='utf-8') as f:
        f.write(text)

fix_tg()
