import re

def fix_tg():
    with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # Regex replacing the async with sess.get block
    pattern = re.compile(r'async with sess\.get\(url, timeout=aiohttp\.ClientTimeout\(total=240\)\) as resp:.*?return', re.DOTALL)
    
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
    # Wait, the pattern match will consume TOO MUCH if there are multiple `return` statements!
    # Let's match from `async with sess.get` up to `if not target_path.exists() or target_path.stat().st_size == 0:`
    pattern2 = re.compile(r'(async with sess\.get\(url, timeout=aiohttp\.ClientTimeout\(total=240\)\) as resp:.*?)(                if not target_path\.exists\(\) or target_path\.stat\(\)\.st_size == 0:)', re.DOTALL)
    
    match = pattern2.search(text)
    if match:
        text = text.replace(match.group(1), new_loop + "\n\n")
        print("Replaced TG loop safely")
    else:
        print("Not matched")

    with open('platforms/telegram_adapter.py', 'w', encoding='utf-8') as f:
        f.write(text)

fix_tg()
