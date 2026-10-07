import re

def fix():
    # Telegram
    with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
        tg = f.read()

    tg_pattern = re.compile(r'(async with sess\.get\(url, timeout=aiohttp\.ClientTimeout\(total=240\)\) as resp:\n.*?if int\(pct\) % 5 == 0:\n.*?await status_msg\.edit_text\("❌ خطا در دریافت فایل از سرور مرجع\."\)\n\s+return)', re.DOTALL)
    
    tg_new_loop = r'''async with sess.get(url, timeout=aiohttp.ClientTimeout(total=3600, connect=30)) as resp:
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
    
    match = tg_pattern.search(tg)
    if match:
        # Match groups indentation based on the start
        tg = tg[:match.start(1)] + "\n".join(["                    " + line if i > 0 else line for i, line in enumerate(tg_new_loop.split('\n'))]) + tg[match.end(1):]
    else:
        print("TG old loop not found.")

    with open('platforms/telegram_adapter.py', 'w', encoding='utf-8') as f:
        f.write(tg)


    # Bale
    with open('platforms/bale_adapter.py', 'r', encoding='utf-8') as f:
        bale = f.read()

    bale_pattern = re.compile(r'(async with sess\.get\(url, timeout=aiohttp\.ClientTimeout\(total=240\)\) as resp:\n.*?if int\(pct\) % 5 == 0:\n.*?await bale\.edit_message_text\(chat_id, status_msg\.id, "❌ خطا در دریافت فایل از سرور مرجع\."\)\n\s+return)', re.DOTALL)
    
    bale_new_loop = r'''async with sess.get(url, timeout=aiohttp.ClientTimeout(total=3600, connect=30)) as resp:
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
    
    match = bale_pattern.search(bale)
    if match:
        bale = bale[:match.start(1)] + "\n".join(["                                                " + line if i > 0 else line for i, line in enumerate(bale_new_loop.split('\n'))]).replace("                                                                                                    if resp.status == 200:", "                                                    if resp.status == 200:") + bale[match.end(1):]
    else:
        print("Bale old loop not found.")

    with open('platforms/bale_adapter.py', 'w', encoding='utf-8') as f:
        f.write(bale)

fix()
