import re

with open('platforms/bale_adapter.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_dispatch = r'# 1\. ارسال نسخه بومی صوت در صورت وجود.*?(?=# ۴\. اگر هیچ‌کدام نبود)'

new_dispatch = '''# ۱. ارسال ویدیو (در صورت وجود)
                                            if video_url:
                                                if not is_vip:
                                                    bale_msg = (
                                                        caption + "\\n\\n"
                                                        "💎 <b>توجه: این محتوا حاوی فایل تصویری و ویدیویی می‌باشد.</b>\\n\\n"
                                                        "جهت دریافت مستقیم و مشاهده نیتیو این فایل تصویری در <b>باشگاه پریمیوم</b> عضو شوید.\\n\\n"
                                                    )
                                                    try: await bale.edit_message_text(chat_id, wait_msg_id, bale_msg, reply_markup={"inline_keyboard": vip_kb})
                                                    except Exception: await bale.send_message(chat_id, bale_msg, reply_markup={"inline_keyboard": vip_kb})
                                                    continue
                                                else:
                                                    from core.database import db_get_cached_file_id, db_set_cached_file_id
                                                    file_key = f"sign_video_{abs(hash(video_url))}"
                                                    cached_vid_fid = await db_get_cached_file_id(file_key, "bale")
                                                    if cached_vid_fid:
                                                        try:
                                                            await bale.send_video(
                                                                chat_id,
                                                                video_file_id=cached_vid_fid,
                                                                caption=caption,
                                                                reply_markup={"inline_keyboard": vip_kb}
                                                            )
                                                            try: await bale.delete_message(chat_id, wait_msg_id)
                                                            except Exception: pass
                                                            continue
                                                        except Exception as e_cached_v:
                                                            logger.warning(f"[bale_sign] Failed sending cached video file_id: {e_cached_v}")

                                                    try:
                                                        await bale.edit_message_text(
                                                            chat_id, wait_msg_id,
                                                            f"⏳ <b>در حال دانلود مستقیم و آماده‌سازی فایل تصویری...</b>\\n\\n"
                                                            f"✨ <b>{escape(sign.get('title', ''))}</b>\\n"
                                                            f"<i>این فرآیند ممکن است چند دقیقه زمان ببرد. لطفاً شکیبا باشید...</i>"
                                                        )
                                                    except Exception: pass

                                                    target_path = None
                                                    try:
                                                        target_path = await SignService.ensure_video_downloaded(sign, reader_tag=reader_tag)
                                                    except Exception as e_dl_v:
                                                        logger.warning(f"[bale_sign] ensure_video_downloaded failed: {e_dl_v}")

                                                    if target_path and target_path.exists():
                                                        try:
                                                            file_name = f"UNFINIT_VIDEO_{uuid.uuid4().hex[:8]}.mp4"
                                                            sent_v = await bale.send_video(
                                                                chat_id,
                                                                video_path=str(target_path),
                                                                caption=caption,
                                                                reply_markup={"inline_keyboard": vip_kb},
                                                                file_name=file_name
                                                            )
                                                            if sent_v and sent_v.get("file_id"):
                                                                await db_set_cached_file_id(file_key, "bale", sent_v["file_id"], "video")
                                                            try: await bale.delete_message(chat_id, wait_msg_id)
                                                            except Exception: pass
                                                            continue
                                                        except Exception as e_send_v:
                                                            logger.warning(f"[bale_sign] reply_video local failed: {e_send_v}")

                                            # ۲. ارسال صوت (اگر ویدیو نبود)
                                            elif audio_url and not (".mp4" in audio_url.lower()):
                                                local_audio_path = None
                                                try:
                                                    local_audio_path = await SignService.ensure_audio_downloaded(sign, reader_tag=reader_tag)
                                                except Exception as e_dl:
                                                    logger.warning(f"[bale_sign] ensure_audio_downloaded failed: {e_dl}")

                                                perf_title = f"@{reader_tag.lstrip('@')}" if reader_tag else None
                                                if local_audio_path and local_audio_path.exists():
                                                    try:
                                                        file_name = f"UNFINIT_{uuid.uuid4().hex[:8]}.mp3"
                                                        sent = await bale.send_audio(
                                                            chat_id,
                                                            audio_path=str(local_audio_path),
                                                            caption=caption,
                                                            reply_markup={"inline_keyboard": vip_kb},
                                                            file_name=file_name,
                                                            performer=perf_title,
                                                            title=sign.get("title", "نشانه امروز من")
                                                        )
                                                        try: await bale.delete_message(chat_id, wait_msg_id)
                                                        except Exception: pass
                                                        continue
                                                    except Exception as ex_snd:
                                                        logger.warning(f"[bale_sign] send_audio local failed: {ex_snd}")

                                            '''

text = re.sub(old_dispatch, new_dispatch, text, flags=re.DOTALL)
with open('platforms/bale_adapter.py', 'w', encoding='utf-8') as f:
    f.write(text)
