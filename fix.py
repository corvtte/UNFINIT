import re

with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_dispatch = r'# 1\. ارسال نسخه بومی صوت در صورت وجود.*?(?=# ۴\. اگر هیچ‌کدام نبود)'

new_dispatch = '''# ۱. ارسال ویدیو (در صورت وجود)
                if video_url:
                    if not is_vip:
                        vip_prompt = (
                            caption + "\\n\\n"
                            "💎 <b>توجه: این محتوا حاوی فایل تصویری و ویدیویی می‌باشد.</b>\\n\\n"
                            "جهت دریافت مستقیم و مشاهده نیتیو این فایل تصویری و صدها فایل دیگر در <b>باشگاه پریمیوم</b> عضو شوید.\\n\\n"
                            "شما می‌توانید با تهیه اشتراک ۳۰ روزه باشگاه، به صورت نامحدود از امکانات ویژه ربات استفاده کنید:"
                        )
                        try:
                            await wait_msg.edit_text(vip_prompt, reply_markup=vip_kb, parse_mode=enums.ParseMode.HTML)
                        except Exception:
                            await message.reply_text(vip_prompt, reply_markup=vip_kb, parse_mode=enums.ParseMode.HTML)
                        return
                    else:
                        from core.database import db_get_cached_file_id, db_set_cached_file_id
                        file_key = f"sign_video_{abs(hash(video_url))}"
                        cached_vid_fid = await db_get_cached_file_id(file_key, "telegram")
                        if cached_vid_fid:
                            try:
                                await message.reply_video(
                                    video=cached_vid_fid,
                                    caption=caption,
                                    reply_markup=vip_kb,
                                    parse_mode=enums.ParseMode.HTML
                                )
                                try: await wait_msg.delete()
                                except Exception: pass
                                return
                            except Exception as e_cached_v:
                                logger.warning(f"[tg_sign] Failed sending cached video file_id: {e_cached_v}")

                        try:
                            await wait_msg.edit_text(
                                f"⏳ <b>در حال دانلود مستقیم و آماده‌سازی فایل تصویری...</b>\\n\\n"
                                f"✨ <b>{escape(sign.get('title', ''))}</b>\\n"
                                f"<i>این فرآیند ممکن است چند دقیقه زمان ببرد. لطفاً شکیبا باشید...</i>",
                                parse_mode=enums.ParseMode.HTML
                            )
                        except Exception:
                            pass

                        target_path = None
                        try:
                            target_path = await SignService.ensure_video_downloaded(sign, reader_tag=reader_tag)
                        except Exception as e_dl_v:
                            logger.warning(f"[tg_sign] ensure_video_downloaded failed: {e_dl_v}")

                        if target_path and target_path.exists():
                            try:
                                sent_v = await message.reply_video(
                                    video=str(target_path),
                                    caption=caption,
                                    reply_markup=vip_kb,
                                    parse_mode=enums.ParseMode.HTML
                                )
                                if sent_v and sent_v.video:
                                    await db_set_cached_file_id(file_key, "telegram", sent_v.video.file_id, "video")
                                try: await wait_msg.delete()
                                except Exception: pass
                                return
                            except Exception as e_send_v:
                                logger.warning(f"[tg_sign] reply_video local failed: {e_send_v}")

                # ۲. ارسال صوت (اگر ویدیو نبود)
                elif audio_url and not (".mp4" in audio_url.lower()):
                    local_audio_path = None
                    try:
                        local_audio_path = await SignService.ensure_audio_downloaded(sign, reader_tag=reader_tag)
                    except Exception as e_dl:
                        logger.warning(f"[tg_sign] ensure_audio_downloaded failed: {e_dl}")

                    perf_title = f"@{reader_tag.lstrip('@')}" if reader_tag else None
                    if local_audio_path and local_audio_path.exists():
                        try:
                            await message.reply_audio(
                                audio=str(local_audio_path),
                                caption=caption,
                                title=sign.get("title", "نشانه امروز من"),
                                performer=perf_title,
                                reply_markup=vip_kb,
                                parse_mode=enums.ParseMode.HTML
                            )
                            try: await wait_msg.delete()
                            except Exception: pass
                            return
                        except Exception as e_send_loc:
                            logger.warning(f"[tg_sign] reply_audio local failed: {e_send_loc}")

                '''

text = re.sub(old_dispatch, new_dispatch, text, flags=re.DOTALL)
with open('platforms/telegram_adapter.py', 'w', encoding='utf-8') as f:
    f.write(text)
