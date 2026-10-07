import re

def fix_bale():
    with open('platforms/bale_adapter.py', 'r', encoding='utf-8') as f:
        text = f.read()

    pattern2 = re.compile(r'(async with sess\.get\(url, timeout=aiohttp\.ClientTimeout\(total=240\)\) as resp:.*?)(                                if not target_path\.exists\(\) or target_path\.stat\(\)\.st_size == 0:)', re.DOTALL)
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
                                                            try: await bale.edit_message_text(chat_id, status_msg.id, prog_text)
                                                            except Exception: pass
                                    else:
                                        await bale.edit_message_text(chat_id, status_msg.id, "❌ خطا در دریافت فایل از سرور. ممکن است لینک منقضی شده باشد.")
                                        return\n\n'''
    match = pattern2.search(text)
    if match:
        text = text.replace(match.group(1), new_loop)
        print('Replaced Bale loop')
    else:
        print('Not matched bale loop')

    id3_pattern = re.compile(r'(if media_type == "audio":\s+reader_tag = await get_system_setting\("sign_reader_tag", "abasmanesh365"\)\s+perf_val = f"@{reader_tag\.lstrip\(\'@\'\)}" if reader_tag else None)', re.DOTALL)
    id3_inject = '''\\1
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
                                    await bale.edit_message_text(chat_id, status_msg.id, "⏳ <b>در حال ارسال فایل به بله...</b>\\n\\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.")
                                except Exception as e_meta:
                                    import logging
                                    logging.getLogger().error(f"Failed to modify ID3 tags for VIP bale download: {e_meta}")
'''
    if id3_pattern.search(text):
        text = id3_pattern.sub(id3_inject, text)
        print('Replaced Bale id3')
    else:
        print('Bale id3 not found')

    video_inject = '''                                else:
                                    await bale.edit_message_text(chat_id, status_msg.id, "⏳ <b>در حال ارسال ویدیو به بله...</b>\\n\\nاین مرحله بسته به حجم فایل ممکن است کمی زمان‌بر باشد، لطفاً صبور باشید.")
                                    sent = await bale.send_video('''
    text = text.replace('                                else:\n                                    sent = await bale.send_video(', video_inject)

    with open('platforms/bale_adapter.py', 'w', encoding='utf-8') as f:
        f.write(text)

fix_bale()
