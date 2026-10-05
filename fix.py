with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_loop = '''                        if resp.status == 200:
                            with open(target_path, "wb") as f_out:
                                async for chunk in resp.content.iter_chunked(128 * 1024):
                                    f_out.write(chunk)'''

new_loop = '''                        if resp.status == 200:
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
                                            prog_text = f"⏳ <b>در حال دریافت و آماده‌سازی مستقیم از سرور...</b>\\n\\n✨ <b>{escape(ep.get('title', ''))}</b>\\n\\n⬇️ <b>دریافت:</b> <code>{pct:.1f}%</code>"
                                            if prog_text != last_prog_text:
                                                last_prog_text = prog_text
                                                try: await status_msg.edit_text(prog_text, parse_mode=enums.ParseMode.HTML)
                                                except Exception: pass'''

text = text.replace(old_loop, new_loop)

old_ensure = '''                        target_path = None
                        try:
                            target_path = await SignService.ensure_video_downloaded(sign, reader_tag=reader_tag)'''

new_ensure = '''                        target_path = None
                        try:
                            last_vid_prog = ""
                            async def vid_prog(dl, tot, pct):
                                nonlocal last_vid_prog
                                if int(pct) % 5 == 0:
                                    p_txt = f"⏳ <b>در حال آماده‌سازی نشانه امروز شما...</b>\\n\\n✨ <b>{escape(sign.get('title', ''))}</b>\\n\\n⬇️ <b>پیشرفت:</b> <code>{pct:.1f}%</code>"
                                    if p_txt != last_vid_prog:
                                        last_vid_prog = p_txt
                                        try: await wait_msg.edit_text(p_txt, parse_mode=enums.ParseMode.HTML)
                                        except Exception: pass
                            
                            target_path = await SignService.ensure_video_downloaded(sign, reader_tag=reader_tag, progress_callback=vid_prog)'''

text = text.replace(old_ensure, new_ensure)

with open('platforms/telegram_adapter.py', 'w', encoding='utf-8') as f:
    f.write(text)
