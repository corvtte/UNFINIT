import re

def rewrite_bale():
    with open('platforms/bale_adapter.py', 'r', encoding='utf-8') as f:
        text = f.read()

    pattern = re.compile(r'(async with sess\.get\(url, timeout=aiohttp\.ClientTimeout\(total=3600, connect=30\)\) as resp:\n)(.*?)(                                if not target_path\.exists\(\) or target_path\.stat\(\)\.st_size == 0:)', re.DOTALL)

    new_block = '''                                                    if resp.status == 200:
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
                                                        return
'''
    
    match = pattern.search(text)
    if match:
        text = text.replace(match.group(2), new_block)
        
    with open('platforms/bale_adapter.py', 'w', encoding='utf-8') as f:
        f.write(text)

rewrite_bale()
