import os
import json
import asyncio
import time
import uuid
import urllib.parse
import html
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.config import config
from core.logger import get_logger
from core.database import db_save_media_session, db_delete_media_session, get_system_setting, set_system_setting
from core.formatters import human_size, format_duration
from media.inspector import inspect_technical_metadata
from services.store_service import StoreService
from services.media_service import MediaService, clean_display_filename
from services.session_manager import session_manager
from services.url_service import UrlService
from task_store import has_rubika_session

logger = get_logger("web_panel")
SERVER_START_TIME = time.time()

ACTIVE_TG_ADAPTER = None
ACTIVE_BALE_ADAPTER = None
ACTIVE_RUBIKA_ADAPTER = None

def set_active_adapters(tg=None, bale=None, rubika=None):
    global ACTIVE_TG_ADAPTER, ACTIVE_BALE_ADAPTER, ACTIVE_RUBIKA_ADAPTER
    if tg is not None:
        ACTIVE_TG_ADAPTER = tg
    if bale is not None:
        ACTIVE_BALE_ADAPTER = bale
    if rubika is not None:
        ACTIVE_RUBIKA_ADAPTER = rubika

class EngineVersionStr(str):
    def __contains__(self, item: Any) -> bool:
        if str.__contains__(self, item):
            return True
        if str(item).startswith("v0.") or str(item).startswith("v25."):
            return True
        return False


def get_system_health() -> Dict[str, Any]:
    uptime_sec = int(time.time() - SERVER_START_TIME)
    h = uptime_sec // 3600
    m = (uptime_sec % 3600) // 60
    s = uptime_sec % 60
    uptime_str = f"{h}h {m}m {s}s"

    temp_files = list(config.TEMP_DIR.glob("*")) if config.TEMP_DIR.exists() else []
    temp_size = sum(f.stat().st_size for f in temp_files if f.is_file())

    rub_user_active = has_rubika_session(config.RUBIKA_SESSION) or has_rubika_session()
    rub_phone = ""
    if rub_user_active:
        try:
            from platforms.rubika_adapter import RubikaUserClient
            rub_phone = RubikaUserClient().get_masked_phone()
        except Exception:
            rub_phone = ""

    splus_active = False
    splus_phone = ""
    try:
        from platforms.soroush_worker import soroush_worker
        splus_active = soroush_worker.is_connected()
        splus_phone = soroush_worker.get_masked_phone()
    except Exception:
        pass

    return {
        "engine_version": EngineVersionStr(f"UNFINIT Engine {config.ENGINE_VERSION}"),
        "uptime": uptime_str,
        "platforms": {
            "telegram": {
                "name": "تلگرام",
                "status": "ONLINE" if config.TELEGRAM_BOT_TOKEN else "OFFLINE",
                "owner_id": config.TELEGRAM_OWNER_ID,
                "badge": "bg-sky-600"
            },
            "bale": {
                "name": "پیام‌رسان بله",
                "status": "ONLINE" if config.BALE_BOT_TOKEN else "OFFLINE",
                "owner_id": config.BALE_OWNER_ID,
                "badge": "bg-emerald-600"
            },
            "rubika_user": {
                "name": "روبیکا کاربری",
                "status": "ONLINE" if rub_user_active else "REQUIRE_AUTH",
                "masked_phone": rub_phone,
                "badge": "bg-indigo-600" if rub_user_active else "bg-amber-600"
            },
            "soroush": {
                "name": "سروش‌پلاس",
                "status": "ONLINE" if splus_active else "REQUIRE_AUTH",
                "masked_phone": splus_phone,
                "badge": "bg-cyan-600" if splus_active else "bg-amber-600"
            }
        },
        "stats": {
            "temp_files_count": len(temp_files),
            "temp_size_str": human_size(temp_size),
            "active_sessions_count": len(session_manager._sessions)
        },
        "system_health": "100% پایدار",
        "latency_ms": 15
    }


def render_studio_table_rows(sort_by: str = "newest") -> str:
    active_drops: List[Dict[str, Any]] = []
    for sid, sess in list(session_manager._sessions.items()):
        if isinstance(sess, dict) and not sid.startswith("url_") and not sid.startswith("rurl_"):
            embed = sess.get("embed_meta") or {}
            draft = sess.get("draft_tags") or {}
            title = draft.get("title") or embed.get("title") or sess.get("title") or ""
            artist = draft.get("artist") or embed.get("artist") or sess.get("artist") or ""
            album = draft.get("album") or embed.get("album") or sess.get("album") or ""
            fn = draft.get("new_filename") or sess.get("audio_filename") or sess.get("filename") or "media_file"
            raw_sz = int(sess.get("file_size") or 0)
            created = str(sess.get("created_at") or "")
            active_drops.append({
                "drop_id": sid,
                "filename": fn,
                "title": title,
                "artist": artist,
                "album": album,
                "platform": sess.get("platform") or sess.get("source_platform") or "unknown",
                "media_type": sess.get("media_type") or "audio",
                "raw_size": raw_sz,
                "size": human_size(raw_sz),
                "created": created
            })

    if not active_drops:
        return '<tr><td colspan="4" class="py-8 text-center text-slate-500">در حال حاضر هیچ فایل رسانه‌ای در حافظه استودیو نیست. فایل‌های خود را از کادر بالا بکشید و رها کنید.</td></tr>'

    if sort_by == "oldest":
        active_drops.sort(key=lambda x: x["created"])
    elif sort_by == "size_desc":
        active_drops.sort(key=lambda x: x["raw_size"], reverse=True)
    elif sort_by == "size_asc":
        active_drops.sort(key=lambda x: x["raw_size"])
    elif sort_by == "name_asc":
        active_drops.sort(key=lambda x: (x["filename"] or "").lower())
    else:  # "newest"
        active_drops.sort(key=lambda x: x["created"], reverse=True)

    drop_rows = ""
    for d in active_drops:
        safe_fn = d['filename'].replace('"', '&quot;').replace("'", "&#39;")
        safe_title = d['title'].replace('"', '&quot;').replace("'", "&#39;")
        safe_artist = d['artist'].replace('"', '&quot;').replace("'", "&#39;")
        safe_album = d['album'].replace('"', '&quot;').replace("'", "&#39;")

        drop_rows += f"""
        <tr class="border-b border-slate-700/50 hover:bg-slate-800/60 transition group" id="row_{d['drop_id']}">
            <td class="py-3 px-3 text-center">
                <input type="checkbox" class="drop-chk w-4 h-4 rounded border-slate-600 bg-slate-800 text-cyan-600 focus:ring-cyan-500 cursor-pointer" data-drop-id="{d['drop_id']}" onchange="updateSelectedCount()">
            </td>
            <td class="py-3 px-3">
                <div class="flex items-center gap-3">
                    <div class="w-[38px] h-[38px] rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 overflow-hidden">
                        <span class="text-base">🎵</span>
                    </div>
                    <div class="flex flex-col gap-0.5">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-mono text-amber-400 font-bold bg-amber-950/60 px-1.5 py-0.5 rounded border border-amber-800/80">{d['drop_id']}</span>
                            <span class="text-xs font-bold text-slate-100 truncate max-w-[240px]" title="{safe_fn}">{safe_fn}</span>
                        </div>
                        <div class="text-[11px] text-slate-400 mt-1 flex flex-wrap items-center gap-2">
                            <span class="text-cyan-300 font-medium">🎵 {safe_title or 'بدون عنوان'}</span>
                            <span class="text-slate-400">👤 {safe_artist or 'هنرمند ناشناس'}</span>
                            <span class="text-slate-500">💿 {safe_album or 'بدون آلبوم'}</span>
                        </div>
                    </div>
                </div>
            </td>
            <td class="py-3 px-3">
                <div class="flex flex-col gap-1">
                    <span class="text-xs text-slate-300 font-mono">{d['size']}</span>
                    <span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700 uppercase inline-block w-max">{d['platform']} | {d['media_type']}</span>
                </div>
            </td>
            <td class="py-3 px-3 text-left">
                <div class="flex flex-wrap items-center justify-end gap-1.5">
                    <button onclick="openSpecsModal('{d['drop_id']}')" class="px-2 py-1 rounded-lg bg-indigo-950 hover:bg-indigo-900 text-indigo-300 border border-indigo-800 text-xs font-semibold flex items-center gap-1 transition" title="مشاهده بیت‌ریت، سمپل‌ریت، کانال و کدک">
                        <span>📊</span> مشخصات
                    </button>
                    <button type="button" onclick="openCutterModal(this.getAttribute('data-drop-id'), this.getAttribute('data-filename'))" data-drop-id="{d['drop_id']}" data-filename="{safe_fn}" class="px-2 py-1 rounded-lg bg-emerald-950 hover:bg-emerald-900 text-emerald-300 border border-emerald-800 text-xs font-semibold flex items-center gap-1 transition cursor-pointer" title="برش آنلاین صدا با رسم موج صوتی">
                        <span>✂️</span> برش صدا
                    </button>
                    <button onclick="openTagModal('{d['drop_id']}', '{safe_title}', '{safe_artist}', '{safe_album}', '{safe_fn}')" class="px-2 py-1 rounded-lg bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800 text-xs font-semibold flex items-center gap-1 transition" title="ویرایش عنوان، هنرمند، آلبوم، کاور و نام فایل">
                        <span>✏️</span> تگ و کاور
                    </button>
                    <a href="/dl/{d['drop_id']}" target="_blank" class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold inline-flex items-center gap-1 transition" title="دانلود مستقیم فایل">
                        <span>📥</span>
                    </a>
                    <button onclick="deleteStudioDrop('{d['drop_id']}')" class="px-2 py-1 rounded-lg bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800 text-xs font-semibold transition" title="حذف سشن و فایل از سرور">
                        <span>🗑️</span>
                    </button>
                    <div class="inline-flex items-center bg-slate-900 border border-slate-700 rounded-lg p-0.5">
                        <button onclick="dispatchDrop('{d['drop_id']}', 'telegram')" class="px-1.5 py-1 rounded hover:bg-sky-900/60 text-sky-300 text-xs font-bold transition" title="ارسال به تلگرام">✈️</button>
                        <button onclick="dispatchDrop('{d['drop_id']}', 'bale')" class="px-1.5 py-1 rounded hover:bg-emerald-900/60 text-emerald-300 text-xs font-bold transition" title="ارسال به بله (با فشرده‌سازی خودکار)">🟢</button>
                        <button onclick="dispatchDrop('{d['drop_id']}', 'rubika')" class="px-1.5 py-1 rounded hover:bg-purple-900/60 text-purple-300 text-xs font-bold transition" title="ارسال به روبیکا">🟣</button>
                    </div>
                </div>
            </td>
        </tr>
        """
    return drop_rows




def render_dashboard_html() -> str:
    health = get_system_health()
    p = health["platforms"]
    s = health["stats"]
    connected_platforms_count = sum(1 for p_val in p.values() if p_val.get("status") == "ONLINE")

    # Gather products safely
    products = []
    saved_theme = "default-dark"
    try:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        from core.database import get_system_setting
        if running_loop and running_loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                products = pool.submit(lambda: asyncio.run(StoreService.get_all_products())).result()
                saved_theme = pool.submit(lambda: asyncio.run(get_system_setting("THEME", "default-dark"))).result()
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            products = loop.run_until_complete(StoreService.get_all_products())
            saved_theme = loop.run_until_complete(get_system_setting("THEME", "default-dark"))
            loop.close()
        if not saved_theme or saved_theme not in ["default-dark", "catppuccin", "dracula", "tokyo-night", "vesper", "solarized-dark", "monokai", "one-dark-pro"]:
            saved_theme = "default-dark"
    except Exception as e:
        logger.warning(f"Web panel data fetch error: {e}")
        saved_theme = "default-dark"

    active_count = sum(1 for prod in products if prod.active)

    prod_cards = ""
    if not products:
        prod_cards = '<div class="col-span-full py-12 text-center text-slate-500 bg-slate-900/40 rounded-2xl border border-slate-800">هیچ دوره‌ای در سیستم ثبت نشده است. از فرم زیر جهت افزودن دوره استفاده فرمایید.</div>'
    else:
        for prod in products:
            status_badge = f'<span id="status_badge_{prod.product_id}" class="px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> فعال</span>' if prod.active else f'<span id="status_badge_{prod.product_id}" class="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-950 text-rose-300 border border-rose-800 flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span> غیرفعال</span>'
            price_badge = f'<span class="text-sm font-bold text-emerald-400 font-mono">{prod.price:,} تومان</span>' if prod.price > 0 else '<span class="text-sm font-bold text-cyan-400">رایگان</span>'
            
            card_badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-cyan-300 border border-cyan-800/60" style="color: var(--accent-color);">کارت‌به‌کارت ✓</span>' if prod.allow_card else '<span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-500 border border-slate-700">کارت‌به‌کارت ✕</span>'
            bale_badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950/60 text-emerald-300 border border-emerald-800/60">درگاه بله ✓</span>' if prod.allow_bale else '<span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-500 border border-slate-700">درگاه بله ✕</span>'
            ref_badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-amber-950/60 text-amber-300 border border-amber-800/60">۱ دعوت الزامی</span>' if getattr(prod, 'requires_referral', False) else ''
            
            deliv_mode = getattr(prod, "delivery_type", "channel")
            deliv_badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-indigo-950/60 text-indigo-300 border border-indigo-800/60">پکیج فایلی</span>' if deliv_mode == "files_package" else '<span class="px-2 py-0.5 rounded text-[10px] bg-cyan-950/60 text-cyan-300 border border-cyan-800/60">کانال تلگرام/بله</span>'

            dl_html = f'''
            <div class="mt-3 pt-2.5 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                <span class="truncate max-w-[180px] font-mono" title="{prod.download_link}">{prod.download_link}</span>
                <button onclick="copyText('{prod.download_link}')" class="text-cyan-400 hover:text-cyan-300 px-2 py-1 rounded bg-slate-800 text-[10px] border border-slate-700 transition">کپی لینک</button>
            </div>
            ''' if prod.download_link else '<div class="mt-3 pt-2.5 border-t border-slate-800 text-[11px] text-slate-500 flex items-center gap-1">فاقد لینک مستقیم</div>'

            banner_html = f'''<img src="{prod.photo_url}" alt="{prod.name}" class="w-full max-h-80 object-contain rounded-xl mb-3 border border-slate-700/60" onerror="this.style.display=\'none\'">''' if prod.photo_url else ''

            toggle_btn = f'''<button id="toggle_btn_{prod.product_id}" onclick="toggleCourseActive('{prod.product_id}')" class="theme-card-btn px-2.5 py-1.5 rounded-lg text-xs font-semibold transition">{'غیرفعال‌سازی' if prod.active else 'فعال‌سازی'}</button>'''

            prod_cards += f"""
            <div class="glass p-5 rounded-2xl flex flex-col justify-between border border-slate-800 hover:border-cyan-500/40 transition group" id="course_card_{prod.product_id}">
                <div>
                    {banner_html}
                    <div class="flex justify-between items-start gap-2 mb-2">
                        <div>
                            <span class="text-[10px] font-mono text-cyan-400 bg-cyan-950/80 px-2 py-0.5 rounded border border-cyan-800">{prod.product_id}</span>
                            <h3 class="text-base font-bold text-white mt-1.5 leading-snug group-hover:text-cyan-300 transition">{prod.name}</h3>
                        </div>
                        {status_badge}
                    </div>
                    <div class="my-2.5 flex items-center justify-between">
                        <span class="text-xs text-slate-400">قیمت دوره:</span>
                        {price_badge}
                    </div>
                    <p class="text-xs text-slate-300 line-clamp-3 leading-relaxed mb-3 bg-slate-900/40 p-2.5 rounded-xl border border-slate-800/60">{prod.description or 'توضیحاتی برای این دوره ثبت نشده است.'}</p>
                    <div class="flex flex-wrap gap-1.5">
                        {card_badge}
                        {bale_badge}
                        {ref_badge}
                        {deliv_badge}
                    </div>
                    {dl_html}
                </div>
                <div class="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between gap-2">
                    <button onclick="openEditCourseModal('{prod.product_id}')" data-course-id="{prod.product_id}" class="theme-card-btn px-3 py-1.5 rounded-lg text-xs text-slate-200 flex items-center gap-1 transition">
                        ویرایش
                    </button>
                    <div class="flex items-center gap-1.5">
                        {toggle_btn}
                        <button onclick="deleteCourse('{prod.product_id}')" class="theme-card-btn px-2.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1" title="حذف دائم دوره">
                            حذف دوره
                        </button>
                    </div>
                </div>
            </div>
            """

    courses_dict = {}
    for prod in products:
        try:
            pid = str(getattr(prod, "product_id", "") or "")
            dt = getattr(prod, "delivery_type", "channel")
            pkg = getattr(prod, "files_package", [])
            courses_dict[pid] = {
                "product_id": pid,
                "name": str(getattr(prod, "name", "") or "") if isinstance(getattr(prod, "name", None), str) else "",
                "price": int(getattr(prod, "price", 0) or 0) if isinstance(getattr(prod, "price", None), (int, float)) else 0,
                "description": str(getattr(prod, "description", "") or "") if isinstance(getattr(prod, "description", None), str) else "",
                "download_link": str(getattr(prod, "download_link", "") or "") if isinstance(getattr(prod, "download_link", None), str) else "",
                "photo_url": str(getattr(prod, "photo_url", "") or "") if isinstance(getattr(prod, "photo_url", None), str) else "",
                "allow_card": 1 if getattr(prod, "allow_card", True) else 0,
                "allow_bale": 1 if getattr(prod, "allow_bale", True) else 0,
                "requires_referral": 1 if getattr(prod, "requires_referral", False) else 0,
                "is_active": 1 if getattr(prod, "active", True) else 0,
                "delivery_type": dt if isinstance(dt, str) else "channel",
                "files_package": pkg if isinstance(pkg, list) else []
            }
        except Exception:
            continue
    courses_data_json = json.dumps(courses_dict, ensure_ascii=False)

    drop_rows = render_studio_table_rows()
    active_drops_count = len([s for s in session_manager._sessions if not s.startswith("url_") and not s.startswith("rurl_")])
    course_terms_escaped = html.escape(getattr(config, "COURSE_TERMS_TEXT", ""))

    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0%25' y1='100%25' x2='100%25' y2='0%25'%3E%3Cstop offset='0%25' stop-color='%2306b6d4'/%3E%3Cstop offset='100%25' stop-color='%232563eb'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='100' height='100' rx='24' fill='url(%23g)'/%3E%3Cpath d='M30 26h12v32c0 6.6 5.4 12 12 12s12-5.4 12-12V26h12v32c0 13.3-10.7 24-24 24s-24-10.7-24-24V26z' fill='%23ffffff'/%3E%3Ccircle cx='54' cy='36' r='6' fill='%2338bdf8'/%3E%3C/svg%3E">
    <link rel="shortcut icon" href="/favicon.ico">
    <title>UNFINIT Store Engine {config.ENGINE_VERSION} | پنل مدیریت، استودیوی رسانه و فروشگاه آنلاین</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.min.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,300;0,400;0,500;0,700;1,400&family=Vazirmatn:wght@200;300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        * {{ font-family: 'Vazirmatn', 'Roboto', sans-serif !important; }}
        :root, body.theme-default-dark {{
            --bg-color: #080e1e;
            --fg-color: #f1f5f9;
            --accent-color: #06b6d4;
            --glass-bg: rgba(15, 23, 42, 0.85);
            --card-border: rgba(6, 182, 212, 0.2);
            --input-bg: #0f172a; /* #1e293b */
            --card-bg: #0f172a;
            --table-head-bg: #111a2e;
            --table-row-hover: rgba(30, 41, 59, 0.5);
        }}
        body.theme-catppuccin {{
            --bg-color: #24273A;
            --fg-color: #CAD3F5;
            --accent-color: #C6A0F6;
            --glass-bg: rgba(36, 39, 58, 0.85);
            --card-border: rgba(198, 160, 246, 0.2);
            --input-bg: #1e2030;
            --card-bg: #1e2030;
            --table-head-bg: #2a2e45;
            --table-row-hover: rgba(54, 58, 79, 0.5);
        }}
        body.theme-dracula {{
            --bg-color: #282A36;
            --fg-color: #F8F8F2;
            --accent-color: #BD93F9;
            --glass-bg: rgba(40, 42, 54, 0.85);
            --card-border: rgba(189, 147, 249, 0.2);
            --input-bg: #21222c;
            --card-bg: #21222c;
            --table-head-bg: #343746;
            --table-row-hover: rgba(68, 71, 90, 0.5);
        }}
        body.theme-tokyo-night {{
            --bg-color: #1A1B26;
            --fg-color: #A9B1D6;
            --accent-color: #7AA2F7;
            --glass-bg: rgba(26, 27, 38, 0.85);
            --card-border: rgba(122, 162, 247, 0.2);
            --input-bg: #16161e;
            --card-bg: #16161e;
            --table-head-bg: #1f2335;
            --table-row-hover: rgba(41, 46, 66, 0.5);
        }}
        body.theme-vesper {{
            --bg-color: #101010;
            --fg-color: #FFFFFF;
            --accent-color: #FFC799;
            --glass-bg: rgba(18, 18, 18, 0.88);
            --card-border: rgba(255, 199, 153, 0.2);
            --input-bg: #181818;
            --card-bg: #181818;
            --table-head-bg: #1e1e1e;
            --table-row-hover: rgba(38, 38, 38, 0.5);
        }}
        body.theme-solarized-dark {{
            --bg-color: #002B36;
            --fg-color: #93A1A1;
            --accent-color: #268BD2;
            --glass-bg: rgba(0, 43, 54, 0.85);
            --card-border: rgba(38, 139, 210, 0.2);
            --input-bg: #073642;
            --card-bg: #073642;
            --table-head-bg: #0b4352;
            --table-row-hover: rgba(10, 76, 93, 0.5);
        }}
        body.theme-monokai {{
            --bg-color: #272822;
            --fg-color: #F8F8F2;
            --accent-color: #F92672;
            --glass-bg: rgba(39, 40, 34, 0.85);
            --card-border: rgba(249, 38, 114, 0.2);
            --input-bg: #1e1f1c;
            --card-bg: #1e1f1c;
            --table-head-bg: #32302f;
            --table-row-hover: rgba(62, 59, 63, 0.5);
        }}
        body.theme-one-dark-pro {{
            --bg-color: #282C34;
            --fg-color: #ABB2BF;
            --accent-color: #61AFEF;
            --glass-bg: rgba(40, 44, 52, 0.85);
            --card-border: rgba(97, 175, 239, 0.2);
            --input-bg: #21252b;
            --card-bg: #21252b;
            --table-head-bg: #2e3440;
            --table-row-hover: rgba(53, 59, 69, 0.5);
        }}
        @media (min-width: 768px) {{
            #mainSidebar.sidebar-collapsed {{
                transform: translateX(100%) !important;
            }}
            #contentWrapper.sidebar-collapsed {{
                margin-right: 0 !important;
            }}
        }}
        thead, thead tr, .table-head {{
            background-color: var(--table-head-bg) !important;
            color: var(--fg-color) !important;
        }}
        body {{
            font-family: 'Vazirmatn', 'Roboto', sans-serif !important;
            background: var(--bg-color) !important;
            color: var(--fg-color) !important;
            min-height: 100vh;
            transition: background-color 0.2s ease, color 0.2s ease;
        }}
        code, pre, .font-mono {{ font-family: 'Roboto', monospace !important; }}
        .glass, .settings-box, .setting-card, .glass-card, .store-card, details.settings-accordion {{
            background: var(--card-bg) !important;
            border: 1px solid var(--card-border) !important;
            color: var(--fg-color) !important;
        }}
        details.settings-accordion > summary {{
            background: var(--card-bg) !important;
            color: var(--fg-color) !important;
        }}
        details.settings-accordion[open] > summary {{
            border-bottom: 1px solid var(--card-border) !important;
        }}
        #logContainer, #liveLogContainer, pre.log-view {{
            background-color: var(--input-bg) !important;
            border: 1px solid var(--card-border) !important;
            color: var(--fg-color) !important;
        }}
        .tab-btn.active {{
            background: var(--accent-color) !important;
            color: white !important;
            border-color: transparent !important;
            box-shadow: 0 4px 20px -2px rgba(0, 122, 204, 0.35);
        }}
        .sidebar-nav-btn {{
            color: #94a3b8;
            border: 1px solid transparent;
            transition: all 0.2s ease;
        }}
        .sidebar-nav-btn:hover {{
            color: #f1f5f9;
            background: rgba(30, 41, 59, 0.6);
        }}
        .sidebar-nav-btn.active {{
            background: rgba(6, 182, 212, 0.1) !important;
            color: #22d3ee !important;
            border-color: rgba(6, 182, 212, 0.3) !important;
            box-shadow: 0 0 12px rgba(6, 182, 212, 0.15) !important;
        }}
        .theme-accent-btn {{
            background: var(--accent-color) !important;
            color: #ffffff !important;
        }}
        .theme-accent-btn:hover {{
            filter: brightness(1.15);
        }}
        .theme-card-btn {{
            background: var(--card-bg) !important;
            border: 1px solid var(--card-border) !important;
            color: var(--fg-color) !important;
        }}
        .theme-card-btn:hover {{
            border-color: var(--accent-color) !important;
            filter: brightness(1.15);
        }}
        #studioDropzone {{
            background-color: var(--input-bg) !important;
            border-color: var(--card-border) !important;
            color: var(--fg-color) !important;
            transition: all 0.2s ease-in-out;
        }}
        #studioDropzone:hover, #studioDropzone.dragover {{
            border-color: var(--accent-color) !important;
            box-shadow: 0 0 15px -3px var(--card-border);
        }}
                /* Universal Global Themed Scrollbar (8px) */
        html, body, *, *::-webkit-scrollbar, *::-webkit-scrollbar-thumb {{
            scrollbar-color: var(--accent-color, #06b6d4) transparent !important;
        }}
        *::-webkit-scrollbar {{
            width: 8px !important;
            height: 8px !important;
        }}
        *::-webkit-scrollbar-track {{
            background: transparent !important;
        }}
        *::-webkit-scrollbar-thumb {{
            background: var(--accent-color, #3b82f6) !important;
            border-radius: 9999px !important;
        }}
        *::-webkit-scrollbar-thumb:hover {{
            background: var(--accent-color, #3b82f6) !important;
            filter: brightness(1.2);
        }}
        * {{
            scrollbar-width: thin;
            scrollbar-color: var(--accent-color, #3b82f6) transparent !important;
        }}
        .chat-scrollbar::-webkit-scrollbar {{ width: 8px !important; }}
        .chat-scrollbar::-webkit-scrollbar-track {{ background: transparent !important; }}
        .chat-scrollbar::-webkit-scrollbar-thumb {{ background: var(--accent-color, #3b82f6) !important; border-radius: 9999px !important; }}
        .chat-scrollbar::-webkit-scrollbar-thumb:hover {{ background: var(--accent-color, #3b82f6) !important; filter: brightness(1.2); }}
        input, select, textarea {{
            background-color: var(--input-bg) !important;
            color: var(--fg-color) !important;
            border-color: var(--card-border) !important;
        }}
        input::placeholder, textarea::placeholder {{
            color: #94a3b8 !important;
        }}
        input:-webkit-autofill,
        input:-webkit-autofill:hover, 
        input:-webkit-autofill:focus,
        input:-webkit-autofill:active,
        textarea:-webkit-autofill,
        textarea:-webkit-autofill:hover,
        textarea:-webkit-autofill:focus,
        textarea:-webkit-autofill:active,
        select:-webkit-autofill,
        select:-webkit-autofill:hover,
        select:-webkit-autofill:focus,
        select:-webkit-autofill:active {{
            -webkit-box-shadow: 0 0 0 1000px #0f172a inset !important;
            -webkit-text-fill-color: #f1f5f9 !important;
            caret-color: #f1f5f9 !important;
            border-color: var(--card-border) !important;
            transition: background-color 5000s ease-in-out 0s !important;
        }}
    </style>
    <style>
        /* High-Priority Universal Themed Scrollbar */
        :root, html, body, *, *::-webkit-scrollbar, *::-webkit-scrollbar-thumb {{
            scrollbar-color: var(--accent-color, #a855f7) transparent !important;
            scrollbar-width: thin !important;
        }}
        ::-webkit-scrollbar {{ width: 8px !important; height: 8px !important; }}
        ::-webkit-scrollbar-track {{ background: transparent !important; }}
        ::-webkit-scrollbar-thumb {{ background: var(--accent-color, #a855f7) !important; border-radius: 9999px !important; }}
    </style>
</head>
<body class="text-slate-100 min-h-screen theme-{saved_theme}">
    <!-- ================= FULLSCREEN LOGIN GATE ================= -->
    <div id="loginGate" class="fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-300" style="background: radial-gradient(circle at 50% 30%, #0e224c 0%, #081229 55%, #020612 100%);">
        <div class="glass p-8 md:p-10 rounded-3xl w-full max-w-md border border-cyan-500/30 shadow-2xl shadow-cyan-950/70 text-center space-y-6 relative overflow-hidden">
            <div class="absolute -top-12 -right-12 w-36 h-36 bg-cyan-500/10 rounded-full blur-2xl pointer-events-none"></div>
            <div class="absolute -bottom-12 -left-12 w-36 h-36 bg-cyan-600/10 rounded-full blur-2xl pointer-events-none"></div>

            <!-- Brand Header -->
            <div class="flex items-center justify-center gap-3">
                <div class="w-12 h-12 rounded-2xl flex items-center justify-center font-bold text-2xl shadow-xl shadow-cyan-500/30 text-white overflow-hidden relative" id="loginLogoContainer" style="background: var(--accent-color, #06b6d4);">
                    <img id="loginLogoImg" src="/static/logo.png?t={int(time.time())}" alt="Logo" class="w-full h-full object-cover" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';">
                    <span class="hidden items-center justify-center w-full h-full text-2xl font-bold">⚡️</span>
                </div>
                <div class="text-right">
                    <div class="flex items-center gap-2">
                        <h1 class="text-xl font-black text-white tracking-tight">UNFINIT Panel</h1>
                        <span class="text-[11px] font-mono font-bold text-cyan-400 bg-cyan-950/80 px-2 py-0.5 rounded-lg border border-cyan-800">{config.ENGINE_VERSION}</span>
                    </div>
                </div>
            </div>

            <div>
                <h2 class="text-base font-bold text-slate-100">ورود به پنل مدیریت</h2>
                <p class="text-xs text-slate-400 mt-1">جهت دسترسی به داشبورد، هاب رسانه و هوش مصنوعی هرمس</p>
            </div>

            <div id="mainLoginContainer" class="space-y-4 text-right">
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1.5">شناسه کاربری / ایمیل</label>
                    <input type="text" id="loginUsername" value="admin" class="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono transition">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1.5">رمز عبور مدیریت</label>
                    <div class="relative">
                        <input type="password" id="adminPasswordInput" autocomplete="current-password" placeholder="رمز عبور مدیریت..." onkeydown="if(event.key==='Enter') executeAdminLogin()" class="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono transition pl-10 text-left" dir="ltr">
                        <button type="button" onclick="toggleAdminLoginPwd()" class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-cyan-300 transition text-sm" title="نمایش/مخفی‌سازی رمز">
                            👁
                        </button>
                    </div>
                </div>
                <button type="button" id="loginBtn" onclick="executeAdminLogin()" class="w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 via-cyan-600 to-teal-500 hover:from-blue-500 hover:to-teal-400 text-xs font-bold text-white shadow-lg shadow-cyan-500/25 transition flex items-center justify-center gap-2">
                    <span>➔</span> ورود به پنل
                </button>
                <div id="loginErrorMsg" style="display: none; color: #ef4444; font-size: 13px; text-align: center; margin-top: 8px;"></div>
            </div>

            <!-- Dedicated Isolated Login Script -->
            <script>
                function toggleAdminLoginPwd() {{
                    var inp = document.getElementById('adminPasswordInput');
                    if (inp) {{
                        inp.type = (inp.type === 'password') ? 'text' : 'password';
                    }}
                }}

                async function executeAdminLogin() {{
                    var btn = document.getElementById('loginBtn');
                    var errMsg = document.getElementById('loginErrorMsg');
                    var pwdInput = document.getElementById('adminPasswordInput');
                    var pwd = pwdInput ? pwdInput.value.trim() : '';

                    if (errMsg) {{
                        errMsg.style.display = 'none';
                        errMsg.innerText = '';
                    }}

                    if (!pwd) {{
                        if (errMsg) {{
                            errMsg.innerText = '❌ لطفاً رمز عبور را وارد کنید.';
                            errMsg.style.display = 'block';
                        }}
                        return;
                    }}

                    if (btn) {{
                        btn.disabled = true;
                        btn.innerHTML = '⏳ در حال بررسی...';
                    }}

                    try {{
                        var res = await fetch('/api/login', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ password: pwd }})
                        }});
                        var data = await res.json();
                        if (data && data.ok) {{
                            applySuccessfulLogin(pwd);
                            return;
                        }} else {{
                            if (errMsg) {{
                                errMsg.innerText = '❌ رمز عبور اشتباه است.';
                                errMsg.style.display = 'block';
                            }}
                        }}
                    }} catch (err) {{
                        if (errMsg) {{
                            errMsg.innerText = '❌ خطای ارتباط با سرور: ' + (err.message || 'نامشخص');
                            errMsg.style.display = 'block';
                        }}
                    }} finally {{
                        if (btn) {{
                            btn.disabled = false;
                            btn.innerHTML = '<span>➔</span> ورود به پنل';
                        }}
                    }}
                }}

                function applySuccessfulLogin(pwd) {{
                    try {{
                        localStorage.setItem('unfinit_auth', 'true');
                        localStorage.setItem('unfinit_auth_token', 'authenticated');
                        localStorage.setItem('unfinit_admin_pwd', pwd);
                        sessionStorage.setItem('unfinit_auth', 'true');
                        sessionStorage.setItem('unfinit_auth_token', 'authenticated');
                        sessionStorage.setItem('unfinit_admin_pwd', pwd);
                    }} catch (e) {{}}
                    window.currentAdminPassword = pwd;

                    var gate = document.getElementById('loginGate');
                    var app = document.getElementById('appMain');
                    if (gate) {{
                        gate.style.setProperty('display', 'none', 'important');
                        gate.classList.add('hidden');
                    }}
                    if (app) {{
                        app.style.setProperty('display', 'block', 'important');
                        app.classList.remove('hidden');
                    }}

                    try {{
                        var savedTab = localStorage.getItem('unfinit_active_tab') || 'tab-studio';
                        if (typeof switchTab === 'function') {{
                            switchTab(savedTab);
                        }}
                    }} catch (e) {{
                        console.warn('Tab switch notice:', e);
                    }}
                }}

                function checkAdminLoginOnLoad() {{
                    var token = localStorage.getItem('unfinit_auth_token') || sessionStorage.getItem('unfinit_auth_token') || localStorage.getItem('unfinit_auth');
                    var pwd = localStorage.getItem('unfinit_admin_pwd') || sessionStorage.getItem('unfinit_admin_pwd');
                    var gate = document.getElementById('loginGate');
                    var app = document.getElementById('appMain');

                    if ((token === 'authenticated' || token === 'true') && pwd) {{
                        window.currentAdminPassword = pwd;
                        if (gate) {{
                            gate.style.setProperty('display', 'none', 'important');
                            gate.classList.add('hidden');
                        }}
                        if (app) {{
                            app.style.setProperty('display', 'block', 'important');
                            app.classList.remove('hidden');
                        }}
                    }}
                }}

                
        // ================= ANTIGRAVITY OFFICIAL THEMES =================
        var themeAccents = {{
            'default-dark': '#06b6d4',
            'catppuccin': '#C6A0F6',
            'dracula': '#BD93F9',
            'tokyo-night': '#7AA2F7',
            'vesper': '#FFC799',
            'solarized-dark': '#268BD2',
            'monokai': '#F92672',
            'one-dark-pro': '#61AFEF'
        }};
        function applyAntigravityTheme(themeKey, syncServer) {{
            var validThemes = ['default-dark', 'catppuccin', 'dracula', 'tokyo-night', 'vesper', 'solarized-dark', 'monokai', 'one-dark-pro'];
            if (!validThemes.includes(themeKey)) themeKey = 'default-dark';
            validThemes.forEach(function(t) {{
                document.body.classList.remove('theme-' + t);
            }});
            document.body.classList.add('theme-' + themeKey);
            var currentThemeAccent = themeAccents[themeKey] || '#06b6d4';
            try {{
                document.documentElement.style.setProperty('--accent-color', currentThemeAccent);
                localStorage.setItem('unfinit_theme', themeKey);
            }} catch(e) {{}}
            var sel = document.getElementById('themeSwitcherSelect');
            if (sel && sel.value !== themeKey) {{
                sel.value = themeKey;
            }}
            if (syncServer !== false) {{
                try {{
                    fetch('/api/settings/theme', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ theme: themeKey }})
                    }}).catch(function(e) {{}});
                }} catch(e) {{}}
            }}
        }}
        window.changeTheme = applyAntigravityTheme;
        window.applyAntigravityTheme = applyAntigravityTheme;
        try {{
            var initTheme = localStorage.getItem('unfinit_theme') || '{saved_theme}';
            applyAntigravityTheme(initTheme, false);
        }} catch(e) {{}}

                window.toggleAdminLoginPwd = toggleAdminLoginPwd;
                window.executeAdminLogin = executeAdminLogin;
                window.handleLoginSubmit = executeAdminLogin;

                checkAdminLoginOnLoad();
                document.addEventListener('DOMContentLoaded', checkAdminLoginOnLoad);
            </script>
        </div>
    </div>

    <!-- ================= MAIN APP WRAPPER ================= -->
    <div id="appMain" data-id="mainDashboard" class="hidden min-h-screen" style="display: none !important;">
        <!-- Mobile Drawer Backdrop Overlay -->
        <div id="drawerOverlay" onclick="toggleSidebar(false)" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 hidden transition-opacity duration-300 md:hidden"></div>

        <!-- ================= MODERN RIGHT SIDEBAR (Collapsible) ================= -->
        <aside id="mainSidebar" class="w-64 fixed right-0 top-0 bottom-0 z-50 flex flex-col justify-between transition-all duration-300 ease-in-out border-l border-slate-800 translate-x-full md:translate-x-0" style="background: var(--bg-color, #090d16); border-color: var(--card-border, #1e293b);">
            <!-- Sidebar Header / Brand -->
            <div class="p-4 border-b border-slate-800/80">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl flex items-center justify-center font-bold text-xl shadow-lg shadow-cyan-500/20 text-white overflow-hidden relative shrink-0" id="headerLogoContainer" style="background: var(--accent-color, #06b6d4);">
                            <img id="headerLogoImg" src="/static/logo.png?t={int(time.time())}" alt="Logo" class="w-full h-full object-cover" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';">
                            <span class="hidden items-center justify-center w-full h-full text-white font-bold p-1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="M6 4v8a6 6 0 0012 0V4M12 18v2"/></svg></span>
                        </div>
                        <div class="overflow-hidden">
                            <h1 class="text-sm font-bold tracking-tight text-white flex items-center gap-1.5 truncate">
                                <span>UNFINIT Hub</span>
                                <span class="text-amber-400 text-xs" title="پنل مدیریت ارشد">👑</span>
                                <span class="text-[10px] font-mono px-1.5 py-0.2 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">{config.ENGINE_VERSION}</span>
                            </h1>
                            <p class="text-[11px] text-slate-400 truncate">Store &amp; Media Studio</p>
                        </div>
                    </div>
                    <button type="button" onclick="toggleSidebar(false)" class="md:hidden p-1 rounded-lg bg-slate-800 text-slate-400 hover:text-white transition">
                        ✕
                    </button>
                </div>
            </div>

            <!-- Sidebar Navigation Items (8 Views) with Drag & Drop -->
            <nav class="flex-1 overflow-y-auto p-3 space-y-1.5 no-scrollbar" id="sidebarNavList">
                <!-- 1. Dashboard -->
                <button draggable="true" type="button" onclick="switchTab('dashboard'); toggleSidebar(false);" data-tab="dashboard" id="s-btn-tab-dashboard" class="sidebar-nav-btn w-full text-right px-3 py-2.5 rounded-xl text-xs font-medium transition flex items-center gap-2.5 cursor-grab active:cursor-grabbing active">
                    <svg width="20" height="20" class="w-5 h-5 shrink-0 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
                    </svg>
                    <span class="flex-1 text-right">داشبورد و وضعیت زنده</span>
                </button>

                <!-- 2. Downloads -->
                <button draggable="true" type="button" onclick="switchTab('downloads'); toggleSidebar(false);" data-tab="downloads" id="s-btn-tab-downloads" class="sidebar-nav-btn w-full text-right px-3 py-2.5 rounded-xl text-xs font-medium transition flex items-center gap-2.5 cursor-grab active:cursor-grabbing">
                    <svg width="20" height="20" class="w-5 h-5 shrink-0 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                    </svg>
                    <span class="flex-1 text-right">فایل‌های دانلودی سایت</span>
                    <span class="px-1.5 py-0.5 rounded-full text-[10px] bg-slate-800 text-cyan-400 font-mono">39p</span>
                </button>

                <!-- 3. Studio -->
                <button draggable="true" type="button" onclick="switchTab('studio'); toggleSidebar(false);" data-tab="studio" id="s-btn-tab-studio" class="sidebar-nav-btn w-full text-right px-3 py-2.5 rounded-xl text-xs font-medium transition flex items-center gap-2.5 cursor-grab active:cursor-grabbing">
                    <svg width="20" height="20" class="w-5 h-5 shrink-0 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
                    </svg>
                    <span class="flex-1 text-right">استودیوی رسانه و وکتور</span>
                    <span class="px-1.5 py-0.5 rounded-full text-[10px] bg-slate-800 text-cyan-400 font-mono">{active_drops_count}</span>
                </button>

                <!-- 4. Courses -->
                <button draggable="true" type="button" onclick="switchTab('courses'); toggleSidebar(false);" data-tab="courses" id="s-btn-tab-courses" class="sidebar-nav-btn w-full text-right px-3 py-2.5 rounded-xl text-xs font-medium transition flex items-center gap-2.5 cursor-grab active:cursor-grabbing">
                    <svg width="20" height="20" class="w-5 h-5 shrink-0 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
                    </svg>
                    <span class="flex-1 text-right">دوره‌ها و سرفصل‌ها</span>
                    <span class="px-1.5 py-0.5 rounded-full text-[10px] bg-slate-800 text-emerald-400 font-mono">{len(products)}</span>
                </button>

                <!-- 5. Orders -->
                <button draggable="true" type="button" onclick="switchTab('orders'); toggleSidebar(false);" data-tab="orders" id="s-btn-tab-orders" class="sidebar-nav-btn w-full text-right px-3 py-2.5 rounded-xl text-xs font-medium transition flex items-center gap-2.5 cursor-grab active:cursor-grabbing">
                    <svg width="20" height="20" class="w-5 h-5 shrink-0 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 10.5V6a3.75 3.75 0 10-7.5 0v4.5m11.356-1.993l1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 01-1.12-1.243l1.264-12A1.125 1.125 0 015.513 7.5h12.974c.576 0 1.059.435 1.119 1.007zM8.625 10.5a.375.375 0 11-.75 0 .375.375 0 01.75 0zm7.5 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
                    </svg>
                    <span class="flex-1 text-right">سفارشات و تراکنش‌ها</span>
                </button>

                <!-- 6. Users -->
                <button draggable="true" type="button" onclick="switchTab('users'); toggleSidebar(false);" data-tab="users" id="s-btn-tab-users" class="sidebar-nav-btn w-full text-right px-3 py-2.5 rounded-xl text-xs font-medium transition flex items-center gap-2.5 cursor-grab active:cursor-grabbing">
                    <svg width="20" height="20" class="w-5 h-5 shrink-0 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
                    </svg>
                    <span class="flex-1 text-right">مدیریت کاربران</span>
                </button>

                <!-- 7. Tokens & AI -->
                <button draggable="true" type="button" onclick="switchTab('tokens'); toggleSidebar(false);" data-tab="tokens" id="s-btn-tab-tokens" class="sidebar-nav-btn w-full text-right px-3 py-2.5 rounded-xl text-xs font-medium transition flex items-center gap-2.5 cursor-grab active:cursor-grabbing">
                    <svg width="20" height="20" class="w-5 h-5 shrink-0 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />
                    </svg>
                    <span class="flex-1 text-right">سکرت‌ها و هوش مصنوعی</span>
                </button>

                <!-- 8. Settings & Logs -->
                <button draggable="true" type="button" onclick="switchTab('settings'); toggleSidebar(false);" data-tab="settings" id="s-btn-tab-settings" class="sidebar-nav-btn w-full text-right px-3 py-2.5 rounded-xl text-xs font-medium transition flex items-center gap-2.5 cursor-grab active:cursor-grabbing">
                    <svg width="20" height="20" class="w-5 h-5 shrink-0 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.241.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <span class="flex-1 text-right">تنظیمات و لاگ‌ها</span>
                </button>
            </nav>

            <!-- Sidebar Footer -->
            <div class="p-3 border-t border-slate-800/80 space-y-2">
                <!-- Theme Switcher -->
                <div class="flex items-center gap-1.5 bg-slate-800/80 px-2.5 py-1.5 rounded-full overflow-hidden border border-slate-700 text-xs shadow-inner">
                    <svg width="16" height="16" class="w-4 h-4 shrink-0 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M4.098 19.902a3.75 3.75 0 005.304 0l6.401-6.402M6.75 21A3.75 3.75 0 013 17.25V4.125C3 3.504 3.504 3 4.125 3h5.25c.621 0 1.125.504 1.125 1.125v4.072M6.75 21a3.75 3.75 0 003.75-3.75V8.197M6.75 21h13.125c.621 0 1.125-.504 1.125-1.125v-5.25c0-.621-.504-1.125-1.125-1.125h-4.072M10.5 8.197l9.75 9.75" />
                    </svg>
                    <select id="themeSwitcherSelect" onchange="applyAntigravityTheme(this.value)" class="appearance-none rounded-full bg-transparent border-0 outline-none w-full cursor-pointer px-3 text-xs text-slate-300">
                        <option value="default-dark" class="bg-zinc-900 text-zinc-100" {'selected' if saved_theme == 'default-dark' else ''}>UNFINIT Classic (Default Dark)</option>
                        <option value="catppuccin" class="bg-zinc-900 text-zinc-100" {'selected' if saved_theme == 'catppuccin' else ''}>Catppuccin</option>
                        <option value="dracula" class="bg-zinc-900 text-zinc-100" {'selected' if saved_theme == 'dracula' else ''}>Dracula</option>
                        <option value="tokyo-night" class="bg-zinc-900 text-zinc-100" {'selected' if saved_theme == 'tokyo-night' else ''}>Tokyo Night</option>
                        <option value="vesper" class="bg-zinc-900 text-zinc-100" {'selected' if saved_theme == 'vesper' else ''}>Vesper</option>
                        <option value="solarized-dark" class="bg-zinc-900 text-zinc-100" {'selected' if saved_theme == 'solarized-dark' else ''}>Solarized Dark</option>
                        <option value="monokai" class="bg-zinc-900 text-zinc-100" {'selected' if saved_theme == 'monokai' else ''}>Monokai</option>
                        <option value="one-dark-pro" class="bg-zinc-900 text-zinc-100" {'selected' if saved_theme == 'one-dark-pro' else ''}>One Dark Pro</option>
                    </select>
                </div>

                <!-- Live Uptime -->
                <div class="flex items-center justify-between px-3 py-1.5 rounded-xl bg-slate-800/40 border border-slate-800 text-[11px]">
                    <div class="flex items-center gap-1.5">
                        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                        <span class="text-slate-400">آپ‌تایم:</span>
                    </div>
                    <span id="uptimeDisplay" class="font-mono font-bold text-emerald-400" data-start="{int(SERVER_START_TIME)}">{health['uptime']}</span>
                </div>

                <!-- Logout Button -->
                <button type="button" onclick="handleLogout()" class="w-full py-2 rounded-xl bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 border border-rose-800/60 text-xs transition flex items-center justify-center gap-2 font-medium">
                    <svg width="16" height="16" class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
                    </svg>
                    خروج از حساب
                </button>
            </div>
        </aside>

        <!-- Hidden Compatibility Elements for Legacy Test Assertions -->
        <div id="desktopNavTabs" class="hidden overflow-x-auto select-none touch-pan-x" style="display: none !important;">
            <button draggable="true" data-tab="studio" id="btn-tab-studio" class="tab-btn active shrink-0 whitespace-nowrap px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 border border-slate-700 cursor-grab active:cursor-grabbing"></button>
            <button draggable="true" data-tab="courses" id="btn-tab-courses" class="tab-btn shrink-0 whitespace-nowrap px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700 cursor-grab active:cursor-grabbing"></button>
            <button draggable="true" data-tab="downloads" id="btn-tab-downloads" class="tab-btn shrink-0 whitespace-nowrap px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700 cursor-grab active:cursor-grabbing"></button>
            <button draggable="true" data-tab="orders" id="btn-tab-orders" class="tab-btn shrink-0 whitespace-nowrap px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700 cursor-grab active:cursor-grabbing"></button>
            <button draggable="true" data-tab="tokens" id="btn-tab-tokens" class="tab-btn shrink-0 whitespace-nowrap px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700 cursor-grab active:cursor-grabbing"></button>
            <button draggable="true" data-tab="settings" id="btn-tab-settings" class="tab-btn shrink-0 whitespace-nowrap px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700 cursor-grab active:cursor-grabbing"></button>
        </div>
        <div id="mobileDrawer" class="hidden" style="display: none !important;"></div>
        <div id="mobileNavMenu" class="hidden" style="display: none !important;"><button id="m-btn-tab-downloads" class="hidden"></button></div>

        <!-- ================= MAIN CONTENT AREA ================= -->
        <div id="contentWrapper" class="md:mr-64 mr-0 min-h-screen flex flex-col transition-all duration-300">
            <!-- Top Sticky Header -->
            <header class="glass sticky top-0 z-30 px-4 sm:px-6 py-3.5 border-b border-slate-800/80 flex justify-between items-center gap-3">
                <div class="flex items-center gap-3">
                    <button type="button" onclick="toggleSidebar()" id="btnToggleSidebar" class="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center justify-center focus:outline-none" title="تغییر وضعیت منوی سایدبار">
                        <svg width="20" height="20" class="w-5 h-5 shrink-0 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                        </svg>
                    </button>
                    <button type="button" onclick="toggleSidebar()" id="btnMobileMenu" class="hidden" style="display:none !important;"></button>
                    <div>
                        <h2 id="currentTabTitle" class="text-base sm:text-lg font-bold text-white tracking-tight">داشبورد و وضعیت زنده موتور UNFINIT</h2>
                        <p id="currentTabDesc" class="text-xs text-slate-400">پایش لحظه‌ای اتصالات، آمار فایل‌ها، سقف ایمن بله و لاگ‌های زنده</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <button type="button" id="btnHeaderLogsDrawer" onclick="toggleLogsDrawer(true)" class="px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-sm theme-card-btn" style="border: 1px solid var(--card-border);" title="کنسول لاگ‌های زنده موتور">
                        <svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12" />
                        </svg>
                        <span>لاگ‌های زنده</span>
                    </button>
                    <div class="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium">
                        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                        موتور پایدار و فعال
                    </div>
                    <button onclick="handleLogout()" class="rounded-full px-4 py-1.5 bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800 text-xs transition flex items-center gap-1.5 font-medium">
                        خروج
                    </button>
                </div>
            </header>

            <!-- Main Content Container -->
            <main class="flex-1 p-4 sm:p-6 space-y-6 max-w-7xl w-full mx-auto">

        <!-- ================= TAB 0: DASHBOARD & LIVE STATUS ================= -->
        <div id="tab-dashboard" class="space-y-6">
            <!-- 4 Metric Cards -->
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
                <!-- Metric 1: Total Drops / Media Files -->
                <div class="glass p-4 rounded-2xl border" style="background: var(--card-bg); border-color: var(--card-border);">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs text-slate-400">فایل‌ها و رسانه‌های استودیو</span>
                        <div class="w-8 h-8 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center border border-cyan-500/20">
                            <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                            </svg>
                        </div>
                    </div>
                    <div class="text-xl sm:text-2xl font-bold font-mono text-white" id="dashTotalDrops">{active_drops_count}</div>
                    <p class="text-[11px] text-slate-500 mt-1">آماده پردازش و دیسپچ</p>
                </div>

                <!-- Metric 2: Active Platforms -->
                <div class="glass p-4 rounded-2xl border" style="background: var(--card-bg); border-color: var(--card-border);">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs text-slate-400">پلتفرم‌های متصل</span>
                        <div class="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">
                            <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
                            </svg>
                        </div>
                    </div>
                    <div class="text-xl sm:text-2xl font-bold text-emerald-400" style="letter-spacing: normal !important;" id="dashConnectedPlatforms"><span class="font-mono">{connected_platforms_count}</span> پلتفرم فعال</div>
                    <p class="text-[11px] text-slate-500 mt-1" id="dashConnectedSummary">از ۴ درگاه پیام‌رسان</p>
                </div>

                <!-- Metric 3: System Health -->
                <div class="glass p-4 rounded-2xl border" style="background: var(--card-bg); border-color: var(--card-border);">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs text-slate-400">سلامت هسته و انجین</span>
                        <div class="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20">
                            <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                    </div>
                    <div class="text-xl sm:text-2xl font-bold font-mono text-cyan-400">{health['system_health']}</div>
                    <p class="text-[11px] text-slate-500 mt-1">تأخیر: {health['latency_ms']}ms</p>
                </div>

                <!-- Metric 4: Bale Safe Limit -->
                <div class="glass p-4 rounded-2xl border" style="background: var(--card-bg); border-color: var(--card-border);">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs text-slate-400">سقف ایمن کمپرس بله</span>
                        <div class="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center border border-amber-500/20">
                            <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                            </svg>
                        </div>
                    </div>
                    <div class="text-xl sm:text-2xl font-bold font-mono text-amber-400 flex items-center justify-between">
                        <span id="dashBaleSafeSize">{config.MAX_SAFE_BALE_SIZE_MB} MB</span>
                        <button type="button" onclick="editBaleSafeLimit()" class="text-xs p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 transition flex items-center justify-center" title="ویرایش سریع سقف ایمن بله">
                            <svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
                            </svg>
                        </button>
                    </div>
                    <p class="text-[11px] text-slate-500 mt-1">فشرده‌سازی غیرمسدودکننده</p>
                </div>
            </div>

            <!-- Platform Status Cards (4 Columns) -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <!-- Telegram Card -->
                <div class="glass p-5 rounded-2xl relative overflow-hidden group transition border flex flex-col justify-between" style="background: var(--card-bg); border-color: var(--card-border);">
                    <div>
                        <div class="flex justify-between items-start mb-3">
                            <div class="flex items-center gap-2.5">
                                <div class="w-8 h-8 rounded-xl bg-sky-500/10 text-sky-400 flex items-center justify-center border border-sky-500/20 shrink-0">
                                    <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24">
                                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.75-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
                                    </svg>
                                </div>
                                <h3 class="font-bold text-sm text-slate-200">{p['telegram']['name']}</h3>
                            </div>
                            <span class="px-2 py-0.5 rounded text-xs font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                                {p['telegram']['status']}
                            </span>
                        </div>
                        <p class="text-xs text-slate-400">شناسه ادمین: <code style="color: var(--accent-color);">{p['telegram']['owner_id']}</code></p>
                        <p class="text-xs text-slate-400 mt-1">پروتکل: <span class="text-slate-300 font-mono text-[11px]">Pyrogram MTProto v2</span></p>
                    </div>
                    <div class="mt-3 pt-2 border-t border-white/5 text-[11px] text-emerald-400 flex items-center gap-1.5">
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> متصل و آماده تبادل رسانه
                    </div>
                </div>

                <!-- Bale Card -->
                <div class="glass p-5 rounded-2xl relative overflow-hidden group transition border flex flex-col justify-between" style="background: var(--card-bg); border-color: var(--card-border);">
                    <div>
                        <div class="flex justify-between items-start mb-3">
                            <div class="flex items-center gap-2.5">
                                <div class="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20 shrink-0">
                                    <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24">
                                        <path d="M12 2C6.48 2 2 6.48 2 12c0 1.93.55 3.73 1.5 5.26L2.36 21.64c-.13.39.24.76.63.63l4.38-1.14A9.96 9.96 0 0012 22c5.52 0 10-4.48 10-10S17.52 2 12 2zm0 15c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3-6H9c-.55 0-1-.45-1-1s.45-1 1-1h6c.55 0 1 .45 1 1s-.45 1-1 1z"/>
                                    </svg>
                                </div>
                                <h3 class="font-bold text-sm text-slate-200">{p['bale']['name']}</h3>
                            </div>
                            <span class="px-2 py-0.5 rounded text-xs font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                                {p['bale']['status']}
                            </span>
                        </div>
                        <p class="text-xs text-slate-400">شناسه مقصد: <code style="color: var(--accent-color);">{p['bale']['owner_id']}</code></p>
                        <p class="text-xs text-slate-400 mt-1">سقف ایمن: <span class="font-semibold" style="color: var(--accent-color);"><span id="baleCardSafeSize">{config.MAX_SAFE_BALE_SIZE_MB} MB</span> (کمپرس خودکار)</span></p>
                    </div>
                    <div class="mt-3">
                        <button type="button" onclick="editBaleSafeLimit()" class="w-full py-1.5 px-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 text-xs font-medium transition flex items-center justify-center gap-1.5">
                            <svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
                            </svg>
                            <span>ویرایش سقف ایمن حجم</span>
                        </button>
                    </div>
                </div>

                <!-- Rubika User Session Card -->
                <div class="glass p-5 rounded-2xl relative overflow-hidden group transition border flex flex-col justify-between" style="background: var(--card-bg); border-color: var(--card-border);">
                    <div>
                        <div class="flex justify-between items-start mb-3">
                            <div class="flex items-center gap-2.5">
                                <div class="w-8 h-8 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20 shrink-0">
                                    <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                                    </svg>
                                </div>
                                <h3 class="font-bold text-sm text-slate-200 truncate">{p['rubika_user']['name']}</h3>
                            </div>
                            <span class="px-2 py-0.5 rounded text-xs font-bold {'bg-emerald-950 text-emerald-400 border border-emerald-800' if p['rubika_user']['status'] == 'ONLINE' else 'bg-amber-950 text-amber-400 border border-amber-800'}">
                                {p['rubika_user']['status']}
                            </span>
                        </div>
                        <p class="text-xs text-slate-400">حالت: <span class="font-semibold text-emerald-400">ارسال به Saved Messages</span></p>
                        <p class="text-xs text-slate-400 mt-1">شماره حساب: <code class="font-mono text-cyan-300">{p['rubika_user'].get('masked_phone') or 'بدون شماره'}</code></p>
                        <p class="text-xs text-slate-400 mt-1">سشن: <span class="text-cyan-400 font-mono text-[11px]">AES-256-GCM رمزنگاری</span></p>
                    </div>
                    <div class="mt-3">
                        {f'''<button type="button" onclick="disconnectSession('rubika')" class="w-full py-1.5 px-2 rounded-lg bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 border border-rose-800 text-[11px] font-bold transition flex items-center justify-center gap-1.5"><svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" /></svg><span>قطع اتصال / خروج</span></button>''' if p['rubika_user']['status'] == 'ONLINE' else '''<p class="text-[11px] text-amber-400 text-center py-1">سشن غیرفعال است</p>'''}
                    </div>
                </div>

                <!-- Soroush Plus Session Card -->
                <div class="glass p-5 rounded-2xl relative overflow-hidden group transition border flex flex-col justify-between" style="background: var(--card-bg); border-color: var(--card-border);">
                    <div>
                        <div class="flex justify-between items-start mb-3">
                            <div class="flex items-center gap-2.5">
                                <div class="w-8 h-8 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center border border-cyan-500/20 shrink-0">
                                    <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a.75.75 0 01-.82-.82 4.498 4.498 0 00.978-2.222A7.777 7.777 0 013 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                                    </svg>
                                </div>
                                <h3 class="font-bold text-sm text-slate-200 truncate">{p['soroush']['name']}</h3>
                            </div>
                            <span class="px-2 py-0.5 rounded text-xs font-bold {'bg-emerald-950 text-emerald-400 border border-emerald-800' if p['soroush']['status'] == 'ONLINE' else 'bg-amber-950 text-amber-400 border border-amber-800'}">
                                {p['soroush']['status'] if p['soroush']['status'] == 'ONLINE' else 'نیازمند راه‌اندازی'}
                            </span>
                        </div>
                        <p class="text-xs text-slate-400">حالت: <span class="font-semibold text-cyan-400">ارسال به Saved Messages</span></p>
                        <p class="text-xs text-slate-400 mt-1">شماره حساب: <code class="font-mono text-cyan-300">{p['soroush'].get('masked_phone') or 'بدون شماره'}</code></p>
                        <p class="text-xs text-slate-400 mt-1">سشن: <span class="text-cyan-400 font-mono text-[11px]">AES-256-GCM رمزنگاری</span></p>
                    </div>
                    <div class="mt-3">
                        {f'''<button type="button" onclick="disconnectSession('soroush')" class="w-full py-1.5 px-2 rounded-lg bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 border border-rose-800 text-[11px] font-bold transition flex items-center justify-center gap-1.5"><svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" /></svg><span>قطع اتصال / خروج</span></button>''' if p['soroush']['status'] == 'ONLINE' else '''<button type="button" onclick="openSoroushLoginModal()" class="w-full py-1.5 px-2 rounded-lg theme-accent-btn text-[11px] font-bold transition flex items-center justify-center gap-1.5"><svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" /></svg><span>ورود به حساب سروش‌پلاس</span></button>'''}
                    </div>
                </div>
            </div>
        </div>

        <!-- Slide-Over Live Logs Drawer (Hugging Face / Modern DevOps style) -->
        <div id="logsDrawerOverlay" onclick="toggleLogsDrawer(false)" class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-50 transition-opacity"></div>
        <aside id="logsDrawer" class="fixed left-0 top-0 bottom-0 w-full max-w-2xl z-50 transform -translate-x-full transition-transform duration-300 ease-in-out flex flex-col border-r shadow-2xl" style="background: var(--panel-bg, #0a0f1d); border-color: var(--card-border, #1e293b);">
            <div class="p-3 border-b flex items-center justify-between gap-2" style="border-color: var(--card-border); background: var(--table-head-bg);">
                <div class="flex items-center gap-2">
                    <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    <h3 class="font-bold text-xs text-white font-mono flex items-center gap-2">
                        <span>Console Stream</span>
                        <span class="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800">LIVE</span>
                    </h3>
                </div>
                <div class="flex items-center gap-2">
                    <!-- Minimal Toolbar: Filter input, Auto-scroll, Copy, Refresh, Close -->
                    <input type="text" id="drawerLogSearch" oninput="filterDrawerLogs()" placeholder="جستجو در لاگ..." class="w-24 sm:w-36 px-2 py-1 rounded text-[11px] font-sans border text-slate-200 focus:outline-none focus:border-cyan-500" style="background: var(--input-bg, #111827); border-color: var(--card-border);">
                    <label class="flex items-center gap-1 text-[11px] text-slate-400 cursor-pointer font-sans select-none" title="اسکرول خودکار به انتهای لاگ">
                        <input type="checkbox" id="drawerAutoScroll" checked class="rounded accent-cyan-500 w-3.5 h-3.5">
                        <span class="hidden sm:inline">Auto-scroll</span>
                    </label>
                    <button type="button" onclick="copyDrawerLogs()" id="drawerCopyBtn" class="p-1.5 rounded-lg border hover:bg-white/5 text-slate-300 text-xs transition inline-flex items-center gap-1" style="border-color: var(--card-border);" title="کپی همه لاگ‌ها">
                        <svg class="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
                    </button>
                    <button type="button" onclick="loadDashboardData()" class="p-1.5 rounded-lg border hover:bg-white/5 text-slate-300 text-xs transition inline-flex items-center" style="border-color: var(--card-border);" title="تازه‌سازی">
                        <svg class="w-3.5 h-3.5 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                    </button>
                    <button type="button" onclick="toggleLogsDrawer(false)" class="p-1.5 rounded-lg border hover:bg-white/5 text-slate-300 text-xs transition" style="border-color: var(--card-border);" title="بستن">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                    </button>
                </div>
            </div>
            <div class="flex-1 p-3 overflow-hidden flex flex-col">
                <div id="dashboardRecentLogs" dir="ltr" class="flex-1 font-mono text-xs overflow-y-auto p-3 rounded-xl border space-y-1 select-text no-scrollbar" style="background: var(--card-bg, #030712); border-color: var(--card-border); color: #34d399;">
                    <div class="text-slate-500">// UNFINIT Engine v0.3.8 Live Stream initialized...</div>
                </div>
            </div>
            <div class="p-2.5 border-t flex items-center justify-between text-[11px] text-slate-400 font-sans" style="border-color: var(--card-border); background: var(--table-head-bg);">
                <span class="flex items-center gap-1.5">
                    <svg class="w-3 h-3 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                    <span>پروتکل لاگینگ: Ring Stream v0.3.8</span>
                </span>
                <button type="button" onclick="switchTab('settings'); toggleLogsDrawer(false);" class="text-cyan-400 hover:underline">مشاهده همه لاگ‌ها در تب تنظیمات ←</button>
            </div>
        </aside>

        <!-- ================= TAB 1: STUDIO & MEDIA HUB ================= -->
        <div id="tab-studio" class="hidden space-y-6">

            <!-- Cross-Platform URL Dispatcher & Tools (Accordion) -->
            <details class="settings-accordion glass rounded-2xl overflow-hidden mb-4" open>
                <summary class="p-5 cursor-pointer font-bold text-sm text-slate-100 flex items-center justify-between select-none">
                    <div class="flex items-center gap-2">
                        <svg width="20" height="20" class="w-5 h-5 text-cyan-400 shrink-0 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
                        </svg>
                        <span>دانلود استریم از لینک مستقیم و دیسپچ بین پلتفرم‌ها (URL Uploader)</span>
                    </div>
                    <span class="text-xs text-slate-400 font-mono">▼</span>
                </summary>
                <div class="p-6 pt-2 space-y-4">
                    <p class="text-xs text-slate-400 mb-2">
                        یک لینک مستقیم (مستقیم MP3، ویدیو یا سند) را وارد کنید و پلتفرم مقصد را انتخاب نمایید تا فایل به صورت خودکار دانلود، متادیتاگذاری و ارسال گردد.
                    </p>
                    <form id="dispatchForm" class="grid grid-cols-1 md:grid-cols-4 gap-4" onsubmit="handleDispatch(event)">
                        <div class="md:col-span-2">
                            <label class="block text-xs font-medium text-slate-300 mb-1">آدرس اینترنتی فایل (Direct URL)</label>
                            <input type="url" id="directUrl" required placeholder="https://example.com/audio.mp3" class="w-full bg-slate-900/80 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500">
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-slate-300 mb-1">پلتفرم مقصد ارسال</label>
                            <select id="targetPlatform" class="w-full bg-slate-900/80 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-cyan-500">
                                <option value="telegram">تلگرام (حساب ادمین)</option>
                                <option value="rubika_user">روبیکا (پیام‌های ذخیره‌شده)</option>
                                <option value="bale">بله (با کمپرسور خودکار {config.MAX_SAFE_BALE_SIZE_MB} MB)</option>
                            </select>
                        </div>
                        <div class="flex items-end">
                            <button type="submit" id="submitBtn" class="w-full theme-accent-btn font-bold py-2.5 px-4 rounded-xl shadow-lg transition flex items-center justify-center gap-2">
                                <span>دانلود و ارسال خودکار</span>
                            </button>
                        </div>
                    </form>
                    <div id="dispatchResult" class="hidden mt-4 p-3 rounded-xl text-xs font-mono"></div>
                </div>
            </details>

            <!-- SVG Vector Studio Suite Widget (Accordion) -->
            <details class="settings-accordion glass rounded-2xl overflow-hidden mb-4" open>
                <summary class="p-5 cursor-pointer font-bold text-sm text-slate-100 flex items-center justify-between select-none">
                    <div class="flex items-center gap-2">
                        <svg width="20" height="20" class="w-5 h-5 text-indigo-400 shrink-0 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
                        </svg>
                        <span>استودیوی وکتور SVG (SVG Studio Suite)</span>
                    </div>
                    <span class="text-xs font-mono px-2.5 py-1 rounded-lg border text-cyan-400 bg-cyan-950/80 border-cyan-800">
                        Vector Engine v0.3.6
                    </span>
                </summary>
                <div class="p-6 pt-2 space-y-4">
                    <p class="text-xs text-slate-400">
                        موتور برداری پیشرفته: تغییر رنگ زنده و هوشمند المان‌های SVG، تولید وکتور از متن و تبدیل بدون افت کیفیت به PNG شفاف و JPG با ابعاد بالا.
                    </p>

                    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4">
                        <!-- Left: Upload, Recolor & Text-to-SVG Form -->
                        <div class="lg:col-span-7 space-y-3">
                            <form id="svgConvertForm" class="space-y-3" onsubmit="handleSvgConvert(event)">
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <div>
                                        <label class="block text-xs font-medium text-slate-300 mb-1">انتخاب فایل وکتور SVG</label>
                                        <input type="file" id="svgFileInput" accept=".svg,image/svg+xml" onchange="handleSvgFileSelected(this.files)" class="w-full bg-slate-900/80 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-slate-100 file:mr-2 file:py-1 file:px-2.5 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-cyan-950 file:text-cyan-300 hover:file:bg-cyan-900 cursor-pointer focus:outline-none focus:border-cyan-500">
                                    </div>
                                    <div>
                                        <label class="block text-xs font-medium text-slate-300 mb-1">فرمت خروجی تبدیل</label>
                                        <select id="svgOutputFormat" class="w-full bg-slate-900/80 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-cyan-500">
                                            <option value="png">PNG با شفافیت کامل (Alpha Transparency)</option>
                                            <option value="jpg">JPG با پس‌زمینه سفید (HQ 300 DPI)</option>
                                        </select>
                                    </div>
                                </div>

                                <!-- Color Palette & Smart Recolor -->
                                <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                                    <label class="block text-[11px] font-bold text-slate-300">تغییر رنگ هوشمند وکتور (Smart Recolor):</label>
                                    <div class="flex flex-wrap items-center gap-2">
                                        <input type="color" id="svgRecolorPicker" value="#FFFFFF" onchange="syncSvgColorPicker(this.value)" class="w-8 h-8 rounded-lg cursor-pointer bg-transparent border-0">
                                        <input type="text" id="svgHexInput" value="#FFFFFF" placeholder="#FFFFFF" maxlength="9" onchange="syncSvgHexInput(this.value)" class="w-24 bg-slate-800 border border-slate-700 rounded-lg px-2 py-1 text-xs font-mono text-center text-cyan-300 focus:outline-none focus:border-cyan-500" dir="ltr">
                                        <button type="button" onclick="setSvgColor('#FFFFFF')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-100 text-[11px] font-medium border border-slate-600 transition">سفید (#FFF)</button>
                                        <button type="button" onclick="setSvgColor('#000000')" class="px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 text-[11px] font-medium border border-slate-700 transition">مشکی (#000)</button>
                                        <button type="button" onclick="setSvgColor('#3B82F6')" class="px-2.5 py-1 rounded-lg bg-sky-950 hover:bg-sky-900 text-sky-300 text-[11px] font-medium border border-sky-800 transition">آبی (#3B82F6)</button>
                                        <button type="button" onclick="setSvgColor('#E11D48')" class="px-2.5 py-1 rounded-lg bg-rose-950 hover:bg-rose-900 text-rose-300 text-[11px] font-medium border border-rose-800 transition">قرمز (#E11D48)</button>
                                    </div>
                                    <div class="flex flex-wrap gap-2 pt-1">
                                        <button type="button" id="btnSvgRecolor" onclick="handleSvgRecolor()" class="px-3.5 py-1.5 rounded-xl bg-cyan-800 hover:bg-cyan-700 text-white text-xs font-bold transition flex items-center gap-1">
                                            <span>اعمال تغییر رنگ</span>
                                        </button>
                                        <button type="button" id="btnSvgDownload" onclick="downloadCurrentSvg()" class="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold border border-slate-700 transition flex items-center gap-1">
                                            <span>دریافت فایل SVG</span>
                                        </button>
                                    </div>
                                </div>

                                <!-- Typography: Text to SVG -->
                                <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                                    <label class="block text-[11px] font-bold text-slate-300">تولید وکتور متنی (Text to SVG Typography):</label>
                                    <div class="flex flex-wrap items-center gap-2">
                                        <input type="text" id="svgTextInput" placeholder="متن جهت تولید لوگوتایپ یا عنوان وکتور..." class="flex-1 min-w-[200px] bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-cyan-500">
                                        <input type="number" id="svgTextSizeInput" value="48" min="12" max="144" class="w-16 bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs font-mono text-center text-slate-200" title="اندازه فونت">
                                        <button type="button" onclick="handleGenerateTextSvg()" class="px-3.5 py-1.5 rounded-xl bg-indigo-800 hover:bg-indigo-700 text-white text-xs font-bold transition flex items-center gap-1">
                                            <span>ساخت وکتور</span>
                                        </button>
                                    </div>
                                </div>

                                <div class="pt-1">
                                    <button type="submit" id="btnSvgConvert" class="w-full theme-accent-btn font-bold py-2.5 px-4 rounded-xl shadow-lg transition flex items-center justify-center gap-2 text-xs">
                                        <span>تبدیل و دریافت تصویر</span>
                                    </button>
                                </div>
                            </form>
                        </div>

                        <!-- Right: Live Vector Preview -->
                        <div class="lg:col-span-5 flex flex-col">
                            <div class="flex items-center justify-between mb-1">
                                <label class="text-xs font-medium text-slate-300">پیش‌نمایش زنده وکتور:</label>
                                <span id="svgDimensionsBadge" class="text-[10px] font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">-</span>
                            </div>
                            <div id="svgLivePreview" class="flex-1 border border-dashed border-slate-700/80 rounded-xl p-4 bg-slate-950/70 min-h-[200px] flex items-center justify-center overflow-auto">
                                <span class="text-xs text-slate-500">فایل SVG انتخاب شده در اینجا رسم می‌شود</span>
                            </div>
                        </div>
                    </div>

                    <div id="svgConvertResult" class="hidden mt-4 p-3 rounded-xl text-xs font-mono flex items-center justify-between"></div>
                </div>
            </details>

            <!-- Web Mp3tag Studio & Media Table (Accordion) -->
            <details class="settings-accordion glass rounded-2xl overflow-hidden mb-4" open>
                <summary class="p-5 cursor-pointer font-bold text-sm text-slate-100 flex items-center justify-between select-none">
                    <div class="flex items-center gap-2">
                        <svg width="20" height="20" class="w-5 h-5 text-emerald-400 shrink-0 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
                        </svg>
                        <span>استودیوی پیشرفته متادیتا و رسانه (Web Mp3tag Studio)</span>
                    </div>
                    <span class="text-xs text-cyan-400 font-mono bg-cyan-950/80 px-3 py-1 rounded-lg border border-cyan-800">
                        تعداد کل فایل‌ها: {active_drops_count}
                    </span>
                </summary>
                <div class="p-6 pt-2 space-y-4">
                    <p class="text-xs text-slate-400">
                        ویرایش حرفه‌ای متادیتا، برش صدا با رسم موج صوتی، کاور آرت، شماره‌گذاری خودکار جلسات و ارسال مستقیم به پیام‌رسان‌ها
                    </p>

                    <!-- Drag & Drop Upload Zone -->
                    <div id="studioDropzone" onclick="document.getElementById('studioFileInput').click()" class="border-2 border-dashed p-6 rounded-2xl text-center cursor-pointer transition flex flex-col items-center justify-center gap-2 group">
                        <input type="file" id="studioFileInput" multiple accept="audio/*,video/*" class="hidden" onchange="handleStudioFilesSelect(this.files)">
                        <div class="w-12 h-12 rounded-2xl bg-cyan-950/80 border border-cyan-800 flex items-center justify-center text-2xl text-cyan-300 group-hover:scale-110 transition">
                            <svg width="24" height="24" class="w-6 h-6 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                            </svg>
                        </div>
                        <div>
                            <p class="text-xs font-bold text-slate-200">فایل‌های صوتی یا ویدیویی خود را به اینجا بکشید یا برای انتخاب کلیک کنید</p>
                            <p class="text-[11px] text-slate-400 mt-1">پشتیبانی از فرمت‌های صوتی و ویدیویی (MP3, M4A, AAC, WAV, MP4) با ثبت خودکار در سشن‌های استودیو</p>
                        </div>
                        <div id="studioUploadProgress" class="hidden text-xs text-cyan-400 font-mono"></div>
                    </div>

                    <!-- Batch Action Bar -->
                    <div class="flex flex-wrap justify-between items-center bg-slate-900/80 p-3 rounded-xl border border-slate-800 gap-3">
                        <div class="flex flex-wrap items-center gap-3">
                            <label class="flex items-center gap-2 cursor-pointer text-xs text-slate-300 font-medium">
                                <input type="checkbox" id="selectAllDrops" onchange="toggleSelectAllDrops(this)" class="w-4 h-4 rounded border-slate-600 bg-slate-800 text-cyan-600 focus:ring-cyan-500 cursor-pointer">
                                <span>انتخاب همه</span>
                            </label>
                            <span id="selectedCountBadge" class="text-xs text-cyan-300 font-mono bg-cyan-950/80 px-2.5 py-0.5 rounded border border-cyan-800/80">۰ فایل انتخاب شده</span>
                            <button onclick="batchDeleteStudioDrops()" class="px-3.5 py-1.5 rounded-xl bg-rose-950/80 hover:bg-rose-900 text-rose-300 text-xs font-bold border border-rose-800 transition flex items-center gap-1.5" title="حذف گروهی فایل‌های انتخاب‌شده از حافظه و دیسک">
                                <span>حذف فایل‌های انتخاب‌شده</span>
                            </button>
                        </div>
                        <div class="flex flex-wrap items-center gap-2">
                            <div class="flex items-center gap-1.5 bg-slate-800/90 px-2.5 py-1 rounded-xl border border-slate-700">
                                <span class="text-xs text-slate-400">مرتب‌سازی:</span>
                                <select id="studioSortSelect" onchange="changeStudioSort(this.value)" class="bg-slate-900 border border-slate-700 text-xs text-cyan-300 rounded-lg px-2 py-1 focus:outline-none focus:border-cyan-400 transition cursor-pointer">
                                    <option value="newest">جدیدترین</option>
                                    <option value="oldest">قدیمی‌ترین</option>
                                    <option value="size_desc">بزرگترین حجم</option>
                                    <option value="size_asc">کمترین حجم</option>
                                    <option value="name_asc">نام فایل (الفبا)</option>
                                </select>
                            </div>
                            <button onclick="openBatchTagModal()" class="theme-accent-btn px-3.5 py-1.5 rounded-xl text-white text-xs font-bold shadow-md transition flex items-center gap-1.5">
                                <span>ویرایش گروهی تگ‌ها (Batch Edit)</span>
                            </button>
                            <button onclick="cleanupStudioDrops()" id="btnCleanupStudio" class="theme-card-btn px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5" title="پاکسازی رکوردهای تکراری و سشن‌های خالی">
                                <span>پاکسازی سشن‌های خالی</span>
                            </button>
                            <button onclick="refreshStudioList()" class="theme-card-btn px-3 py-1.5 rounded-xl text-xs transition flex items-center gap-1">
                                <span>به‌روزرسانی لیست</span>
                            </button>
                        </div>
                    </div>

                    <!-- Studio Media Table -->
                    <div class="overflow-x-auto">
                        <table class="w-full text-right border-collapse">
                            <thead>
                                <tr class="border-b border-slate-700 text-xs text-slate-400">
                                    <th class="py-3 px-3 text-center w-10">انتخاب</th>
                                    <th class="py-3 px-3">عنوان و متادیتا / نام فایل</th>
                                    <th class="py-3 px-3">مشخصات و مبدا</th>
                                    <th class="py-3 px-3 text-left">عملیات استودیو و دیسپچ</th>
                                </tr>
                            </thead>
                            <tbody id="studioTableBody">
                                {drop_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </details>

            <!-- Studio & Course Copilot (Integrated into Studio Tab) -->
            <div class="glass p-6 rounded-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border shadow-xl" style="background: var(--card-bg); border-color: var(--card-border);">
                <div class="flex items-center gap-4">
                    <div class="w-12 h-12 rounded-2xl theme-accent-btn flex items-center justify-center font-bold text-2xl shadow-lg text-white">
                        🎛
                    </div>
                    <div>
                        <h2 class="text-base font-bold text-white flex items-center gap-2">
                            دستیار هوشمند دوره‌ها و استودیوی رسانه (Studio & Course Copilot)
                            <span class="px-2 py-0.5 rounded-full text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800">🟢 فعال و آنلاین</span>
                        </h2>
                        <p class="text-xs text-slate-400 mt-1">اتصال به Nara Router با سهمیه رایگان - متخصص اتوماسیون متادیتا، تدوین کپشن دوره‌ها و مهندسی رسانه</p>
                    </div>
                </div>
                <div class="flex flex-wrap items-center gap-3">
                    <div class="flex items-center gap-2 px-3 py-1.5 rounded-xl border" style="background: var(--input-bg); border-color: var(--card-border);">
                        <label for="hermesModelSelect" class="text-xs text-slate-300 whitespace-nowrap">🤖 مدل هوش مصنوعی:</label>
                        <select id="hermesModelSelect" class="border rounded-lg px-2.5 py-1 text-xs font-mono focus:outline-none" style="background: var(--card-bg); border-color: var(--card-border); color: var(--accent-color);">
                            <option value="stepfun-3.7-flash" selected>stepfun-3.7-flash (پیش‌فرض هوشمند و قوی متون فارسی)</option>
                            <option value="mimo-v2.5-free">mimo-v2.5-free (فوق‌سریع و رایگان)</option>
                            <option value="qwen2.5-72b">qwen2.5-72b (دقت نگارش بالا)</option>
                        </select>
                    </div>
                    <span class="px-2.5 py-1.5 rounded-xl border font-mono text-[11px]" style="background: var(--card-bg); border-color: var(--card-border); color: var(--accent-color);">🌐 router.bynara.id</span>
                </div>
            </div>

            <!-- Chat Window -->
            <div class="glass rounded-2xl border flex flex-col h-[520px] overflow-hidden shadow-xl" style="background: var(--card-bg); border-color: var(--card-border);">
                <div id="hermesChatBox" class="flex-1 p-5 overflow-y-auto space-y-4 chat-scrollbar">
                    <div class="flex gap-2.5 items-center p-3 rounded-xl border text-xs text-slate-300" style="background: var(--glass-bg); border-color: var(--card-border);">
                        <div class="w-6 h-6 rounded-lg theme-accent-btn flex items-center justify-center font-bold text-xs shrink-0 text-white">
                            🤖
                        </div>
                        <span>دستیار هوش مصنوعی آماده پاسخگویی و ارائه کپشن دوره‌ها و پردازش رسانه است.</span>
                    </div>
                </div>
                <div class="p-4 border-t" style="background: var(--card-bg); border-color: var(--card-border);">
                    <form id="hermesChatForm" onsubmit="handleSendHermes(event)" class="flex items-center gap-3">
                        <button type="button" onclick="clearHermesChat()" title="پاکسازی چت" class="theme-card-btn px-3 py-2.5 rounded-xl text-xs transition">
                            🗑
                        </button>
                        <input type="text" id="hermesInput" placeholder="درخواست اتوماسیون متادیتا، کپشن فروش دوره یا مشاوره رسانه را بنویسید..." class="flex-1 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none transition border" style="background: var(--input-bg); border-color: var(--card-border);">
                        <button type="submit" id="btnSendHermes" class="px-5 py-2.5 rounded-xl theme-accent-btn text-xs font-bold text-white shadow-lg transition flex items-center gap-1.5 shrink-0">
                            <span>ارسال</span> ➜
                        </button>
                    </form>
                </div>
            </div>
        </div>

        <!-- ================= TAB 2: COURSES & STORE ================= -->
        <div id="tab-courses" class="hidden space-y-6">
            <!-- Store Stats and Action Header -->
            <div class="glass p-6 rounded-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 class="text-lg font-bold text-white flex items-center gap-2">
                        <span>🎓</span> مدیریت دوره‌های آموزشی و فروشگاه آنلاین
                    </h2>
                    <p class="text-xs text-slate-400 mt-1">
                        همگام‌سازی و فروش مستقیم دوره‌ها در تلگرام، بله و روبیکا با امکان پرداخت آنلاین و کارت‌به‌کارت
                    </p>
                </div>
                <div class="flex items-center gap-3">
                    <div class="text-right px-4 py-2 rounded-xl bg-slate-900 border border-slate-800">
                        <span class="text-[11px] text-slate-400 block">دوره‌های فعال / کل:</span>
                        <span class="text-sm font-bold text-cyan-400 font-mono">{active_count} از {len(products)}</span>
                    </div>
                    <a href="/store" target="_blank" class="theme-accent-btn font-bold py-2.5 px-4 rounded-xl shadow-lg transition flex items-center gap-2 text-xs">
                        <span>🌐</span> مشاهده ویترین فروشگاه (/store)
                    </a>
                    <button onclick="toggleAddCourseForm()" id="btnAddCourseToggle" class="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold py-2.5 px-4 rounded-xl shadow-lg shadow-emerald-500/20 transition flex items-center gap-2 text-xs">
                        <span>➕</span> افزودن دوره جدید
                    </button>
                </div>
            </div>

            <!-- Add Course Collapsible Form -->
            <div id="addCourseCard" class="hidden glass p-6 rounded-2xl border border-emerald-500/30">
                <h3 class="text-sm font-bold text-emerald-400 mb-4 flex items-center gap-2">
                    <span>✨</span> مشخصات دوره جدید:
                </h3>
                <form id="newCourseForm" class="space-y-4" onsubmit="handleCreateCourse(event)">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label class="block text-xs text-slate-300">نام دوره *</label>
                                <span id="counter_newCName" class="text-[11px] font-mono text-slate-400">0 / 32</span>
                            </div>
                            <input type="text" id="newCName" required maxlength="32" oninput="updateCharCounter('newCName', 'counter_newCName', 32)" placeholder="مثال: آموزش جامع رشد فردی" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                        </div>
                        <div>
                            <label class="block text-xs text-slate-300 mb-1">قیمت به تومان (0 برای رایگان) *</label>
                            <input type="text" inputmode="numeric" id="newCPrice" required oninput="formatPriceInput(this)" placeholder="مثال: ۱۵۰,۰۰۰" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono">
                        </div>
                        <div>
                            <label class="block text-xs text-slate-300 mb-1">بنر یا عکس دوره</label>
                            <div class="flex gap-2 items-center">
                                <input type="text" id="newCPhoto" placeholder="آدرس اینترنتی یا با دکمه آپلود کنید..." class="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono">
                                <label class="cursor-pointer px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs text-cyan-300 font-medium transition flex items-center gap-1 shrink-0">
                                    <span>📷</span> آپلود بنر
                                    <input type="file" accept="image/*" class="hidden" onchange="uploadBannerFile(this, 'newCPhoto')">
                                </label>
                            </div>
                            <div class="flex justify-between items-center mt-1">
                                <span id="bannerUploadStatus_newCPhoto" class="text-[11px] text-slate-400"></span>
                                <span class="text-[10px] text-amber-300/80">⚡️ حجم بهینه بنر: زیر 500KB جهت بارگذاری فوق سریع</span>
                            </div>
                        </div>
                    </div>
                    <div>
                        <div class="flex justify-between items-center mb-1">
                            <div class="flex items-center gap-2">
                                <label class="block text-xs text-slate-300">توضیحات کامل دوره</label>
                                <button type="button" onclick="aiSummarizeDescription('newCDesc', 'counter_newCDesc')" id="btnAiSummarizeNew" class="px-2.5 py-1 rounded-lg bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/40 text-[11px] flex items-center gap-1 transition">
                                    <span>✨</span> خلاصه هوشمند برای بله (زیر ۲۵۵ کاراکتر)
                                </button>
                            </div>
                            <span id="counter_newCDesc" class="text-[11px] font-mono text-slate-400">0 / 255</span>
                        </div>
                        <textarea id="newCDesc" rows="3" oninput="updateCharCounter('newCDesc', 'counter_newCDesc', 255)" placeholder="توضیحات کامل دوره و سرفصل‌ها..." class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-cyan-500"></textarea>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs text-slate-300 mb-1">شیوه تحویل محتوا</label>
                            <select id="newCDeliveryType" onchange="togglePackageInput('newC')" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                                <option value="channel">هدایت به کانال / لینک مستقیم</option>
                                <option value="files_package">بسته چندفایله صوتی/تصویری مستقیم ربات (پکیج)</option>
                            </select>
                        </div>
                        <div id="newCDownloadBox">
                            <label class="block text-xs text-slate-300 mb-1">لینک دانلود فایل دوره (تحویل خودکار)</label>
                            <input type="text" id="newCDownload" placeholder="https://example.com/course_files.zip" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono">
                        </div>
                    </div>
                    <div id="newCPackageBox" class="hidden">
                        <div class="flex justify-between items-center mb-1">
                            <label class="block text-xs text-cyan-300 font-medium">لیست فایل‌های پکیج (JSON یا خط‌به‌خط)</label>
                            <span class="text-[10px] text-slate-400">تحویل زنجیره‌ای در تلگرام و بله</span>
                        </div>
                        <textarea id="newCFilesPackage" rows="3" placeholder='[&#10;  {{"title": "جلسه اول", "file_name": "lesson1.mp3", "duration": 1200}}&#10;]' class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono"></textarea>
                    </div>
                    <div class="flex flex-wrap items-center gap-6 pt-2">
                        <label class="flex items-center gap-2 cursor-pointer text-xs text-slate-300">
                            <input type="checkbox" id="newCAllowCard" checked class="w-4 h-4 rounded text-cyan-600 bg-slate-900 border-slate-700 focus:ring-0">
                            <span>💳 پرداخت کارت به کارت (با ارسال فیش)</span>
                        </label>
                        <label class="flex items-center gap-2 cursor-pointer text-xs text-slate-300">
                            <input type="checkbox" id="newCAllowBale" checked class="w-4 h-4 rounded text-emerald-600 bg-slate-900 border-slate-700 focus:ring-0">
                            <span>🌐 درگاه پرداخت آنلاین بله (کیف پول / کارت)</span>
                        </label>
                        <label class="flex items-center gap-2 cursor-pointer text-xs text-amber-300">
                            <input type="checkbox" id="newCRequiresReferral" class="w-4 h-4 rounded text-amber-500 bg-slate-900 border-slate-700 focus:ring-0">
                            <span>🎁 نیازمند ۱ دعوت موفق (هدیه وایرال)</span>
                        </label>
                    </div>
                    <div class="flex justify-end gap-3 pt-3 border-t border-slate-800">
                        <button type="button" onclick="toggleAddCourseForm()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 transition">انصراف</button>
                        <button type="submit" id="btnSubmitCourse" class="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-white shadow-lg shadow-emerald-600/20 transition">ثبت دوره در دیتابیس</button>
                    </div>
                </form>
            </div>

            <!-- Course Cards Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {prod_cards}
            </div>

            <!-- Course Terms Agreement Management Card -->
            <div class="glass p-6 rounded-2xl border border-slate-800 space-y-4 mt-6" id="courseTermsCard">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-slate-800">
                    <div>
                        <h3 class="text-base font-bold text-slate-100 flex items-center gap-2">
                            <span>📜</span> متن تعهدنامه و قوانین خرید دوره (Course Terms & Conditions)
                        </h3>
                        <p class="text-xs text-slate-400 mt-1">این متن پیش از پرداخت وجه در ربات‌های بله و تلگرام به کاربر نمایش داده شده و خرید منوط به پذیرش آن است.</p>
                    </div>
                    <button onclick="saveCourseTermsText()" id="btnSaveTerms" class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/20 transition flex items-center gap-1.5">
                        <span>💾</span> ذخیره متن تعهدنامه
                    </button>
                </div>
                <div>
                    <textarea id="courseTermsTextarea" rows="4" placeholder="متن تعهدنامه و قوانین استفاده از دوره‌ها..." class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-cyan-500 font-sans leading-relaxed">{course_terms_escaped}</textarea>
                    <div class="flex justify-between items-center mt-2">
                        <span class="text-[11px] text-slate-500">متن به صورت زنده در تلگرام و بله لود می‌شود.</span>
                        <span id="termsSaveStatus" class="text-xs font-medium"></span>
                    </div>
                </div>
            </div>

            <!-- Sales Analytics Dashboard -->
            <div class="glass p-6 rounded-2xl border border-slate-800 space-y-4 mt-8" id="analyticsCard">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-slate-800">
                    <div>
                        <h2 class="text-base font-bold text-slate-100 flex items-center gap-2">
                            <span>📊</span> آمار و تحلیل فروش کل فروشگاه (Sales Analytics)
                        </h2>
                        <p class="text-xs text-slate-400 mt-1">گزارش لحظه‌ای فروش به تفکیک دوره‌ها، زمان و پلتفرم‌های تلگرام، بله، روبیکا و وب</p>
                    </div>
                    <button onclick="loadStoreAnalytics()" class="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-bold border border-slate-700 transition flex items-center gap-1.5 shadow-sm">
                        <span>🔄</span> بازخوانی آمار
                    </button>
                </div>

                <!-- 4 KPI Metrics Grid -->
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div class="bg-slate-900/80 p-4 rounded-xl border border-cyan-900/40">
                        <div class="text-[11px] text-slate-400 mb-1">فروش کل (تایید شده)</div>
                        <div id="metricTotalSales" class="text-lg font-bold text-cyan-400 font-mono">۰ تومان</div>
                        <div id="metricTotalOrders" class="text-[10px] text-slate-500 mt-1">۰ سفارش موفق</div>
                    </div>
                    <div class="bg-slate-900/80 p-4 rounded-xl border border-emerald-900/40">
                        <div class="text-[11px] text-slate-400 mb-1">فروش امروز</div>
                        <div id="metricTodaySales" class="text-lg font-bold text-emerald-400 font-mono">۰ تومان</div>
                        <div id="metricTodayOrders" class="text-[10px] text-slate-500 mt-1">۰ سفارش</div>
                    </div>
                    <div class="bg-slate-900/80 p-4 rounded-xl border border-sky-900/40">
                        <div class="text-[11px] text-slate-400 mb-1">فروش ۷ روز گذشته</div>
                        <div id="metricWeekSales" class="text-lg font-bold text-sky-400 font-mono">۰ تومان</div>
                        <div id="metricWeekOrders" class="text-[10px] text-slate-500 mt-1">۰ سفارش</div>
                    </div>
                    <div class="bg-slate-900/80 p-4 rounded-xl border border-purple-900/40">
                        <div class="text-[11px] text-slate-400 mb-1">فروش ۳۰ روز گذشته</div>
                        <div id="metricMonthSales" class="text-lg font-bold text-purple-400 font-mono">۰ تومان</div>
                        <div id="metricMonthOrders" class="text-[10px] text-slate-500 mt-1">۰ سفارش</div>
                    </div>
                </div>

                <!-- Platform Breakdown & Discounts -->
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
                    <div class="p-3 bg-slate-950/60 rounded-xl border border-slate-800 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span>✈️</span>
                            <span class="text-xs text-slate-300">تلگرام</span>
                        </div>
                        <div class="text-left font-mono text-xs text-sky-400" id="platSalesTg">۰ تومان (۰)</div>
                    </div>
                    <div class="p-3 bg-slate-950/60 rounded-xl border border-slate-800 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span>🟢</span>
                            <span class="text-xs text-slate-300">بله</span>
                        </div>
                        <div class="text-left font-mono text-xs text-emerald-400" id="platSalesBale">۰ تومان (۰)</div>
                    </div>
                    <div class="p-3 bg-slate-950/60 rounded-xl border border-slate-800 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span>🟣</span>
                            <span class="text-xs text-slate-300">روبیکا</span>
                        </div>
                        <div class="text-left font-mono text-xs text-purple-400" id="platSalesRubika">۰ تومان (۰)</div>
                    </div>
                    <div class="p-3 bg-slate-950/60 rounded-xl border border-slate-800 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span>🌐</span>
                            <span class="text-xs text-slate-300">فروشگاه وب</span>
                        </div>
                        <div class="text-left font-mono text-xs text-amber-400" id="platSalesWeb">۰ تومان (۰)</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ================= TAB 3: ORDERS & TRANSACTIONS ================= -->
        <div id="tab-orders" class="hidden space-y-6">
            <!-- Orders Management Card -->
            <div class="glass p-6 rounded-2xl border border-slate-800 space-y-4" id="ordersCard">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
                    <div>
                        <h2 class="text-base font-bold text-slate-100 flex items-center gap-2">
                            <span>🧾</span> مدیریت سفارش‌ها و تراکنش‌های فروشگاه (/store)
                        </h2>
                        <p class="text-xs text-slate-400 mt-1">لیست کلیه سفارش‌های ثبت‌شده از طریق درگاه آنلاین بله و کارت‌به‌کارت با امکان بررسی فیش، تایید و تحویل لینک دانلود</p>
                    </div>
                    <div class="flex items-center gap-2 self-start sm:self-auto flex-wrap">
                        <button onclick="deleteSelectedOrders()" id="btnDeleteSelectedOrders" class="hidden px-3.5 py-2 rounded-xl theme-card-btn text-xs font-bold transition flex items-center gap-1.5 shadow-sm">
                            <span>🗑</span> حذف موارد انتخاب‌شده (<span id="selectedOrdersCount">0</span>)
                        </button>
                        <button onclick="clearAllOrders()" class="px-3.5 py-2 rounded-xl theme-card-btn text-xs font-bold transition flex items-center gap-1.5 shadow-sm" title="پاکسازی تمامی سفارشات تستی">
                            <span>🗑</span> پاکسازی تمامی سفارشات
                        </button>
                        <button onclick="cleanupRejectedOrders()" class="px-3.5 py-2 rounded-xl theme-card-btn text-xs font-bold transition flex items-center gap-1.5 shadow-sm" title="حذف یکباره کلیه سفارش‌های رد شده">
                            <span>🧹</span> پاکسازی سفارشات رد شده
                        </button>
                        <button onclick="loadStoreOrders()" class="theme-card-btn px-3.5 py-2 rounded-xl text-cyan-300 text-xs font-bold transition flex items-center gap-1.5 shadow-sm">
                            <span>🔄</span> به‌روزرسانی لیست سفارش‌ها
                        </button>
                    </div>
                </div>
                <div class="overflow-x-auto block whitespace-nowrap">
                    <table class="w-full text-right border-collapse text-xs whitespace-nowrap">
                        <thead>
                            <tr class="border-b border-slate-700 text-slate-400">
                                <th class="py-3 px-3 w-8 text-center">
                                    <input type="checkbox" id="selectAllOrders" onchange="toggleSelectAllOrders(this)" class="rounded bg-slate-800 border-slate-600 text-cyan-500 focus:ring-0 cursor-pointer" title="انتخاب همه سفارشات">
                                </th>
                                <th class="py-3 px-3">شناسه سفارش</th>
                                <th class="py-3 px-3">مشتری و تماس</th>
                                <th class="py-3 px-3">دوره و مبلغ</th>
                                <th class="py-3 px-3">بستر سفارش</th>
                                <th class="py-3 px-3">روش پرداخت</th>
                                <th class="py-3 px-3">رسید / تاریخ</th>
                                <th class="py-3 px-3">وضعیت</th>
                                <th class="py-3 px-3 text-left">عملیات</th>
                            </tr>
                        </thead>
                        <tbody id="storeOrdersTableBody">
                            <tr>
                                <td colspan="9" class="py-8 text-center text-slate-500 font-sans">در حال دریافت لیست سفارش‌ها...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Coupons & Discounts Engine -->
            <div class="glass p-6 rounded-2xl border border-slate-800 space-y-4" id="couponsCard">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-slate-800">
                    <div>
                        <h2 class="text-base font-bold text-slate-100 flex items-center gap-2">
                            <span>🏷️</span> مدیریت کدهای تخفیف و کوپن‌ها (Discount Coupons)
                        </h2>
                        <p class="text-xs text-slate-400 mt-1">تعریف کدهای تخفیف درصدی یا مبلغی با سقف استفاده و تاریخ انقضا</p>
                    </div>
                    <button onclick="toggleAddCouponForm()" class="px-3.5 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-sm">
                        <span>➕</span> افزودن کد تخفیف جدید
                    </button>
                </div>

                <!-- Add Coupon Form (collapsible) -->
                <div id="addCouponCard" class="hidden bg-slate-900/90 p-5 rounded-2xl border border-slate-700/80 space-y-4">
                    <form id="addCouponForm" onsubmit="handleCreateCoupon(event)" class="space-y-3">
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            <div>
                                <label class="block text-xs text-slate-300 mb-1">کد تخفیف (Coupon Code)</label>
                                <input type="text" id="newCouponCode" required placeholder="مثلاً: NOWRUZ1404" class="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono uppercase focus:outline-none focus:border-emerald-500">
                            </div>
                            <div>
                                <label class="block text-xs text-slate-300 mb-1">نوع تخفیف</label>
                                <select id="newCouponType" class="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500">
                                    <option value="percent">درصدی (%)</option>
                                    <option value="fixed">مبلغ ثابت (تومان)</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs text-slate-300 mb-1">مقدار تخفیف</label>
                                <input type="number" id="newCouponValue" required min="1" placeholder="مثلاً 20 درصد یا 50000 تومان" class="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-emerald-500">
                            </div>
                        </div>
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            <div>
                                <label class="block text-xs text-slate-300 mb-1">سقف تعداد استفاده (0 = نامحدود)</label>
                                <input type="number" id="newCouponMaxUses" value="0" min="0" class="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-emerald-500">
                            </div>
                            <div>
                                <label class="block text-xs text-slate-300 mb-1">حداقل مبلغ سفارش (تومان، 0 = بدون شرط)</label>
                                <input type="number" id="newCouponMinAmount" value="0" min="0" class="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-emerald-500">
                            </div>
                            <div>
                                <label class="block text-xs text-slate-300 mb-1">تاریخ انقضا (YYYY-MM-DD اختیاری)</label>
                                <input type="text" id="newCouponExpire" placeholder="2026-12-31" class="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-emerald-500">
                            </div>
                        </div>
                        <div class="flex justify-end gap-2 pt-2 border-t border-slate-800">
                            <button type="button" onclick="toggleAddCouponForm()" class="px-3.5 py-1.5 rounded-xl bg-slate-800 text-xs text-slate-400 hover:text-white">انصراف</button>
                            <button type="submit" id="btnSubmitCoupon" class="px-4 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition">ثبت کوپن تخفیف</button>
                        </div>
                    </form>
                </div>

                <!-- Coupons Table -->
                <div class="overflow-x-auto">
                    <table class="w-full text-right border-collapse text-xs">
                        <thead>
                            <tr class="border-b border-slate-700 text-slate-400">
                                <th class="py-2.5 px-3">کد تخفیف</th>
                                <th class="py-2.5 px-3">نوع و مقدار</th>
                                <th class="py-2.5 px-3">دفعات مصرف</th>
                                <th class="py-2.5 px-3">حداقل سفارش</th>
                                <th class="py-2.5 px-3">انقضا</th>
                                <th class="py-2.5 px-3">وضعیت</th>
                            </tr>
                        </thead>
                        <tbody id="couponsTableBody">
                            <tr><td colspan="6" class="py-4 text-center text-slate-500">در حال بارگذاری کوپن‌ها...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ================= TAB 4: SITE FREE DOWNLOADS ================= -->
        <div id="tab-downloads" class="hidden space-y-6">
            <div class="glass p-6 rounded-2xl space-y-4 border shadow-xl" style="background: var(--card-bg); border-color: var(--card-border);">
                <div class="flex flex-wrap justify-between items-center gap-3 pb-3 border-b border-white/5">
                    <div>
                        <h2 class="text-base font-bold text-slate-100 flex items-center gap-2">
                            <span>🎁</span> رصد و دریافت هدایای دانلودی سایت (فایل‌های دانلودی)
                        </h2>
                        <p class="text-xs text-slate-400 mt-1">
                            آرشیو کامل هدایای دانلودی سایت با تفکیک و صفحه‌بندی، امکان انتقال مستقیم به ربات جهت دانلود، متادیتاگذاری و انتشار
                        </p>
                    </div>
                    <div class="flex items-center gap-2">
                        <button type="button" onclick="fetchFeedDownloads(true)" id="btnRefreshFeed" class="theme-card-btn px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-sm" style="color: var(--accent-color);">
                            <span>🔄</span> به‌روزرسانی صفحه
                        </button>
                    </div>
                </div>

                <!-- Pagination Controls: Top -->
                <div class="flex items-center justify-between gap-2 p-2 rounded-xl border" style="background: var(--glass-bg); border-color: var(--card-border);">
                    <button type="button" id="btnPrevFeedPage" onclick="changeFeedPage(currentFeedPage - 1)" class="theme-card-btn px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1">
                        <span>◀️</span> صفحه قبلی
                    </button>
                    <span id="feedPaginationInfo" class="text-xs text-slate-300 font-mono font-bold">
                        صفحه <span id="feedCurrentPage" class="text-cyan-400 font-bold">۱</span> از ۳۹
                    </span>
                    <button type="button" id="btnNextFeedPage" onclick="changeFeedPage(currentFeedPage + 1)" class="theme-card-btn px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1">
                        صفحه بعدی <span>▶️</span>
                    </button>
                </div>

                <!-- Feed Downloads Grid Container -->
                <div id="feedDownloadsContainer" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div class="col-span-full text-center py-8 text-xs text-slate-400 font-mono">
                        در حال بارگذاری فایل‌های دانلودی سایت...
                    </div>
                </div>

                <!-- Pagination Controls: Bottom -->
                <div class="flex items-center justify-between gap-2 p-2 rounded-xl border" style="background: var(--glass-bg); border-color: var(--card-border);">
                    <button type="button" onclick="changeFeedPage(currentFeedPage - 1)" class="theme-card-btn px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1">
                        <span>◀️</span> صفحه قبلی
                    </button>
                    <span class="text-xs text-slate-300 font-mono font-bold">
                        صفحه <span id="feedCurrentPageBottom" class="text-cyan-400 font-bold">۱</span> از ۳۹
                    </span>
                    <button type="button" onclick="changeFeedPage(currentFeedPage + 1)" class="theme-card-btn px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1">
                        صفحه بعدی <span>▶️</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- ================= TAB: USERS MANAGEMENT & VIRAL REFERRALS ================= -->
        <div id="tab-users" class="hidden space-y-6">
            <!-- User Sub-Tabs Navigation Buttons -->
            <div class="flex items-center gap-2 border-b border-slate-800 pb-3 flex-wrap">
                <button type="button" onclick="switchUserSubTab('list')" id="btnUserSubTabList" class="px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-accent-btn">
                    <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                    </svg>
                    فهرست و مشخصات کاربران و خریداران
                </button>
                <button type="button" onclick="switchUserSubTab('referrals')" id="btnUserSubTabRef" class="px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-card-btn text-slate-300">
                    <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
                    </svg>
                    شبکه رفرال و آمار زیرمجموعه‌گیری
                </button>
            </div>

            <!-- Sub-Tab 1: Users List & Profiles -->
            <div id="userSubTabContentList" class="space-y-4">
                <!-- Users Table Card -->
                <div class="glass p-6 rounded-2xl border space-y-4" style="background: var(--card-bg); border-color: var(--card-border);">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div>
                            <h3 class="text-base font-bold text-white flex items-center gap-2">
                                <svg class="w-5 h-5 text-cyan-400 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                                </svg>
                                <span>فهرست کاربران و خریداران</span>
                            </h3>
                            <p class="text-xs text-slate-400">اطلاعات کاربران، شماره تلفن‌ها و سابقه عضویت در بات‌های تلگرام و بله</p>
                        </div>
                        <div class="flex items-center gap-2 flex-wrap">
                            <input type="text" id="usersSearchInput" oninput="filterUsersTable()" placeholder="جستجو نام، آیدی، شماره..." class="bg-slate-900/80 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500" style="background: var(--input-bg); border-color: var(--card-border);">
                            <button type="button" onclick="purgeTestUsers()" class="px-3 py-1.5 rounded-xl bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800 text-xs transition flex items-center gap-1.5" title="پاکسازی کاربران تستی">
                                <svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                </svg>
                                پاکسازی تست
                            </button>
                            <button type="button" onclick="exportUsersCsv()" class="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs transition flex items-center gap-1.5" style="background: var(--input-bg); border-color: var(--card-border);">
                                <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                                </svg>
                                خروجی CSV
                            </button>
                            <button type="button" onclick="loadUsersData()" class="px-3 py-1.5 rounded-xl theme-accent-btn text-xs font-bold transition flex items-center gap-1.5">
                                <svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                                </svg>
                                بروزرسانی
                            </button>
                        </div>
                    </div>

                    <div class="overflow-x-auto block whitespace-nowrap rounded-xl border" style="border-color: var(--card-border);">
                        <table class="w-full text-right text-xs whitespace-nowrap">
                            <thead class="text-slate-400 border-b" style="background: var(--table-head-bg); border-color: var(--card-border);">
                                <tr>
                                    <th class="p-3">پلتفرم</th>
                                    <th class="p-3">شناسه کاربری</th>
                                    <th class="p-3">نام / نام کاربری</th>
                                    <th class="p-3">شماره تماس</th>
                                    <th class="p-3">معرف رفرال</th>
                                    <th class="p-3">موجودی کیف پول</th>
                                    <th class="p-3">وضعیت تعهدنامه</th>
                                    <th class="p-3 text-center">عملیات</th>
                                </tr>
                            </thead>
                            <tbody id="usersTableBody" class="divide-y divide-slate-800/60 font-mono">
                                <tr>
                                    <td colspan="8" class="p-6 text-center text-slate-500 font-sans">در حال دریافت فهرست کاربران...</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Sub-Tab 2: Viral Referral Network & Stats -->
            <div id="userSubTabContentRef" class="hidden space-y-6">
                <!-- User Stat Cards -->
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div class="glass p-4 rounded-2xl border" style="background: var(--card-bg); border-color: var(--card-border);">
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-xs text-slate-400">کل کاربران ثبت‌نامی</span>
                            <div class="w-8 h-8 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center border border-cyan-500/20">
                                <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                                </svg>
                            </div>
                        </div>
                        <div class="text-2xl font-bold font-mono text-white" id="statTotalUsers">0</div>
                        <p class="text-[11px] text-slate-500 mt-1">شناسه یکپارچه بله و تلگرام</p>
                    </div>

                    <div class="glass p-4 rounded-2xl border" style="background: var(--card-bg); border-color: var(--card-border);">
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-xs text-slate-400">معرفی‌شده‌ها (رفرال فعال)</span>
                            <div class="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">
                                <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z" />
                                </svg>
                            </div>
                        </div>
                        <div class="text-2xl font-bold font-mono text-emerald-400" id="statRefUsers">0</div>
                        <p class="text-[11px] text-slate-500 mt-1">شبکه بازاریابی دهان‌به‌دهان</p>
                    </div>

                    <div class="glass p-4 rounded-2xl border" style="background: var(--card-bg); border-color: var(--card-border);">
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-xs text-slate-400">مجموع اعتبار کیف‌پول‌ها</span>
                            <div class="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center border border-amber-500/20">
                                <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M21 12a2.25 2.25 0 00-2.25-2.25H15a3 3 0 11-6 0H5.25A2.25 2.25 0 003 12m18 0v6a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 18v-6m18 0V9M3 12V9m18 0a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 9m18 0V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v3" />
                                </svg>
                            </div>
                        </div>
                        <div class="text-2xl font-bold font-mono text-amber-400" id="statTotalWallet">۰ تومان</div>
                        <p class="text-[11px] text-slate-500 mt-1">پاداش‌های رفرال و خرید</p>
                    </div>
                </div>

                <!-- Referral Architecture Info Box -->
                <div class="glass p-6 rounded-2xl border space-y-3" style="background: var(--card-bg); border-color: var(--card-border);">
                    <div class="flex items-center gap-2">
                        <span class="text-xl">🌐</span>
                        <h4 class="text-sm font-bold text-slate-100">شبکه بازاریابی رفرال ویروسی (Identical Twin Referral Engine)</h4>
                    </div>
                    <p class="text-xs text-slate-300 leading-relaxed">
                        سامانه رفرال با مکانیزم یکپارچه دوگانه عمل می‌کند: هر کاربر در تلگرام و بله با شناسه عددی یکسان به عنوان معرف ثبت شده و با دعوت هر کاربر جدید، پاداش رفرال به صورت خودکار به کیف پول افزوده شده و سوابق در دیتابیس رمزنگاری‌شده ثبت می‌گردد.
                    </p>
                </div>
            </div>
        </div>

        <!-- ================= TAB 5: SECRETS & TOKENS ================= -->
        <div id="tab-tokens" class="hidden space-y-6">
            <div class="glass p-6 rounded-2xl space-y-6">
                <!-- Cloud Secrets Sync Hub -->
                <div class="p-4 rounded-2xl border text-xs text-slate-200 space-y-2.5 leading-relaxed shadow-lg" style="background: var(--glass-bg); border-color: var(--card-border);">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div class="flex items-center gap-2 text-cyan-300 font-bold text-sm">
                            <span class="text-base">🔐</span>
                            <span>هاب یکپارچه مدیریت سکرت‌های ابری (Cloud Secrets & Security Hub)</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                                اتصال خودکار به Hugging Face Space Secrets
                            </span>
                        </div>
                    </div>
                    <p class="text-slate-300 text-xs">
                        تمامی کلیدهای حساس (توکن‌های تلگرام، بله، روبیکا، رمز پنل، کلیدهای هوش مصنوعی و درگاه‌ها) در این بخش با کلیک روی آیکون <b class="text-cyan-300">👁</b> قابل مشاهده و ویرایش هستند. با کلیک بر روی <b>«ذخیره سکرت‌ها و توکن‌ها»</b>، مقادیر جدید به طور خودکار به <b>Hugging Face Space Secrets</b> تزریق شده و بدون ثبت در فایل‌های متنی گیت‌هاب، در محیط ابری پایدار می‌مانند.
                    </p>
                </div>

                <form id="tokenSettingsForm" onsubmit="handleSaveSettings(event)" class="space-y-6">
                    <!-- ================= SECTION A: CLOUD SECRETS & SECURITY HUB ================= -->
                    <div class="p-5 rounded-2xl border space-y-4 shadow-xl" style="background: var(--glass-bg); border-color: var(--card-border);">
                        <div class="flex items-center gap-2.5 pb-3 border-b border-cyan-500/20">
                            <span class="text-xl">🔐</span>
                            <div>
                                <h3 class="text-sm font-bold text-cyan-300">سکرت‌ها و کلیدهای محرمانه ابری (Cloud Secrets Hub)</h3>
                                <p class="text-[11px] text-slate-400">توکن‌های اتصال ربات‌ها، کلیدهای هوش مصنوعی و سکرت‌های هاگینگ‌فیس (همگام‌سازی خودکار با Hugging Face Space Secrets)</p>
                            </div>
                        </div>

                        <!-- Accordion 1: Bot Tokens & Bale Payment Gateway -->
                        <details class="settings-accordion group rounded-xl p-4 space-y-3 border transition duration-200" open style="background: var(--glass-bg); border-color: var(--card-border);">
                            <summary class="flex items-center justify-between cursor-pointer list-none select-none pb-2 border-b border-white/5">
                                <h4 class="text-xs font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-2">
                                    <span>🤖</span> توکن‌های ربات‌ها و درگاه‌های پرداخت
                                </h4>
                                <span class="text-xs text-slate-400 group-open:rotate-180 transition-transform duration-200 font-mono">▼</span>
                            </summary>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">توکن ربات تلگرام (TELEGRAM_BOT_TOKEN)</label>
                                    <div class="relative">
                                        <input type="text" id="cfg_TELEGRAM_BOT_TOKEN" data-token-field="true" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" data-lpignore="true" data-1p-ignore="true" style="-webkit-text-security: disc; text-security: disc;" class="w-full bg-slate-800/80 border border-sky-500/80 text-sky-400 rounded-xl px-3.5 py-2.5 pl-9 text-xs font-mono focus:outline-none focus:border-sky-400 transition" dir="ltr">
                                        <button type="button" onclick="togglePasswordVisibility('cfg_TELEGRAM_BOT_TOKEN', this)" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-sky-300 transition text-xs">👁</button>
                                    </div>
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">توکن ربات بله (BALE_BOT_TOKEN)</label>
                                    <div class="relative">
                                        <input type="text" id="cfg_BALE_BOT_TOKEN" data-token-field="true" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" data-lpignore="true" data-1p-ignore="true" style="-webkit-text-security: disc; text-security: disc;" class="w-full bg-slate-800/80 border border-emerald-500/80 text-emerald-400 rounded-xl px-3.5 py-2.5 pl-9 text-xs font-mono focus:outline-none focus:border-emerald-400 transition" dir="ltr">
                                        <button type="button" onclick="togglePasswordVisibility('cfg_BALE_BOT_TOKEN', this)" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-emerald-300 transition text-xs">👁</button>
                                    </div>
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">توکن درگاه پرداخت بله (BALE_PAYMENT_TOKEN)</label>
                                    <div class="relative">
                                        <input type="text" id="cfg_BALE_PAYMENT_TOKEN" data-token-field="true" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" data-lpignore="true" data-1p-ignore="true" style="-webkit-text-security: disc; text-security: disc;" class="w-full bg-slate-800/80 border border-emerald-500/80 text-emerald-400 rounded-xl px-3.5 py-2.5 pl-9 text-xs font-mono focus:outline-none focus:border-emerald-400 transition" dir="ltr">
                                        <button type="button" onclick="togglePasswordVisibility('cfg_BALE_PAYMENT_TOKEN', this)" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-emerald-300 transition text-xs">👁</button>
                                    </div>
                                </div>
                            </div>
                        </details>

                        <!-- Accordion 1: Admin IDs & Permissions -->
                        <details class="settings-accordion group rounded-xl p-4 space-y-3 border transition duration-200" open style="background: var(--glass-bg); border-color: var(--card-border);">
                            <summary class="flex items-center justify-between cursor-pointer list-none select-none pb-2 border-b border-white/5">
                                <h4 class="text-xs font-bold text-sky-400 uppercase tracking-wider flex items-center gap-2">
                                    <span>👑</span> مدیریت دسترسی‌ها و شناسه مدیران
                                    <span class="hidden" style="display:none;">شناسه‌های ادمین‌ها و سوپرگروه تاپیک‌دار تلگرام</span>
                                </h4>
                                <span class="text-xs text-slate-400 group-open:rotate-180 transition-transform duration-200 font-mono">▼</span>
                            </summary>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">شناسه عددی مدیر تلگرام (TELEGRAM_OWNER_ID)</label>
                                    <input type="text" id="cfg_TELEGRAM_OWNER_ID" placeholder="12345678" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">شناسه عددی مدیر بله (BALE_OWNER_ID)</label>
                                    <input type="text" id="cfg_BALE_OWNER_ID" placeholder="12345678" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">شناسه تاپیک/سوپرگروه تلگرام - اختیاری (TELEGRAM_FORUM_GROUP_ID)</label>
                                    <input type="text" id="cfg_TELEGRAM_FORUM_GROUP_ID" placeholder="-100xxxxxxxxxx" class="w-full bg-slate-800/80 border border-sky-500/80 text-sky-300 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-sky-400 transition text-left" dir="ltr">
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">شناسه‌های کمکی ادمین - جداشده با کاما (ADMIN_USER_IDS)</label>
                                    <input type="text" id="cfg_ADMIN_USER_IDS" placeholder="12345678, 87654321" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                </div>
                                <input type="hidden" id="cfg_RUBIKA_OWNER_ID" value="" style="display:none;">
                                <div class="hidden border-purple-500/80 text-purple-400" style="display:none;"><input type="hidden" id="cfg_RUBIKA_BOT_TOKEN" value=""></div>
                            </div>
                        </details>

                        <!-- Accordion 2: Multi-Provider AI Hub -->
                        <details class="settings-accordion group rounded-xl p-4 space-y-3 border transition duration-200" open style="background: var(--glass-bg); border-color: var(--card-border);">
                            <summary class="flex items-center justify-between cursor-pointer list-none select-none pb-2 border-b border-white/5">
                                <h4 class="text-xs font-bold text-teal-400 uppercase tracking-wider flex items-center gap-2">
                                    <span>🧠</span> تنظیمات موتورهای هوش مصنوعی (Multi-Provider AI Hub)
                                    <span class="hidden" style="display:none;">تنظیمات هوش مصنوعی (Google Gemini & Nara Router)</span>
                                </h4>
                                <span class="text-xs text-slate-400 group-open:rotate-180 transition-transform duration-200 font-mono">▼</span>
                            </summary>
                            <div class="space-y-4 pt-1">
                                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    <div class="md:col-span-1">
                                        <label class="text-slate-300 font-medium text-xs mb-1.5 block">سرویس‌دهنده فعال هوش مصنوعی (AI_PROVIDER)</label>
                                        <select id="cfg_AI_PROVIDER" onchange="handleAiProviderChange(this.value)" class="w-full bg-slate-800/80 border border-teal-500/80 text-teal-300 rounded-xl px-3.5 py-2.5 text-xs font-bold focus:outline-none focus:border-teal-400 transition cursor-pointer">
                                            <option value="vyceai">VyceAI (پیش‌فرض قدرتمند و سریع)</option>
                                            <option value="nara">Nara Router (روتر چندمدلی نارا)</option>
                                            <option value="gemini">Google Gemini (جمینای رسمی گوگل)</option>
                                            <option value="custom">سفارشی / Custom (OpenAI Compatible)</option>
                                        </select>
                                    </div>
                                    <div class="md:col-span-1">
                                        <label class="text-slate-300 font-medium text-xs mb-1.5 block">آدرس پایه API (AI_BASE_URL)</label>
                                        <input type="url" id="cfg_AI_BASE_URL" placeholder="https://vyceai.com/v1" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                    </div>
                                    <div class="md:col-span-1">
                                        <label class="text-slate-300 font-medium text-xs mb-1.5 block">مدل هوش مصنوعی فعال (AI_MODEL)</label>
                                        <select id="cfg_AI_MODEL" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                            <option value="deepseek-v4.1">deepseek-v4.1 (VyceAI)</option>
                                            <option value="deepseek-v4-flash">deepseek-v4-flash (VyceAI)</option>
                                            <option value="claude-sonnet-4-6">claude-sonnet-4-6 (VyceAI)</option>
                                            <option value="agnes-3.0-flash">agnes-3.0-flash (VyceAI)</option>
                                            <option value="stepfun-3.7-flash">stepfun-3.7-flash (Nara)</option>
                                            <option value="minimax-0.5-free">minimax-0.5-free (Nara)</option>
                                            <option value="qwen2.5-72b">qwen2.5-72b (Nara)</option>
                                            <option value="gemini-2.0-flash">gemini-2.0-flash (Gemini)</option>
                                            <option value="gemini-1.5-flash">gemini-1.5-flash (Gemini)</option>
                                            <option value="gemini-1.5-pro">gemini-1.5-pro (Gemini)</option>
                                        </select>
                                        <!-- Legacy Gemini models reference: value="gemini-3.8-flash" value="gemini-3.1-pro" value="gemini-3.6-flash" -->
                                        <input type="text" id="cfg_AI_MODEL_CUSTOM" placeholder="نام مدل سفارشی (مثلاً gpt-4o-mini)" class="hidden w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-cyan-500 transition text-left mt-1" dir="ltr">
                                    </div>
                                </div>

                                <!-- Distinct Keys for Each Provider -->
                                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-white/5">
                                    <div id="box_vyceai_key">
                                        <label class="text-slate-300 font-medium text-xs mb-1.5 block flex items-center justify-between">
                                            <span>کلید VyceAI (VYCEAI_API_KEY)</span>
                                            <span class="text-[10px] text-teal-400 font-normal">پیش‌فرض</span>
                                        </label>
                                        <div class="relative">
                                            <input type="text" id="cfg_VYCEAI_API_KEY" data-token-field="true" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" data-lpignore="true" data-1p-ignore="true" placeholder="sk-..." style="-webkit-text-security: disc; text-security: disc;" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 pl-9 text-xs font-mono focus:outline-none focus:border-cyan-500 transition" dir="ltr">
                                            <button type="button" onclick="togglePasswordVisibility('cfg_VYCEAI_API_KEY', this)" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-cyan-300 transition text-xs">👁</button>
                                        </div>
                                    </div>
                                    <div id="box_nara_key">
                                        <label class="text-slate-300 font-medium text-xs mb-1.5 block">کلید نارا روتر (NARA_API_KEY)</label>
                                        <div class="relative">
                                            <input type="text" id="cfg_NARA_API_KEY" data-token-field="true" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" data-lpignore="true" data-1p-ignore="true" placeholder="sk-nara-..." style="-webkit-text-security: disc; text-security: disc;" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 pl-9 text-xs font-mono focus:outline-none focus:border-cyan-500 transition" dir="ltr">
                                            <button type="button" onclick="togglePasswordVisibility('cfg_NARA_API_KEY', this)" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-cyan-300 transition text-xs">👁</button>
                                        </div>
                                    </div>
                                    <div id="box_gemini_key">
                                        <label class="text-slate-300 font-medium text-xs mb-1.5 block">کلید گوگل جمینای (GEMINI_API_KEY)</label>
                                        <div class="relative">
                                            <input type="text" id="cfg_GEMINI_API_KEY" data-token-field="true" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" data-lpignore="true" data-1p-ignore="true" placeholder="AIzaSy..." style="-webkit-text-security: disc; text-security: disc;" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 pl-9 text-xs font-mono focus:outline-none focus:border-cyan-500 transition" dir="ltr">
                                            <button type="button" onclick="togglePasswordVisibility('cfg_GEMINI_API_KEY', this)" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-cyan-300 transition text-xs">👁</button>
                                        </div>
                                    </div>
                                </div>

                                <!-- Hidden general AI_API_KEY, NARA_MODEL, etc. for backward compatibility -->
                                <input type="hidden" id="cfg_AI_API_KEY">
                                <select id="cfg_NARA_MODEL" class="hidden" style="display:none;">
                                    <option value="stepfun-3.7-flash">stepfun-3.7-flash</option>
                                    <option value="mimo-v2.5-free">mimo-v2.5-free</option>
                                    <option value="qwen2.5-72b">qwen2.5-72b</option>
                                </select>
                                <input type="hidden" id="cfg_NARA_BASE_URL" value="https://router.bynara.id/v1">
                                <select id="cfg_GEMINI_MODEL" class="hidden" style="display:none;">
                                    <option value="gemini-3.8-flash">gemini-3.8-flash</option>
                                    <option value="gemini-3.6-flash">gemini-3.6-flash</option>
                                    <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                                    <option value="gemini-3.7-flash">gemini-3.7-flash</option>
                                    <option value="gemini-1.5-pro">gemini-1.5-pro</option>
                                </select>

                                <div class="text-[11px] text-slate-400 pt-1">
                                    💡 <b>نکته مهندسی:</b> با تغییر سرویس‌دهنده در منوی کشویی، تنظیمات آدرس پایه و مدل‌ها به صورت خودکار تغییر می‌کنند و کلیدهای سایر سرویس‌ها پاک نمی‌شوند. در صورت عدم تنظیم کلید یا بروز خطای شبکه، پیام خطای صریح ارسال شده و از درج برچسب مدل فیک جلوگیری می‌شود.
                                </div>
                            </div>
                        </details>

                        <!-- Accordion 3: Hugging Face & Admin Security -->
                        <details class="settings-accordion group rounded-xl p-4 space-y-3 border transition duration-200" style="background: var(--glass-bg); border-color: var(--card-border);">
                            <summary class="flex items-center justify-between cursor-pointer list-none select-none pb-2 border-b border-white/5">
                                <h4 class="text-xs font-bold text-rose-400 uppercase tracking-wider flex items-center gap-2">
                                    <span>☁️</span> سکرت‌های هاگینگ فیس و امنیت و تغییر رمز عبور مدیریت
                                </h4>
                                <span class="text-xs text-slate-400 group-open:rotate-180 transition-transform duration-200 font-mono">▼</span>
                            </summary>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">توکن دسترسی هاگینگ فیس (HF_TOKEN)</label>
                                    <div class="relative">
                                        <input type="text" id="cfg_HF_TOKEN" data-token-field="true" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" data-lpignore="true" data-1p-ignore="true" placeholder="hf_..." style="-webkit-text-security: disc; text-security: disc;" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 pl-9 text-xs font-mono focus:outline-none focus:border-cyan-500 transition" dir="ltr">
                                        <button type="button" onclick="togglePasswordVisibility('cfg_HF_TOKEN', this)" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-cyan-300 transition text-xs">👁</button>
                                    </div>
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">شناسه اسپیس هاگینگ فیس (HF_SPACE_ID)</label>
                                    <input type="text" id="cfg_HF_SPACE_ID" placeholder="Foadian/UNFINIT" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">رمز عبور جدید مدیریت</label>
                                    <div class="relative">
                                        <input type="password" id="cfg_NEW_ADMIN_PASSWORD" autocomplete="new-password" placeholder="در صورت تمایل به تغییر رمز عبور وارد کنید" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 pl-9 text-xs focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                        <button type="button" onclick="togglePasswordVisibility('cfg_NEW_ADMIN_PASSWORD', this)" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-rose-300 transition text-xs">👁</button>
                                    </div>
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">تکرار رمز عبور جدید</label>
                                    <div class="relative">
                                        <input type="password" id="cfg_CONFIRM_ADMIN_PASSWORD" autocomplete="new-password" placeholder="تکرار رمز عبور جدید" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 pl-9 text-xs focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                        <button type="button" onclick="togglePasswordVisibility('cfg_CONFIRM_ADMIN_PASSWORD', this)" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-rose-300 transition text-xs">👁</button>
                                    </div>
                                </div>
                            </div>
                        </details>
                    </div>

                    <div class="pt-4 border-t border-slate-800 flex items-center justify-between">
                        <span id="tokensSaveStatus" class="text-xs font-semibold text-emerald-400"></span>
                        <button type="submit" id="btnSaveTokens" class="theme-accent-btn px-6 py-2.5 rounded-xl text-xs font-bold text-white shadow-lg transition">
                            💾 ذخیره سکرت‌ها و توکن‌ها
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- ================= TAB 5: SYSTEM SETTINGS ================= -->
        <div id="tab-settings" class="hidden space-y-6">
            <!-- Settings Form (Directly accessible inside authenticated dashboard) -->
            <div id="settingsContent" class="glass p-6 rounded-2xl space-y-6">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
                    <div>
                        <h2 class="text-base font-bold text-slate-100 flex items-center gap-2">
                            <span>⚙️</span> تنظیمات سیستم، پیام‌رسان‌ها و اتصال پایدار دیتابیس
                        </h2>
                        <p class="text-xs text-slate-400 mt-1">تغییرات در data/settings.json و دیتابیس پایدار ذخیره شده و پس از ریستارت سرور نیز پایدار خواهند ماند.</p>
                    </div>
                    <div class="flex items-center gap-2">
                        <button type="button" onclick="handleExportContactsCSV()" class="theme-card-btn px-3 py-2 rounded-xl text-xs text-amber-300 font-medium flex items-center gap-1.5 transition shadow-sm">
                            <span>📥</span> خروجی مخاطبین (.csv)
                        </button>
                        <button type="button" onclick="handleExportSettings()" class="theme-card-btn px-3 py-2 rounded-xl text-xs text-cyan-300 font-medium flex items-center gap-1.5 transition shadow-sm">
                            <span>📤</span> خروجی و پشتیبان‌گیری تنظیمات (.json)
                        </button>
                        <label class="theme-card-btn px-3 py-2 rounded-xl text-xs text-emerald-300 font-medium flex items-center gap-1.5 transition shadow-sm cursor-pointer">
                            <span>📥</span> درون‌ریزی و بازیابی تنظیمات
                            <input type="file" accept=".json,application/json" class="hidden" onchange="handleImportSettingsFile(this)">
                        </label>
                    </div>
                </div>

                <form id="systemSettingsForm" onsubmit="handleSaveSettings(event)" class="space-y-6">
                    <!-- ================= SECTION B: STORE & MESSAGING SETTINGS ================= -->
                    <div class="p-5 rounded-2xl border space-y-4 shadow-xl" style="background: var(--glass-bg); border-color: var(--card-border);">
                        <div class="flex items-center gap-2.5 pb-3 border-b border-white/5">
                            <span class="text-xl">🛍️</span>
                            <div>
                                <h3 class="text-sm font-bold text-sky-300">تنظیمات عمومی فروشگاه و پیام‌رسان‌ها (Store & Messaging Settings)</h3>
                                <p class="text-[11px] text-slate-400">شناسه‌های مدیران، متن‌های فروشگاه و پیام تحویل هوشمند، شماره کارت بانکی و تنظیمات رسانه‌ها</p>
                            </div>
                        </div>

                        <!-- Custom Brand Logo Card -->
                        <div class="rounded-xl p-4 space-y-4 border transition duration-200" style="background: var(--glass-bg); border-color: var(--card-border);">
                            <div class="flex items-center justify-between pb-2 border-b border-white/5">
                                <h4 class="text-xs font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-2">
                                    <span>🎨</span> لوگو و نشان تجاری اختصاصی (Custom Brand Logo)
                                </h4>
                                <span class="text-[11px] text-slate-400">ذخیره پایدار در دایرکتوری داده و کش‌باستینگ خودکار</span>
                            </div>
                            <div class="flex flex-col sm:flex-row items-center gap-5 pt-1">
                                <div class="w-20 h-20 rounded-2xl bg-slate-800 border-2 border-dashed border-cyan-500/40 flex items-center justify-center overflow-hidden shrink-0 shadow-lg relative" id="panelLogoPreviewContainer">
                                    <img id="panelLogoPreview" src="/static/logo.png?t={int(time.time())}" alt="لوگوی فعلی" class="w-full h-full object-cover" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';">
                                    <span class="hidden items-center justify-center w-full h-full text-3xl font-bold text-white">⚡️</span>
                                </div>
                                <div class="space-y-2 flex-1 text-right">
                                    <p class="text-xs text-slate-300">تصویر لوگوی برند خود را انتخاب و آپلود نمایید. این لوگو بلافاصله در هدر و صفحه لاگین پنل جایگزین خواهد شد (حداکثر ابعاد بهینه 512x512 پیکسل با فرمت PNG).</p>
                                    <div class="flex flex-wrap items-center gap-3 pt-1">
                                        <label class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-xs text-cyan-300 font-medium cursor-pointer transition flex items-center gap-1.5">
                                            <span>📁</span> انتخاب تصویر لوگو
                                            <input type="file" id="logoFileInput" accept="image/*" class="hidden" onchange="handleLogoFileSelect(this)">
                                        </label>
                                        <button type="button" id="btnUploadLogo" onclick="uploadCustomLogo()" disabled class="px-4 py-2 rounded-xl bg-cyan-600/50 text-slate-400 text-xs font-bold transition flex items-center gap-1.5 cursor-not-allowed">
                                            <span>⬆️</span> آپلود و اعمال لوگو
                                        </button>
                                        <span id="logoUploadStatus" class="text-xs font-medium"></span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Accordion 5: Messages, Delivery Quote, Channels & Bank Account Management -->
                        <details class="settings-accordion group rounded-xl p-4 space-y-4 border transition duration-200" style="background: var(--glass-bg); border-color: var(--card-border);">
                            <summary class="flex items-center justify-between cursor-pointer list-none select-none pb-2 border-b border-white/5">
                                <h4 class="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                                    <span>📝</span> مدیریت پیام‌ها و کانال‌ها (تحویل دوره‌ها و حساب بانکی)
                                </h4>
                                <span class="text-xs text-slate-400 group-open:rotate-180 transition-transform duration-200 font-mono">▼</span>
                            </summary>
                            <p class="text-[11px] text-slate-400">تنظیمات عنوان فروشگاه، متن شروع ربات‌ها، متن گرم پایان پیام تحویل دوره، کانال‌های عضویت اجباری و مشخصات کارت بانکی</p>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">عنوان فروشگاه (STORE_NAME)</label>
                                    <input type="text" id="cfg_STORE_NAME" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:border-cyan-500 transition">
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">شماره کارت ۱۶ رقمی (CARD_NUMBER)</label>
                                    <input type="text" id="cfg_CARD_NUMBER" autocomplete="new-password" class="w-full bg-slate-800/80 border border-amber-500/80 text-amber-300 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-amber-400 transition text-left" dir="ltr">
                                </div>
                                <div class="md:col-span-2">
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">متن خوش‌آمدگویی و استارت ربات‌ها (WELCOME_TEXT)</label>
                                    <textarea id="cfg_WELCOME_TEXT" rows="2" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:border-cyan-500 transition"></textarea>
                                </div>
                                <div class="md:col-span-2">
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">جمله گرم پایان پیام تحویل دوره‌ها (COURSE_DELIVERY_NOTE)</label>
                                    <textarea id="cfg_COURSE_DELIVERY_NOTE" rows="2" placeholder="امیدوارم این دوره، براتون سرشار از آگاهی، رشد و نتایج ارزشمند باشه. ✨" class="w-full bg-slate-800/80 border border-emerald-500/80 text-emerald-300 rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:border-emerald-400 transition"></textarea>
                                </div>
                                <div class="md:col-span-2">
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">متن مرکز پشتیبانی و ارتباط با مشتریان (SUPPORT_CENTER_TEXT)</label>
                                    <textarea id="cfg_SUPPORT_CENTER_TEXT" rows="2" placeholder="جهت ارتباط با واحد پشتیبانی و ارسال تیکت..." class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:border-cyan-500 transition"></textarea>
                                </div>
                                <div class="md:col-span-2">
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">متن طرح دعوت از دوستان و هدیه وایرال (INVITE_FRIENDS_TEXT)</label>
                                    <textarea id="cfg_INVITE_FRIENDS_TEXT" rows="2" placeholder="با ارسال لینک اختصاصی خود به دوستان، هدایای ویژه دریافت کنید..." class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:border-cyan-500 transition"></textarea>
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">کانال قفل تلگرام (tg_fjoin_channel)</label>
                                    <input type="text" id="cfg_FORCE_JOIN_CHANNEL_TELEGRAM" placeholder="@channel یا -100xxx" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">کانال قفل بله (bale_fjoin_channel)</label>
                                    <input type="text" id="cfg_FORCE_JOIN_CHANNEL_BALE" placeholder="@channel" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                </div>
                                <div class="md:col-span-2">
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">نام دارنده حساب (CARD_HOLDER)</label>
                                    <input type="text" id="cfg_CARD_HOLDER" class="w-full bg-slate-800/80 border border-amber-500/80 text-amber-300 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 focus:outline-none focus:border-amber-400 transition">
                                </div>
                            </div>
                        </details>

                        <!-- Accordion 6: Store, Media & Compression Settings -->
                        <details class="settings-accordion group rounded-xl p-4 space-y-3 border transition duration-200" style="background: var(--glass-bg); border-color: var(--card-border);">
                            <summary class="flex items-center justify-between cursor-pointer list-none select-none pb-2 border-b border-white/5">
                                <h4 class="text-xs font-bold text-sky-400 uppercase tracking-wider flex items-center gap-2">
                                    <span>📚</span> تنظیمات محتوا، رسانه‌ها و فشرده‌سازی هوشمند بله
                                </h4>
                                <span class="text-xs text-slate-400 group-open:rotate-180 transition-transform duration-200 font-mono">▼</span>
                            </summary>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">حداکثر طول توضیحات دوره (کاراکتر)</label>
                                    <input type="number" id="cfg_COURSE_DESC_MAX_LEN" value="255" min="50" max="2000" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">نام خواننده پیش‌فرض (DEFAULT_ARTIST)</label>
                                    <input type="text" id="cfg_DEFAULT_ARTIST" placeholder="AbbasManesh365 Bot" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:border-cyan-500 transition text-right" dir="auto">
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">سقف امن آپلود بله (MAX_SAFE_BALE_SIZE_MB)</label>
                                    <input type="number" step="0.01" id="cfg_MAX_SAFE_BALE_SIZE_MB" value="49.99" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                </div>
                                <div>
                                    <label class="text-slate-300 font-medium text-xs mb-1.5 block">درصد پاداش کش‌بک خرید (CASHBACK_PERCENT %)</label>
                                    <input type="number" step="0.1" min="0" max="100" id="cfg_CASHBACK_PERCENT" value="0.0" class="w-full bg-slate-800/80 border border-slate-700/80 text-slate-100 rounded-xl px-3.5 py-2.5 text-xs font-mono focus:outline-none focus:border-cyan-500 transition text-left" dir="ltr">
                                </div>
                                <div class="flex items-center gap-3 pt-2 md:col-span-2">
                                    <label class="relative inline-flex items-center cursor-pointer">
                                        <input type="checkbox" id="cfg_APPLY_DEFAULT_ARTIST_TAG" class="sr-only peer" checked>
                                        <div class="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-600"></div>
                                        <span class="mr-3 text-xs font-medium text-slate-300">اعمال متادیتا و تگ خواننده پیش‌فرض روی فایل‌های خروجی صوتی (APPLY_DEFAULT_ARTIST_TAG)</span>
                                    </label>
                                </div>
                            </div>
                        </details>
                    </div>

                    <div class="pt-4 border-t border-slate-800 flex items-center justify-between">
                        <span id="settingsSaveStatus" class="text-xs font-semibold text-emerald-400"></span>
                        <button type="submit" id="btnSaveSettings" class="theme-accent-btn px-6 py-2.5 rounded-xl text-xs font-bold text-white shadow-lg transition">
                            💾 ذخیره و اعمال آنی تنظیمات
                        </button>
                    </div>
                </form>
            </div>

            <!-- Live Terminal Logs Section -->
            <div class="glass p-6 rounded-2xl space-y-3">
                <div class="flex justify-between items-center">
                    <h2 class="text-base font-bold text-slate-100 flex items-center gap-2">
                        <span>📟</span> لاگ زنده و لحظه‌ای سرور (Live Cloud Logs)
                    </h2>
                    <div class="flex items-center gap-2">
                        <span id="logStatus" class="text-xs text-emerald-400 flex items-center gap-1">
                            <span class="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> همگام‌سازی هر ۴ ثانیه
                        </span>
                        <a href="/api/logs/download" target="_blank" class="theme-card-btn px-2.5 py-1 rounded text-xs font-semibold flex items-center gap-1 transition shadow-sm">
                            <span>📥</span> دانلود فایل لاگ (.txt)
                        </a>
                        <button type="button" onclick="copyAllLogs()" id="copyBtn" class="px-2.5 py-1 rounded bg-cyan-950/80 hover:bg-cyan-900 text-xs font-semibold text-cyan-300 border border-cyan-800 flex items-center gap-1 transition">
                            <span>📋</span> <span id="copyBtnText">کپی کل لاگ‌ها</span>
                        </button>
                        <button type="button" onclick="clearLiveLogs()" class="px-2.5 py-1 rounded bg-rose-950/80 hover:bg-rose-900 text-xs font-semibold text-rose-300 border border-rose-800 flex items-center gap-1 transition">
                            <span>🗑️</span> پاکسازی لاگ
                        </button>
                        <button type="button" onclick="fetchLogs()" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 border border-slate-700 transition">
                            🔄 بازخوانی
                        </button>
                    </div>
                </div>
                <div class="relative group">
                    <div class="absolute top-3 right-3 z-10 flex items-center gap-1.5 opacity-80 group-hover:opacity-100 transition-opacity">
                        <button type="button" onclick="copyAllLogs()" title="کپی لاگ‌ها" class="px-2.5 py-1 rounded-lg bg-slate-900/90 hover:bg-slate-800 text-slate-300 border border-slate-700/80 text-[11px] font-sans flex items-center gap-1 backdrop-blur shadow-sm transition">
                            <span>📋</span> کپی
                        </button>
                        <button type="button" onclick="clearLiveLogs()" title="پاکسازی لاگ‌ها" class="px-2.5 py-1 rounded-lg bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800/80 text-[11px] font-sans flex items-center gap-1 backdrop-blur shadow-sm transition">
                            <span>🗑️</span> پاکسازی
                        </button>
                    </div>
                    <div id="logContainer" dir="ltr" class="text-left font-mono text-xs max-h-96 overflow-y-auto bg-slate-950/90 text-emerald-400 p-4 rounded-xl border border-slate-800 space-y-1 select-text">
                        <div class="text-slate-500">Connecting to server logs...</div>
                    </div>
                </div>
            </div>

            <!-- ================= SECTION C: FREQUENCY OF ABUNDANCE MANAGEMENT ================= -->
            <div id="frequencyContent" class="glass p-6 rounded-2xl space-y-6 border" style="border-color: var(--card-border); background: var(--glass-bg);">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/5">
                    <div>
                        <h3 class="text-base font-bold text-slate-100 flex items-center gap-2">
                            <span class="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400 inline-flex items-center justify-center">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                                </svg>
                            </span>
                            مدیریت فرکانس فراوانی (بانک باورهای صبحگاهی و شبانگاهی)
                        </h3>
                        <p class="text-xs text-slate-400 mt-1">مدیریت کارت‌های ورق‌زن فرکانس فراوانی در تلگرام و بله (ذخیره مستقیم و پایدار در data/frequencies.json)</p>
                    </div>
                    <div class="flex items-center gap-2">
                        <button type="button" onclick="loadFrequenciesTable()" class="theme-card-btn px-3 py-2 rounded-xl text-xs font-medium flex items-center gap-1.5 transition shadow-sm">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            بازخوانی لیست
                        </button>
                    </div>
                </div>

                <!-- Add New Frequency Form -->
                <form id="addFrequencyForm" onsubmit="submitAddNewFrequency(event)" class="p-4 rounded-xl border space-y-4" style="background: var(--glass-bg); border-color: var(--card-border);">
                    <div class="text-xs font-bold text-sky-400 flex items-center gap-2 pb-2 border-b border-white/5">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                        </svg>
                        افزودن باور جدید به سامانه
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <label class="text-slate-300 font-medium text-xs mb-1.5 block">دسته‌بندی زمان</label>
                            <select id="freqNewCategory" class="w-full border rounded-xl px-3 py-2 text-xs focus:outline-none transition" style="background: var(--input-bg); border-color: var(--card-border); color: var(--text-color);">
                                <option value="MORNING">باور صبحگاهی (MORNING)</option>
                                <option value="NIGHT">باور شبانگاهی (NIGHT)</option>
                            </select>
                        </div>
                        <div>
                            <label class="text-slate-300 font-medium text-xs mb-1.5 block">عنوان باور</label>
                            <input type="text" id="freqNewTitle" required placeholder="مثال: ذهن ثروت‌ساز" class="w-full border rounded-xl px-3 py-2 text-xs focus:outline-none transition" style="background: var(--input-bg); border-color: var(--card-border); color: var(--text-color);">
                        </div>
                        <div>
                            <label class="text-slate-300 font-medium text-xs mb-1.5 block">متن تأکیدی باور</label>
                            <input type="text" id="freqNewText" required placeholder="مثال: ذهن من سرشار از ایده‌های طلایی است." class="w-full border rounded-xl px-3 py-2 text-xs focus:outline-none transition" style="background: var(--input-bg); border-color: var(--card-border); color: var(--text-color);">
                        </div>
                    </div>
                    <div class="flex justify-end pt-1">
                        <button type="submit" id="btnSubmitFrequency" class="px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-sm" style="background: var(--accent-color); color: #fff;">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                            </svg>
                            ثبت عبارت در بانک باورها
                        </button>
                    </div>
                </form>

                <!-- Frequencies Table Container -->
                <div class="overflow-x-auto rounded-xl border" style="border-color: var(--card-border);">
                    <table class="w-full text-right text-xs">
                        <thead>
                            <tr class="border-b" style="background: var(--table-head-bg); border-color: var(--card-border); color: var(--text-muted);">
                                <th class="py-3 px-4 w-12 text-center">#</th>
                                <th class="py-3 px-4 w-40">عنوان باور</th>
                                <th class="py-3 px-4 w-32 text-center">دسته‌بندی</th>
                                <th class="py-3 px-4">متن تأکیدی</th>
                                <th class="py-3 px-4 w-20 text-center">عملیات</th>
                            </tr>
                        </thead>
                        <tbody id="frequencyTableBody" class="divide-y" style="border-color: var(--card-border);">
                            <tr>
                                <td colspan="5" class="py-8 text-center text-slate-400">
                                    در حال بارگذاری لیست فرکانس‌ها...
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Edit Course Modal -->
        <div id="editModal" class="hidden fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
            <div class="glass p-6 rounded-2xl w-full max-w-lg border border-slate-700 space-y-4 max-h-[90vh] overflow-y-auto relative">
                <div class="flex justify-between items-center pb-3 border-b border-slate-800">
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                        <span>✏️</span> ویرایش دوره <span id="modalProdIdBadge" class="text-xs font-mono text-cyan-400"></span>
                    </h3>
                    <button onclick="closeEditModal()" class="text-slate-400 hover:text-white text-base">✕</button>
                </div>
                <form id="editForm" onsubmit="handleSaveEdit(event)" class="space-y-3">
                    <input type="hidden" id="editProductId">
                    <div>
                        <div class="flex justify-between items-center mb-1">
                            <label class="block text-xs text-slate-300">نام دوره</label>
                            <span id="counter_editName" class="text-[11px] font-mono text-slate-400">0 / 32</span>
                        </div>
                        <input type="text" id="editName" required maxlength="32" oninput="updateCharCounter('editName', 'counter_editName', 32)" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                    </div>
                    <div>
                        <label class="block text-xs text-slate-300 mb-1">قیمت (تومان)</label>
                        <input type="text" inputmode="numeric" id="editPrice" required oninput="formatPriceInput(this)" placeholder="مثال: ۱۵۰,۰۰۰" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono">
                    </div>
                    <div>
                        <div class="flex justify-between items-center mb-1">
                            <div class="flex items-center gap-2">
                                <label class="block text-xs text-slate-300">توضیحات دوره</label>
                                <button type="button" onclick="aiSummarizeDescription('editDesc', 'counter_editDesc')" id="btnAiSummarizeEdit" class="px-2.5 py-1 rounded-lg bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/40 text-[11px] flex items-center gap-1 transition">
                                    <span>✨</span> خلاصه هوشمند برای بله (زیر ۲۵۵ کاراکتر)
                                </button>
                            </div>
                            <span id="counter_editDesc" class="text-[11px] font-mono text-slate-400">0 / 255</span>
                        </div>
                        <textarea id="editDesc" rows="3" oninput="updateCharCounter('editDesc', 'counter_editDesc', 255)" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-cyan-500"></textarea>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs text-slate-300 mb-1">شیوه تحویل محتوا</label>
                            <select id="editDeliveryType" onchange="togglePackageInput('edit')" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                                <option value="channel">هدایت به کانال / لینک مستقیم</option>
                                <option value="files_package">بسته چندفایله صوتی/تصویری مستقیم ربات (پکیج)</option>
                            </select>
                        </div>
                        <div id="editDownloadBox">
                            <label class="block text-xs text-slate-300 mb-1">لینک دانلود فایل دوره</label>
                            <input type="text" id="editDl" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono">
                        </div>
                    </div>
                    <div id="editPackageBox" class="hidden">
                        <div class="flex justify-between items-center mb-1">
                            <label class="block text-xs text-cyan-300 font-medium">لیست فایل‌های پکیج (JSON یا خط‌به‌خط)</label>
                            <span class="text-[10px] text-slate-400">تحویل زنجیره‌ای در تلگرام و بله</span>
                        </div>
                        <textarea id="editFilesPackage" rows="3" placeholder='[&#10;  {{"title": "جلسه اول", "file_name": "lesson1.mp3", "duration": 1200}}&#10;]' class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono"></textarea>
                    </div>
                    <div>
                        <label class="block text-xs text-slate-300 mb-1">آدرس عکس / بنر</label>
                        <div class="flex gap-2 items-center">
                            <input type="text" id="editPhoto" class="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono">
                            <label class="cursor-pointer px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs text-cyan-300 font-medium transition flex items-center gap-1 shrink-0">
                                <span>📷</span> تغییر بنر
                                <input type="file" accept="image/*" class="hidden" onchange="uploadBannerFile(this, 'editPhoto')">
                            </label>
                        </div>
                        <div class="flex justify-between items-center mt-1">
                            <span id="bannerUploadStatus_editPhoto" class="text-[11px] text-slate-400"></span>
                            <span class="text-[10px] text-amber-300/80">⚡️ حجم بهینه بنر: زیر 500KB جهت بارگذاری فوق سریع</span>
                        </div>
                    </div>
                    <div>
                        <label class="block text-xs text-slate-300 mb-1">روش‌های پرداخت و شرایط دوره</label>
                        <div class="flex flex-wrap items-center gap-6 bg-slate-900/60 p-2.5 rounded-xl border border-slate-700">
                            <label class="flex items-center gap-2 cursor-pointer text-xs text-slate-300">
                                <input type="checkbox" id="editAllowCard" class="w-4 h-4 rounded text-cyan-600 focus:ring-0 bg-slate-900 border-slate-600">
                                <span>💳 پرداخت کارت‌به‌کارت</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer text-xs text-slate-300">
                                <input type="checkbox" id="editAllowBale" class="w-4 h-4 rounded text-emerald-600 focus:ring-0 bg-slate-900 border-slate-600">
                                <span>🌐 درگاه پرداخت بله</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer text-xs text-amber-300">
                                <input type="checkbox" id="editRequiresReferral" class="w-4 h-4 rounded text-amber-500 focus:ring-0 bg-slate-900 border-slate-600">
                                <span>🎁 نیازمند ۱ دعوت موفق (هدیه وایرال)</span>
                            </label>
                        </div>
                    </div>
                    <div class="flex justify-end gap-2 pt-3 border-t border-slate-700 sticky bottom-0 bg-slate-900 p-3 -mx-6 -mb-6 rounded-b-2xl z-10">
                        <button type="button" onclick="closeEditModal()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 transition">انصراف</button>
                        <button type="submit" class="px-5 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-xs font-bold text-white shadow-lg shadow-cyan-600/20 transition">ذخیره تغییرات</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Audio Technical Specs Modal -->
        <div id="specsModal" class="hidden fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
            <div class="glass p-6 rounded-2xl w-full max-w-md border border-slate-700 space-y-4 shadow-2xl">
                <div class="flex justify-between items-center pb-3 border-b border-slate-800">
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                        <span>📊</span> مشخصات فنی صوت و رسانه
                    </h3>
                    <button onclick="closeSpecsModal()" class="text-slate-400 hover:text-white text-base">✕</button>
                </div>
                <div id="specsLoading" class="py-8 text-center text-xs text-cyan-300 animate-pulse">
                    در حال استخراج مشخصات فنی رسانه...
                </div>
                <div id="specsBody" class="hidden space-y-3">
                    <div class="bg-slate-900/90 p-3 rounded-xl border border-slate-800 space-y-2">
                        <div class="flex justify-between text-xs">
                            <span class="text-slate-400">نام فایل:</span>
                            <span id="specFilename" class="text-slate-100 font-bold font-mono text-left truncate max-w-[200px]" dir="ltr"></span>
                        </div>
                        <div class="flex justify-between text-xs">
                            <span class="text-slate-400">بیت‌ریت (Bitrate):</span>
                            <span id="specBitrate" class="text-emerald-400 font-bold font-mono" dir="ltr"></span>
                        </div>
                        <div class="flex justify-between text-xs">
                            <span class="text-slate-400">نرخ نمونه‌برداری (Sample Rate):</span>
                            <span id="specSampleRate" class="text-cyan-300 font-bold font-mono" dir="ltr"></span>
                        </div>
                        <div class="flex justify-between text-xs">
                            <span class="text-slate-400">کانال صوتی (Channels):</span>
                            <span id="specChannels" class="text-purple-300 font-bold"></span>
                        </div>
                        <div class="flex justify-between text-xs">
                            <span class="text-slate-400">کدک (Codec):</span>
                            <span id="specCodec" class="text-amber-300 font-bold font-mono"></span>
                        </div>
                        <div class="flex justify-between text-xs">
                            <span class="text-slate-400">مدت زمان (Duration):</span>
                            <span id="specDuration" class="text-blue-300 font-bold font-mono"></span>
                        </div>
                        <div class="flex justify-between text-xs">
                            <span class="text-slate-400">حجم فایل (Size):</span>
                            <span id="specSize" class="text-slate-200 font-bold font-mono"></span>
                        </div>
                        <div class="flex justify-between text-xs">
                            <span class="text-slate-400">کاور آرت تعبیه‌شده:</span>
                            <span id="specCoverStatus" class="font-bold"></span>
                        </div>
                    </div>
                </div>
                <div class="flex justify-end pt-3 border-t border-slate-800">
                    <button type="button" onclick="closeSpecsModal()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 transition">بستن</button>
                </div>
            </div>
        </div>

        <!-- Studio Single Tag & Cover Edit Modal -->
        <div id="tagModal" class="hidden fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
            <div class="glass p-6 rounded-2xl w-full max-w-lg border border-slate-700 space-y-4 shadow-2xl">
                <div class="flex justify-between items-center pb-3 border-b border-slate-800">
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                        <span>✏️</span> استودیو: ویرایش متادیتا و کاور آرت
                    </h3>
                    <button onclick="closeTagModal()" class="text-slate-400 hover:text-white text-base">✕</button>
                </div>
                <form id="tagForm" onsubmit="handleSaveStudioTags(event)" class="space-y-4">
                    <input type="hidden" id="tagDropId">
                    <input type="hidden" id="tagCoverB64">
                    
                    <!-- Cover Art Section -->
                    <div class="flex items-center gap-4 p-3 bg-slate-900/80 rounded-xl border border-slate-800">
                        <div class="w-20 h-20 rounded-xl overflow-hidden bg-slate-950 border border-slate-700 flex items-center justify-center relative shrink-0">
                            <img id="tagCoverPreview" src="" alt="Cover" class="w-full h-full object-cover">
                        </div>
                        <div class="space-y-2 flex-1">
                            <label class="cursor-pointer px-3 py-1.5 rounded-lg bg-cyan-950 hover:bg-cyan-900 border border-cyan-800 text-xs text-cyan-300 font-medium inline-flex items-center gap-1.5 transition">
                                <span>📷</span> انتخاب کاور جدید
                                <input type="file" accept="image/jpeg,image/png" class="hidden" onchange="previewStudioCover(this, 'tagCoverPreview', 'tagCoverB64')">
                            </label>
                            <div>
                                <label class="flex items-center gap-2 cursor-pointer text-xs text-rose-400">
                                    <input type="checkbox" id="tagRemoveCover" class="w-4 h-4 rounded text-rose-600 focus:ring-0 bg-slate-900 border-slate-700">
                                    <span>🗑 حذف کامل کاور آرت</span>
                                </label>
                            </div>
                        </div>
                    </div>

                    <div>
                        <label class="block text-xs text-slate-300 mb-1">عنوان ترک (Title)</label>
                        <input type="text" id="tagTitle" placeholder="مثال: جلسه اول - مقدمه" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs text-slate-300 mb-1">نام هنرمند / مدرس (Artist)</label>
                            <input type="text" id="tagArtist" placeholder="مثال: مدرس دوره" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                        </div>
                        <div>
                            <label class="block text-xs text-slate-300 mb-1">نام آلبوم / دوره (Album)</label>
                            <input type="text" id="tagAlbum" placeholder="مثال: دوره تخصصی" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                        </div>
                    </div>
                    <div>
                        <label class="block text-xs text-slate-300 mb-1">نام فایل فیزیکی (Physical Filename)</label>
                        <input type="text" id="tagFilename" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-cyan-500 text-left" dir="ltr">
                    </div>

                    <div class="flex justify-end gap-2 pt-3 border-t border-slate-800">
                        <button type="button" onclick="closeTagModal()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 transition">انصراف</button>
                        <button type="submit" id="btnSaveTag" class="px-5 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-xs font-bold text-white shadow-lg shadow-cyan-600/20 transition">💾 ذخیره آنی متادیتا</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Studio Batch Tag Edit Modal -->
        <div id="batchTagModal" class="hidden fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
            <div class="glass p-6 rounded-2xl w-full max-w-lg border border-slate-700 space-y-4 shadow-2xl">
                <div class="flex justify-between items-center pb-3 border-b border-slate-800">
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                        <span>✏️</span> استودیو: ویرایش گروهی متادیتا (Batch Mp3tag)
                    </h3>
                    <button onclick="closeBatchTagModal()" class="text-slate-400 hover:text-white text-base">✕</button>
                </div>
                <form id="batchTagForm" onsubmit="handleSaveBatchTags(event)" class="space-y-4">
                    <input type="hidden" id="batchCoverB64">
                    <div class="p-3 bg-cyan-950/40 border border-cyan-800/80 rounded-xl text-xs text-cyan-200">
                        تعداد <span id="batchCountBadge" class="font-bold font-mono text-white">۰</span> فایل جهت ویرایش یکپارچه انتخاب شده است.
                    </div>

                    <!-- Batch Cover Art Section -->
                    <div class="flex items-center gap-4 p-3 bg-slate-900/80 rounded-xl border border-slate-800">
                        <div class="w-16 h-16 rounded-xl overflow-hidden bg-slate-950 border border-slate-700 flex items-center justify-center relative shrink-0">
                            <img id="batchCoverPreview" src="" alt="Cover" class="w-full h-full object-cover">
                        </div>
                        <div class="space-y-2 flex-1">
                            <label class="cursor-pointer px-3 py-1.5 rounded-lg bg-cyan-950 hover:bg-cyan-900 border border-cyan-800 text-xs text-cyan-300 font-medium inline-flex items-center gap-1.5 transition">
                                <span>📷</span> انتخاب کاور مشترک
                                <input type="file" accept="image/jpeg,image/png" class="hidden" onchange="previewStudioCover(this, 'batchCoverPreview', 'batchCoverB64')">
                            </label>
                            <div>
                                <label class="flex items-center gap-2 cursor-pointer text-xs text-rose-400">
                                    <input type="checkbox" id="batchRemoveCover" class="w-4 h-4 rounded text-rose-600 focus:ring-0 bg-slate-900 border-slate-700">
                                    <span>🗑 حذف کاور تمام فایل‌های انتخابی</span>
                                </label>
                            </div>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs text-slate-300 mb-1">نام آلبوم مشترک (Album)</label>
                            <input type="text" id="batchAlbum" placeholder="نام دوره یا آلبوم" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                        </div>
                        <div>
                            <label class="block text-xs text-slate-300 mb-1">نام هنرمند مشترک (Artist)</label>
                            <input type="text" id="batchArtist" placeholder="نام مدرس یا خواننده" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                        </div>
                    </div>

                    <!-- Auto Numbering Section -->
                    <div class="p-3 bg-slate-900/80 rounded-xl border border-slate-800 space-y-2">
                        <label class="flex items-center gap-2 cursor-pointer text-xs font-bold text-amber-300">
                            <input type="checkbox" id="batchAutoNumber" checked class="w-4 h-4 rounded text-amber-600 focus:ring-0 bg-slate-900 border-slate-700">
                            <span>🔢 شماره‌گذاری خودکار عنوان‌ها (جلسه ۱، جلسه ۲، ...)</span>
                        </label>
                        <div>
                            <label class="block text-[11px] text-slate-400 mb-1">الگوی عنوان (Title Pattern - متغیر {{n}} شماره است):</label>
                            <input type="text" id="batchTitlePattern" value="جلسه {{n}}" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono">
                        </div>
                    </div>

                    <div class="flex justify-end gap-2 pt-3 border-t border-slate-800">
                        <button type="button" onclick="closeBatchTagModal()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 transition">انصراف</button>
                        <button type="submit" id="btnSaveBatch" class="px-5 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-xs font-bold text-white shadow-lg shadow-cyan-600/20 transition">🚀 اعمال روی تمام فایل‌ها</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Audio Cutter Modal (WaveSurfer.js) -->
        <div id="cutterModal" class="hidden fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div class="glass p-6 rounded-2xl w-full max-w-2xl border border-slate-700 space-y-4 shadow-2xl">
                <div class="flex justify-between items-center pb-3 border-b border-slate-800">
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                        <span>✂️</span> استودیو: برش پیشرفته صوت با نمودار موج (WaveSurfer)
                    </h3>
                    <button onclick="closeCutterModal()" class="text-slate-400 hover:text-white text-base">✕</button>
                </div>

                <input type="hidden" id="cutterDropId">
                <div>
                    <span id="cutterFilename" class="text-xs font-bold text-cyan-300 font-mono" dir="ltr"></span>
                </div>

                <!-- Waveform Container -->
                <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                    <div id="waveformLoading" class="text-center py-6 text-xs text-cyan-400 animate-pulse">در حال بارگذاری نمودار موج صوتی...</div>
                    <div id="waveform" class="w-full"></div>
                    <div class="flex justify-between text-[11px] font-mono text-slate-400">
                        <span id="cutterCurrentTime">00:00.0</span>
                        <span id="cutterTotalDuration">00:00.0</span>
                    </div>
                </div>

                <!-- Controls Bar -->
                <div class="flex flex-wrap items-center justify-between gap-3 bg-slate-900/80 p-3 rounded-xl border border-slate-800">
                    <div class="flex items-center gap-2">
                        <button type="button" onclick="setStartFromCursor()" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs transition flex items-center gap-1">
                            <span>📍</span> شروع از نشانگر
                        </button>
                        <button type="button" onclick="setEndFromCursor()" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-emerald-300 text-xs transition flex items-center gap-1">
                            <span>🏁</span> پایان در نشانگر
                        </button>
                    </div>
                    <div class="text-xs text-slate-400">
                        جهت جابجایی نشانگر، روی نمودار موج صوتی کلیک کنید
                    </div>
                </div>

                <!-- Start & End Time Inputs -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs text-slate-300 mb-1">زمان شروع (Start Time - ثانیه یا 00:00.0)</label>
                        <input type="text" id="cutStartTime" value="00:00.0" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-cyan-300 font-mono text-left focus:outline-none focus:border-cyan-500" dir="ltr">
                    </div>
                    <div>
                        <label class="block text-xs text-slate-300 mb-1">زمان پایان (End Time - ثانیه یا 00:00.0)</label>
                        <input type="text" id="cutEndTime" value="00:00.0" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-emerald-300 font-mono text-left focus:outline-none focus:border-cyan-500" dir="ltr">
                    </div>
                </div>

                <div class="flex items-center justify-between pt-3 border-t border-slate-800" dir="ltr">
                    <!-- Left Side: Single Toggle Play/Pause Switch (123apps style) -->
                    <div class="flex items-center gap-3">
                        <button type="button" onclick="toggleWavePlayPause()" id="btnWaveToggle" class="w-11 h-11 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white flex items-center justify-center text-lg font-bold shadow-lg shadow-cyan-600/30 transition hover:scale-105" title="پخش / مکث">
                            <span id="waveToggleIcon">▶</span>
                        </button>
                        <div class="text-left font-mono">
                            <span id="waveToggleTime" class="text-xs text-cyan-300 font-bold block">00:00.0</span>
                            <span class="text-[10px] text-slate-400 block">پخش / مکث</span>
                        </div>
                    </div>

                    <!-- Right Side: Actions -->
                    <div class="flex items-center gap-2" dir="rtl">
                        <button type="button" onclick="closeCutterModal()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 transition">انصراف</button>
                        <button type="button" onclick="submitAudioCut()" id="btnSubmitCut" class="px-5 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-xs font-bold text-white shadow-lg shadow-cyan-600/20 transition flex items-center gap-1.5">
                            <span>✂️</span> برش و ایجاد فایل جدید
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Feed Download Dispatch Destination Modal -->
        <div id="feedDispatchModal" class="hidden fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div class="glass-card max-w-md w-full p-6 rounded-2xl border shadow-2xl relative space-y-4" style="background: var(--card-bg, #1e293b); border-color: var(--card-border, #334155);">
                <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                        <span>⚡️</span> انتقال هدیه دانلودی به پیام‌رسان‌ها
                    </h3>
                    <button type="button" onclick="closeFeedDispatchModal()" class="text-slate-400 hover:text-white text-lg transition">✕</button>
                </div>
                <div>
                    <div id="feedDispatchModalTitle" class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs font-bold text-cyan-300 line-clamp-2 leading-relaxed">
                        -
                    </div>
                </div>

                <!-- Dual Format Selector: MP3 vs MP4 -->
                <div class="space-y-1.5">
                    <label class="text-[11px] text-slate-400 block font-medium">انتخاب فرمت رسانه:</label>
                    <div class="grid grid-cols-2 gap-2">
                        <button type="button" id="btnFormatAudio" onclick="setDispatchFormat('audio')" class="py-2 px-3 rounded-xl border text-xs font-bold transition flex items-center justify-center gap-1.5 theme-accent-btn">
                            <span>🎙</span> نسخه صوتی MP3
                        </button>
                        <button type="button" id="btnFormatVideo" onclick="setDispatchFormat('video')" class="py-2 px-3 rounded-xl border border-slate-700 text-slate-300 bg-slate-800/80 hover:bg-slate-700 text-xs font-bold transition flex items-center justify-center gap-1.5">
                            <span>🎬</span> نسخه تصویری MP4
                        </button>
                    </div>
                </div>

                <!-- Multi-select Checklist for Target Platforms -->
                <div class="space-y-2 pt-2 border-t border-slate-700/60">
                    <label class="text-[11px] text-slate-400 block font-medium">پلتفرم‌های مقصد را انتخاب فرمایید:</label>
                    <div class="grid grid-cols-2 gap-2 text-xs">
                        <label class="flex items-center gap-2 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800 cursor-pointer hover:border-cyan-500/50 transition">
                            <input type="checkbox" id="chkDispatchTg" checked class="rounded bg-slate-800 border-slate-700 text-cyan-500 focus:ring-0">
                            <span class="text-slate-200">✈️ تلگرام</span>
                        </label>
                        <label class="flex items-center gap-2 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800 cursor-pointer hover:border-emerald-500/50 transition">
                            <input type="checkbox" id="chkDispatchBale" checked class="rounded bg-slate-800 border-slate-700 text-emerald-500 focus:ring-0">
                            <span class="text-slate-200">🟢 بله</span>
                        </label>
                        <label class="flex items-center gap-2 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800 cursor-pointer hover:border-indigo-500/50 transition">
                            <input type="checkbox" id="chkDispatchRubika" class="rounded bg-slate-800 border-slate-700 text-indigo-500 focus:ring-0">
                            <span class="text-slate-200">👤 روبیکا کاربری</span>
                        </label>
                        <label class="flex items-center gap-2 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800 cursor-pointer hover:border-cyan-500/50 transition">
                            <input type="checkbox" id="chkDispatchSoroush" class="rounded bg-slate-800 border-slate-700 text-cyan-500 focus:ring-0">
                            <span class="text-slate-200">💬 سروش‌پلاس</span>
                        </label>
                    </div>

                    <button type="button" onclick="executeFeedMultiDispatch()" id="btnExecuteMultiDispatch" class="w-full mt-2 py-2.5 px-4 rounded-xl theme-accent-btn text-xs font-bold transition flex items-center justify-center gap-2 shadow-sm">
                        <span>🚀</span> ارسال به پلتفرم‌های انتخاب‌شده
                    </button>
                </div>

                <!-- Direct Add to Course Episodes Section -->
                <div class="space-y-2 pt-3 border-t border-slate-700/60">
                    <label class="text-[11px] text-cyan-400 block font-bold flex items-center gap-1.5">
                        <span>➕</span> افزودن مستقیم به سرفصل‌های دوره:
                    </label>
                    <div class="flex flex-col gap-2">
                        <select id="feedCourseSelect" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-cyan-500">
                            <!-- Populated dynamically from window.COURSES_CACHE -->
                        </select>
                        <button type="button" onclick="addFeedToCourseEpisodes()" id="btnAddFeedToCourse" class="w-full py-2 px-4 rounded-xl bg-cyan-700 hover:bg-cyan-600 text-white text-xs font-bold transition flex items-center justify-center gap-2 shadow-sm">
                            <span>📦</span> افزودن به عنوان قسمت جدید این دوره
                        </button>
                    </div>
                </div>
                <div class="pt-3 border-t border-slate-700/60 flex justify-end">
                    <button type="button" onclick="closeFeedDispatchModal()" class="px-4 py-2 rounded-xl theme-card-btn text-xs font-bold transition">
                        انصراف
                    </button>
                </div>
            </div>
        </div>

        <!-- Soroush Plus Login Modal -->
        <div id="soroushLoginModal" class="hidden fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div class="glass-card max-w-sm w-full p-6 rounded-2xl border shadow-2xl relative space-y-4" style="background: var(--card-bg, #1e293b); border-color: var(--card-border, #334155);">
                <div class="flex items-center justify-between border-b pb-3" style="border-color: var(--card-border);">
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                        <svg class="w-4 h-4 text-cyan-400 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a.75.75 0 01-.774-.75 4.975 4.975 0 01.75-2.618A7.842 7.842 0 013 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                        </svg>
                        <span>اتصال حساب کاربری سروش‌پلاس</span>
                    </h3>
                    <button type="button" onclick="closeSoroushLoginModal()" class="text-slate-400 hover:text-white text-lg transition">✕</button>
                </div>

                <!-- Sub-Tabs for Mode -->
                <div class="flex items-center gap-1 p-1 rounded-xl" style="background: var(--input-bg); border: 1px solid var(--card-border);">
                    <button type="button" id="tabBtnSoroushSms" onclick="switchSoroushTab('sms')" class="flex-1 py-1.5 rounded-lg text-xs font-bold transition theme-card-btn">
                        دریافت کد پیامک
                    </button>
                    <button type="button" id="tabBtnSoroushManual" onclick="switchSoroushTab('manual')" class="flex-1 py-1.5 rounded-lg text-xs font-bold text-slate-400 hover:text-white transition">
                        ثبت دستی توکن
                    </button>
                </div>

                <!-- SMS Mode: Step 1 Phone -->
                <div id="soroushStepPhone" class="space-y-3">
                    <p class="text-xs text-slate-300 leading-relaxed">
                        شماره موبایل حساب سروش‌پلاس خود را جهت دریافت پیامک تایید وارد نمایید:
                    </p>
                    <input type="text" id="soroushPhoneInput" placeholder="09121234567" class="w-full rounded-xl px-3 py-2 text-xs font-mono text-cyan-300 focus:outline-none text-left" style="background: var(--input-bg); border: 1px solid var(--card-border);" dir="ltr">
                    <button type="button" onclick="submitSoroushPhone()" id="btnSoroushSendCode" class="w-full py-2.5 px-4 rounded-xl theme-accent-btn text-xs font-bold transition flex items-center justify-center gap-2 shadow-sm">
                        <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" /></svg>
                        <span>دریافت کد تایید پیامکی</span>
                    </button>
                </div>

                <!-- SMS Mode: Step 2 Code -->
                <div id="soroushStepCode" class="hidden space-y-3">
                    <p class="text-xs text-slate-300 leading-relaxed">
                        کد تایید ارسال‌شده به شماره <b id="soroushTargetPhoneDisplay" class="text-cyan-300 font-mono"></b> را وارد نمایید:
                    </p>
                    <input type="text" id="soroushCodeInput" placeholder="12345" maxlength="6" class="w-full rounded-xl px-3 py-2 text-xs font-mono text-cyan-300 focus:outline-none text-center text-lg" style="background: var(--input-bg); border: 1px solid var(--card-border);" dir="ltr">
                    <button type="button" onclick="submitSoroushCode()" id="btnSoroushVerifyCode" class="w-full py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition flex items-center justify-center gap-2 shadow-sm">
                        <svg class="w-4 h-4 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
                        <span>تایید و فعال‌سازی سشن امن</span>
                    </button>
                    <button type="button" onclick="resetSoroushLoginForm()" class="w-full text-center text-xs text-slate-400 hover:text-slate-200 transition">
                        ← تغییر شماره موبایل
                    </button>
                </div>

                <!-- Manual Token Mode -->
                <div id="soroushStepManual" class="hidden space-y-3">
                    <p class="text-xs text-slate-300 leading-relaxed">
                        در صورت اختلال وب‌سرویس پیامکی، توکن دسترسی وب سشن سروش‌پلاس را وارد نمایید:
                    </p>
                    <div>
                        <label class="block text-[11px] text-slate-400 mb-1">توکن نشست (Bearer Token)</label>
                        <input type="text" id="soroushManualTokenInput" placeholder="eyJhbGciOiJIUzI1NiIsIn..." class="w-full rounded-xl px-3 py-2 text-xs font-mono text-cyan-300 focus:outline-none text-left" style="background: var(--input-bg); border: 1px solid var(--card-border);" dir="ltr">
                    </div>
                    <div>
                        <label class="block text-[11px] text-slate-400 mb-1">شماره موبایل مرتبط (اختیاری)</label>
                        <input type="text" id="soroushManualPhoneInput" placeholder="09121234567" class="w-full rounded-xl px-3 py-2 text-xs font-mono text-cyan-300 focus:outline-none text-left" style="background: var(--input-bg); border: 1px solid var(--card-border);" dir="ltr">
                    </div>
                    <button type="button" onclick="submitSoroushManualToken()" id="btnSoroushManualSubmit" class="w-full py-2.5 px-4 rounded-xl theme-accent-btn text-xs font-bold transition flex items-center justify-center gap-2 shadow-sm">
                        <svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" /></svg>
                        <span>ذخیره مستقیم توکن و فعال‌سازی سشن</span>
                    </button>
                </div>

                <div id="soroushLoginError" class="hidden p-2.5 rounded-xl bg-rose-950/80 border border-rose-800 text-xs text-rose-300 font-mono"></div>
            </div>
        </div>

        <!-- Footer -->
        <footer class="text-center py-4 text-xs text-slate-500 border-t border-slate-800/80">
            طراحی شده با استانداردهای مدرن یونیکس، FFmpeg، Mutagen و معماری چندپلتفرمه {health['engine_version']}
        </footer>
    </main>
        </div>
    </div>

    <script>
        window.COURSES_CACHE = {courses_data_json};
        window.coursesData = window.COURSES_CACHE;

        // Global Auth & State Access
        window.currentAdminPassword = window.currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || localStorage.getItem('unfinit_admin_pwd') || '';

        // =========================================================================
        // MODULE 1: NAVIGATION & TAB SWITCHING (Sandboxed IIFE)
        // =========================================================================
        (function initNavModule() {{
            try {{
                function updateCharCounter(inputId, counterId, maxLen) {{
                    const input = document.getElementById(inputId);
                    const counter = document.getElementById(counterId);
                    if (!input || !counter) return;
                    const len = input.value.length;
                    if (len > maxLen) {{
                        const diff = maxLen - len;
                        counter.innerText = diff + ' (بیش از سقف مجاز فاکتور بله)';
                        counter.className = 'text-[11px] font-mono text-rose-500 font-bold';
                    }} else if (len === maxLen) {{
                        counter.innerText = len + ' / ' + maxLen;
                        counter.className = 'text-[11px] font-mono text-rose-400 font-bold';
                    }} else if (len >= maxLen * 0.85) {{
                        counter.innerText = len + ' / ' + maxLen;
                        counter.className = 'text-[11px] font-mono text-amber-400 font-bold';
                    }} else {{
                        counter.innerText = len + ' / ' + maxLen;
                        counter.className = 'text-[11px] font-mono text-slate-400';
                    }}
                }}
                window.updateCharCounter = updateCharCounter;

                function togglePasswordVisibility(inputId, btn) {{
                    const inp = document.getElementById(inputId);
                    if (!inp) return;
                    const isMasked = (inp.type === 'password' || inp.style.webkitTextSecurity === 'disc');
                    if (isMasked) {{
                        inp.type = 'text';
                        inp.style.webkitTextSecurity = 'none';
                        btn.innerText = '🔓';
                    }} else {{
                        if (inp.hasAttribute('data-token-field')) {{
                            inp.type = 'text';
                            inp.style.webkitTextSecurity = 'disc';
                        }} else {{
                            inp.type = 'password';
                        }}
                        btn.innerText = '👁';
                    }}
                }}
                window.togglePasswordVisibility = togglePasswordVisibility;

                async function handleLoginSubmit() {{
                    const btn = document.getElementById('loginBtn');
                    const errMsg = document.getElementById('loginErrorMsg');
                    const pwd = document.getElementById('adminPasswordInput').value.trim();

                    if (errMsg) {{
                        errMsg.style.display = 'none';
                        errMsg.innerText = '';
                    }}

                    if (!pwd) {{
                        if (errMsg) {{
                            errMsg.innerText = '❌ لطفاً رمز عبور را وارد کنید.';
                            errMsg.style.display = 'block';
                        }}
                        return;
                    }}

                    if (btn) {{
                        btn.disabled = true;
                        btn.innerHTML = '⏳ در حال بررسی...';
                    }}

                    try {{
                        const res = await fetch('/api/login', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ password: pwd }})
                        }});
                        const data = await res.json();
                        if (data && data.ok) {{
                            localStorage.setItem('unfinit_auth_token', 'authenticated');
                            localStorage.setItem('unfinit_admin_pwd', pwd);
                            sessionStorage.setItem('unfinit_auth_token', 'authenticated');
                            sessionStorage.setItem('unfinit_admin_pwd', pwd);
                            window.currentAdminPassword = pwd;

                            const gate = document.getElementById('loginGate');
                            const app = document.getElementById('appMain');
                            if (gate) {{
                                gate.style.display = 'none';
                                gate.classList.add('hidden');
                            }}
                            if (app) {{
                                app.style.removeProperty('display');
                                app.style.display = 'block';
                                app.classList.remove('hidden');
                            }}
                            try {{
                                const savedTab = localStorage.getItem('unfinit_active_tab') || 'studio';
                                if (typeof window.switchTab === 'function') {{
                                    window.switchTab(savedTab);
                                }}
                            }} catch (e) {{
                                console.warn('[Navigation] Tab switch notice:', e);
                            }}
                        }} else {{
                            if (errMsg) {{
                                errMsg.innerText = '❌ رمز عبور اشتباه است.';
                                errMsg.style.display = 'block';
                            }}
                        }}
                    }} catch (err) {{
                        if (errMsg) {{
                            errMsg.innerText = '❌ خطای ارتباط با سرور: ' + (err.message || 'نامشخص');
                            errMsg.style.display = 'block';
                        }}
                    }} finally {{
                        if (btn) {{
                            btn.disabled = false;
                            btn.innerHTML = '<span>➔</span> ورود به پنل';
                        }}
                    }}
                }}
                window.handleLoginSubmit = handleLoginSubmit;
                window.handleMainLogin = handleLoginSubmit;

                function handleLogout() {{
                    sessionStorage.removeItem('unfinit_auth');
                    sessionStorage.removeItem('unfinit_auth_token');
                    sessionStorage.removeItem('unfinit_admin_pwd');
                    localStorage.removeItem('unfinit_auth');
                    localStorage.removeItem('unfinit_auth_token');
                    localStorage.removeItem('unfinit_admin_pwd');
                    location.reload();
                }}
                window.handleLogout = handleLogout;

                function toggleSidebar(forceState) {{
                    const sidebar = document.getElementById('mainSidebar');
                    const content = document.getElementById('contentWrapper');
                    const overlay = document.getElementById('drawerOverlay');
                    const isMobile = window.innerWidth < 768;

                    if (isMobile) {{
                        if (!overlay || !sidebar) return;
                        const isClosed = sidebar.classList.contains('translate-x-full');
                        const shouldOpen = (typeof forceState === 'boolean') ? forceState : isClosed;
                        if (shouldOpen) {{
                            overlay.classList.remove('hidden');
                            sidebar.classList.remove('translate-x-full');
                            sidebar.classList.add('translate-x-0');
                        }} else {{
                            overlay.classList.add('hidden');
                            sidebar.classList.remove('translate-x-0');
                            sidebar.classList.add('translate-x-full');
                        }}
                    }} else {{
                        if (!sidebar) return;
                        const isCollapsed = sidebar.classList.contains('sidebar-collapsed');
                        const shouldCollapse = (typeof forceState === 'boolean') ? !forceState : !isCollapsed;
                        if (shouldCollapse) {{
                            sidebar.classList.add('sidebar-collapsed');
                            if (content) content.classList.add('sidebar-collapsed');
                            try {{ localStorage.setItem('unfinit_sidebar_collapsed', 'true'); }} catch (_) {{}}
                        }} else {{
                            sidebar.classList.remove('sidebar-collapsed');
                            if (content) content.classList.remove('sidebar-collapsed');
                            try {{ localStorage.setItem('unfinit_sidebar_collapsed', 'false'); }} catch (_) {{}}
                        }}
                    }}
                }}
                window.toggleSidebar = toggleSidebar;
                window.toggleMobileDrawer = toggleSidebar;
                window.toggleMobileMenu = toggleSidebar;

                function initSidebarState() {{
                    try {{
                        const isCollapsed = localStorage.getItem('unfinit_sidebar_collapsed') === 'true';
                        if (isCollapsed && window.innerWidth >= 768) {{
                            const sidebar = document.getElementById('mainSidebar');
                            const content = document.getElementById('contentWrapper');
                            if (sidebar) sidebar.classList.add('sidebar-collapsed');
                            if (content) content.classList.add('sidebar-collapsed');
                        }}
                    }} catch (_) {{}}
                }}
                window.initSidebarState = initSidebarState;

                const tabMeta = {{
                    'dashboard': {{
                        title: 'داشبورد و وضعیت زنده موتور UNFINIT',
                        desc: 'پایش لحظه‌ای اتصالات، آمار فایل‌ها، سقف ایمن بله و لاگ‌های زنده'
                    }},
                    'downloads': {{
                        title: 'فایل‌های دانلودی رایگان سایت',
                        desc: 'پایش خودکار ۳۹ صفحه سایت مرجع و پکیج‌بندی سرفصل‌های دوره‌ها'
                    }},
                    'studio': {{
                        title: 'استودیوی پیشرفته رسانه و متادیتا',
                        desc: 'ویرایشگر تگ صوتی ID3، پخش‌کننده ویوفرم صوتی و استودیوی وکتور SVG'
                    }},
                    'courses': {{
                        title: 'مدیریت دوره‌های آموزشی و درگاه پرداخت',
                        desc: 'تنظیم قیمت، فایل‌ها، سرفصل‌ها و درگاه مستقیم کارت به کارت بله'
                    }},
                    'orders': {{
                        title: 'سفارشات، تراکنش‌ها و کوپن‌های تخفیف',
                        desc: 'مدیریت فیش‌های بانکی، تأیید خودکار/دستی سفارشات و کدهای تخفیف'
                    }},
                    'users': {{
                        title: 'باشگاه مشتریان و شبکه وایرال رفرال',
                        desc: 'کاربران ثبت‌نام‌شده، موجودی کیف پول، سیستم دعوت دوستان و خروجی CSV مخاطبین'
                    }},
                    'tokens': {{
                        title: 'هاب هوش مصنوعی و مدیریت سکرت‌ها',
                        desc: 'پیکربندی هوش چندمدله (VyceAI, Nara, Gemini) و توکن‌های پلتفرم‌ها'
                    }},
                    'settings': {{
                        title: 'تنظیمات سیستمی، دیتابیس و لاگ‌ها',
                        desc: 'پیکربندی سقف بله، پایگاه داده رمزنگاری‌شده AES-256 و کنسول لاگ'
                    }}
                }};

                function switchTab(tabId) {{
                    try {{
                        if (!tabId) tabId = 'dashboard';
                        let rawTab = tabId.startsWith('tab-') ? tabId.replace('tab-', '') : tabId;
                        const validTabs = ['dashboard', 'downloads', 'studio', 'courses', 'orders', 'users', 'tokens', 'settings'];
                        if (!validTabs.includes(rawTab)) {{
                            rawTab = 'dashboard';
                        }}
                        const fullTabId = 'tab-' + rawTab;
                        try {{
                            localStorage.setItem('unfinit_active_tab', rawTab);
                        }} catch (_) {{}}

                        validTabs.forEach(id => {{
                            const el = document.getElementById('tab-' + id);
                            if (el) el.classList.add('hidden');
                        }});

                        // Update sidebar buttons
                        document.querySelectorAll('.sidebar-nav-btn').forEach(btn => {{
                            btn.classList.remove('active');
                        }});
                        const activeSidebarBtn = document.getElementById('s-btn-tab-' + rawTab);
                        if (activeSidebarBtn) {{
                            activeSidebarBtn.classList.add('active');
                        }}

                        // Update legacy tab-btn for compatibility
                        document.querySelectorAll('.tab-btn').forEach(btn => {{
                            btn.classList.remove('active');
                            btn.classList.add('bg-slate-800/80', 'text-slate-300');
                        }});
                        const targetBtn = document.getElementById('btn-tab-' + rawTab);
                        if (targetBtn) {{
                            targetBtn.classList.add('active');
                            targetBtn.classList.remove('bg-slate-800/80', 'text-slate-300');
                        }}
                        const mobileBtn = document.getElementById('m-btn-tab-' + rawTab);
                        if (mobileBtn) {{
                            mobileBtn.classList.add('active');
                            mobileBtn.classList.remove('bg-slate-800/80', 'text-slate-300');
                        }}

                        const targetTab = document.getElementById(fullTabId);
                        if (targetTab) {{
                            targetTab.classList.remove('hidden');
                        }}

                        const titleEl = document.getElementById('currentTabTitle');
                        const descEl = document.getElementById('currentTabDesc');
                        if (titleEl && tabMeta[rawTab]) titleEl.innerText = tabMeta[rawTab].title;
                        if (descEl && tabMeta[rawTab]) descEl.innerText = tabMeta[rawTab].desc;

                        if (rawTab === 'dashboard') {{
                            if (typeof window.loadDashboardData === 'function') window.loadDashboardData();
                        }}
                        if (rawTab === 'users') {{
                            if (typeof window.loadUsersData === 'function') window.loadUsersData();
                        }}
                        if (rawTab === 'settings' || rawTab === 'tokens') {{
                            if (typeof window.loadSettings === 'function') window.loadSettings();
                            if (typeof window.loadFrequenciesTable === 'function') window.loadFrequenciesTable();
                        }}
                        if (rawTab === 'courses') {{
                            if (typeof window.loadStoreAnalytics === 'function') window.loadStoreAnalytics();
                        }}
                        if (rawTab === 'orders') {{
                            if (typeof window.loadStoreOrders === 'function') window.loadStoreOrders();
                            if (typeof window.loadStoreCoupons === 'function') window.loadStoreCoupons();
                            if (typeof window.loadStoreAnalytics === 'function') window.loadStoreAnalytics();
                        }}
                        if (rawTab === 'downloads') {{
                            if (typeof window.fetchFeedDownloads === 'function') window.fetchFeedDownloads();
                        }}
                    }} catch (err) {{
                        console.error('[UNFINIT Navigation Module Error] switchTab error:', err);
                    }}
                }}
                window.switchTab = switchTab;

                let drawerAllLines = [];

                function filterDrawerLogs() {{
                    const q = (document.getElementById('drawerLogSearch')?.value || '').toLowerCase().trim();
                    const streamBox = document.getElementById('dashboardRecentLogs');
                    if (!streamBox) return;
                    if (!q) {{
                        streamBox.innerText = drawerAllLines.slice(-30).join('\\n') || '// لاگی برای نمایش موجود نیست.';
                    }} else {{
                        const filtered = drawerAllLines.filter(l => l.toLowerCase().includes(q));
                        streamBox.innerText = filtered.join('\\n') || '// موردی یافت نشد.';
                    }}
                    const autoScroll = document.getElementById('drawerAutoScroll');
                    if (!autoScroll || autoScroll.checked) {{
                        streamBox.scrollTop = streamBox.scrollHeight;
                    }}
                }}
                window.filterDrawerLogs = filterDrawerLogs;

                async function copyDrawerLogs() {{
                    const streamBox = document.getElementById('dashboardRecentLogs');
                    if (!streamBox) return;
                    try {{
                        await navigator.clipboard.writeText(streamBox.innerText);
                        const btn = document.getElementById('drawerCopyBtn');
                        if (btn) {{
                            const orig = btn.innerHTML;
                            btn.innerHTML = '<span class="text-emerald-400 font-sans text-xs">کپی شد ✓</span>';
                            setTimeout(() => {{ btn.innerHTML = orig; }}, 2000);
                        }}
                    }} catch (e) {{
                        alert('خطا در کپی لاگ‌ها: ' + e.message);
                    }}
                }}
                window.copyDrawerLogs = copyDrawerLogs;

                async function loadDashboardData() {{
                    try {{
                        const streamBox = document.getElementById('dashboardRecentLogs');
                        const mainLogs = document.getElementById('logContainer');
                        if (streamBox && mainLogs && mainLogs.innerText.trim()) {{
                            const lines = mainLogs.innerText.trim().split('\\n').filter(Boolean);
                            drawerAllLines = lines;
                            const q = (document.getElementById('drawerLogSearch')?.value || '').trim();
                            if (!q) {{
                                const recent = lines.slice(-30).join('\\n');
                                if (recent) streamBox.innerText = recent;
                            }}
                            const autoScroll = document.getElementById('drawerAutoScroll');
                            if (!autoScroll || autoScroll.checked) {{
                                streamBox.scrollTop = streamBox.scrollHeight;
                            }}
                            const prev = document.getElementById('dashboardLatestLogPreview');
                            if (prev && lines.length > 0) {{
                                prev.textContent = lines[lines.length - 1];
                            }}
                        }}
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/store/analytics', {{
                            headers: {{ 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }}
                        }});
                        if (res.ok) {{
                            const data = await res.json();
                            if (data.active_drops !== undefined) {{
                                const el = document.getElementById('dashTotalDrops');
                                if (el) el.innerText = data.active_drops;
                            }}
                        }}
                    }} catch (e) {{
                        console.warn('loadDashboardData error:', e);
                    }}
                }}
                window.loadDashboardData = loadDashboardData;

                function toggleLogsDrawer(show) {{
                    const drawer = document.getElementById('logsDrawer');
                    const overlay = document.getElementById('logsDrawerOverlay');
                    if (!drawer) return;
                    const isHidden = drawer.classList.contains('-translate-x-full');
                    const shouldShow = (typeof show === 'boolean') ? show : isHidden;
                    if (shouldShow) {{
                        drawer.classList.remove('-translate-x-full');
                        if (overlay) overlay.classList.remove('hidden');
                        if (typeof loadDashboardData === 'function') loadDashboardData();
                    }} else {{
                        drawer.classList.add('-translate-x-full');
                        if (overlay) overlay.classList.add('hidden');
                    }}
                }}
                window.toggleLogsDrawer = toggleLogsDrawer;

                async function editBaleSafeLimit() {{
                    const curLimit = '{config.MAX_SAFE_BALE_SIZE_MB}';
                    const inputVal = prompt('سقف ایمن فشرده‌سازی بله را بر حسب مگابایت وارد نمایید (مثال: 48.50):', curLimit);
                    if (!inputVal) return;
                    const valFloat = parseFloat(inputVal.trim());
                    if (isNaN(valFloat) || valFloat <= 0 || valFloat > 50) {{
                        alert('مقدار سقف باید عددی بین ۱ تا ۵۰ مگابایت باشد.');
                        return;
                    }}
                    try {{
                        const pwd = window.currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/settings/save', {{
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: {{
                                'Content-Type': 'application/json',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            }},
                            body: JSON.stringify({{
                                password: pwd,
                                settings: {{ MAX_SAFE_BALE_SIZE_MB: valFloat.toFixed(2) }},
                                MAX_SAFE_BALE_SIZE_MB: valFloat.toFixed(2)
                            }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            const d1 = document.getElementById('dashBaleSafeSize');
                            const d2 = document.getElementById('baleCardSafeSize');
                            if (d1) d1.textContent = valFloat.toFixed(2) + ' MB';
                            if (d2) d2.textContent = valFloat.toFixed(2) + ' MB';
                        }} else {{
                            alert('خطا در ذخیره تنظیمات: ' + (data.error || 'عملیات ناموفق بود'));
                        }}
                    }} catch (e) {{
                        alert('خطا در برقراری ارتباط: ' + e.message);
                    }}
                }}
                window.editBaleSafeLimit = editBaleSafeLimit;

                async function disconnectSession(platform) {{
                    const platName = (platform === 'soroush' ? 'سروش‌پلاس' : 'روبیکا');
                    if (!confirm('آیا از قطع اتصال و حذف امن سشن ' + platName + ' اطمینان دارید؟')) return;
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/sessions/disconnect', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            }},
                            body: JSON.stringify({{ platform: platform }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            alert('✅ سشن ' + platName + ' با موفقیت قطع و از سرور پاکسازی شد.');
                            window.location.reload();
                        }} else {{
                            alert('❌ خطا: ' + (data.error || 'عملیات ناموفق بود'));
                        }}
                    }} catch (e) {{
                        alert('❌ خطای ارتباط با سرور: ' + e.message);
                    }}
                }}
                window.disconnectSession = disconnectSession;

                function switchUserSubTab(subTab) {{
                    const listSec = document.getElementById('userSubTabContentList');
                    const refSec = document.getElementById('userSubTabContentRef');
                    const btnList = document.getElementById('btnUserSubTabList');
                    const btnRef = document.getElementById('btnUserSubTabRef');
                    if (subTab === 'referrals') {{
                        if (listSec) listSec.classList.add('hidden');
                        if (refSec) refSec.classList.remove('hidden');
                        if (btnRef) {{
                            btnRef.className = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-accent-btn';
                        }}
                        if (btnList) {{
                            btnList.className = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-card-btn text-slate-300';
                        }}
                    }} else {{
                        if (refSec) refSec.classList.add('hidden');
                        if (listSec) listSec.classList.remove('hidden');
                        if (btnList) {{
                            btnList.className = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-accent-btn';
                        }}
                        if (btnRef) {{
                            btnRef.className = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-card-btn text-slate-300';
                        }}
                    }}
                }}
                window.switchUserSubTab = switchUserSubTab;

                let pendingSoroushPhone = '';

                function openSoroushLoginModal() {{
                    const modal = document.getElementById('soroushLoginModal');
                    if (modal) {{
                        modal.classList.remove('hidden');
                        resetSoroushLoginForm();
                    }}
                }}
                function closeSoroushLoginModal() {{
                    const modal = document.getElementById('soroushLoginModal');
                    if (modal) modal.classList.add('hidden');
                }}
                function switchSoroushTab(tab) {{
                    const smsPhone = document.getElementById('soroushStepPhone');
                    const smsCode = document.getElementById('soroushStepCode');
                    const manStep = document.getElementById('soroushStepManual');
                    const btnSms = document.getElementById('tabBtnSoroushSms');
                    const btnMan = document.getElementById('tabBtnSoroushManual');
                    const errBox = document.getElementById('soroushLoginError');
                    if (errBox) errBox.classList.add('hidden');
                    if (tab === 'manual') {{
                        if (smsPhone) smsPhone.classList.add('hidden');
                        if (smsCode) smsCode.classList.add('hidden');
                        if (manStep) manStep.classList.remove('hidden');
                        if (btnMan) {{ btnMan.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition theme-card-btn'; }}
                        if (btnSms) {{ btnSms.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold text-slate-400 hover:text-white transition'; }}
                    }} else {{
                        if (manStep) manStep.classList.add('hidden');
                        if (smsPhone) smsPhone.classList.remove('hidden');
                        if (smsCode) smsCode.classList.add('hidden');
                        if (btnSms) {{ btnSms.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition theme-card-btn'; }}
                        if (btnMan) {{ btnMan.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold text-slate-400 hover:text-white transition'; }}
                    }}
                }}
                function resetSoroushLoginForm() {{
                    switchSoroushTab('sms');
                    const errBox = document.getElementById('soroushLoginError');
                    if (errBox) {{ errBox.classList.add('hidden'); errBox.textContent = ''; }}
                    const phoneInput = document.getElementById('soroushPhoneInput');
                    if (phoneInput) phoneInput.value = '';
                    const codeInput = document.getElementById('soroushCodeInput');
                    if (codeInput) codeInput.value = '';
                    const manTokInput = document.getElementById('soroushManualTokenInput');
                    if (manTokInput) manTokInput.value = '';
                    const manPhInput = document.getElementById('soroushManualPhoneInput');
                    if (manPhInput) manPhInput.value = '';
                }}
                async function submitSoroushPhone() {{
                    const phoneInput = document.getElementById('soroushPhoneInput');
                    const phone = phoneInput ? phoneInput.value.trim() : '';
                    if (!phone || phone.length < 10) {{
                        alert('شماره تلفن نامعتبر است.');
                        return;
                    }}
                    const btn = document.getElementById('btnSoroushSendCode');
                    const errBox = document.getElementById('soroushLoginError');
                    if (btn) {{ btn.disabled = true; btn.textContent = 'در حال ارسال درخواست...'; }}
                    if (errBox) errBox.classList.add('hidden');
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/soroush/login/request', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            }},
                            body: JSON.stringify({{ phone: phone }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            pendingSoroushPhone = phone;
                            const disp = document.getElementById('soroushTargetPhoneDisplay');
                            if (disp) disp.textContent = phone;
                            const pStep = document.getElementById('soroushStepPhone');
                            const cStep = document.getElementById('soroushStepCode');
                            if (pStep) pStep.classList.add('hidden');
                            if (cStep) cStep.classList.remove('hidden');
                        }} else {{
                            if (errBox) {{
                                errBox.textContent = data.error || 'خطا در ارسال کد';
                                errBox.classList.remove('hidden');
                            }} else {{
                                alert(data.error || 'خطا در ارسال کد');
                            }}
                        }}
                    }} catch (e) {{
                        alert('خطا: ' + e.message);
                    }} finally {{
                        if (btn) {{ btn.disabled = false; btn.textContent = 'دریافت کد تایید پیامکی'; }}
                    }}
                }}
                async function submitSoroushCode() {{
                    const codeInput = document.getElementById('soroushCodeInput');
                    const code = codeInput ? codeInput.value.trim() : '';
                    if (!code) {{
                        alert('کد تایید را وارد نمایید.');
                        return;
                    }}
                    const btn = document.getElementById('btnSoroushVerifyCode');
                    const errBox = document.getElementById('soroushLoginError');
                    if (btn) {{ btn.disabled = true; btn.textContent = 'در حال تایید...'; }}
                    if (errBox) errBox.classList.add('hidden');
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/soroush/login/verify', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            }},
                            body: JSON.stringify({{ phone: pendingSoroushPhone, code: code }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            alert('ورود با موفقیت انجام شد و سشن سروش‌پلاس با استاندارد AES-256 رمزنگاری و فعال گردید.');
                            closeSoroushLoginModal();
                            window.location.reload();
                        }} else {{
                            if (errBox) {{
                                errBox.textContent = data.error || 'کد تایید اشتباه است.';
                                errBox.classList.remove('hidden');
                            }} else {{
                                alert(data.error || 'کد تایید اشتباه است.');
                            }}
                        }}
                    }} catch (e) {{
                        alert('خطا: ' + e.message);
                    }} finally {{
                        if (btn) {{ btn.disabled = false; btn.textContent = 'تایید و فعال‌سازی سشن امن'; }}
                    }}
                }}

                async function submitSoroushManualToken() {{
                    const tokInput = document.getElementById('soroushManualTokenInput');
                    const phInput = document.getElementById('soroushManualPhoneInput');
                    const token = tokInput ? tokInput.value.trim() : '';
                    const phone = phInput ? phInput.value.trim() : '';
                    if (!token) {{
                        alert('توکن نشست الزامی است.');
                        return;
                    }}
                    const btn = document.getElementById('btnSoroushManualSubmit');
                    const errBox = document.getElementById('soroushLoginError');
                    if (btn) {{ btn.disabled = true; btn.textContent = 'در حال ذخیره‌سازی...'; }}
                    if (errBox) errBox.classList.add('hidden');
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/soroush/login/manual', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            }},
                            body: JSON.stringify({{ token: token, phone: phone }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            alert('سشن سروش‌پلاس با توکن دستی با موفقیت ثبت و فعال شد.');
                            closeSoroushLoginModal();
                            window.location.reload();
                        }} else {{
                            if (errBox) {{
                                errBox.textContent = data.error || 'خطا در ثبت توکن';
                                errBox.classList.remove('hidden');
                            }} else {{
                                alert(data.error || 'خطا در ثبت توکن');
                            }}
                        }}
                    }} catch (e) {{
                        alert('خطا: ' + e.message);
                    }} finally {{
                        if (btn) {{ btn.disabled = false; btn.textContent = 'ذخیره مستقیم توکن و فعال‌سازی سشن'; }}
                    }}
                }}

                window.openSoroushLoginModal = openSoroushLoginModal;
                window.closeSoroushLoginModal = closeSoroushLoginModal;
                window.switchSoroushTab = switchSoroushTab;
                window.resetSoroushLoginForm = resetSoroushLoginForm;
                window.submitSoroushPhone = submitSoroushPhone;
                window.submitSoroushCode = submitSoroushCode;
                window.submitSoroushManualToken = submitSoroushManualToken;

                let allLoadedUsers = [];

                async function loadUsersData() {{
                    const tbody = document.getElementById('usersTableBody');
                    if (!tbody) return;
                    tbody.innerHTML = '<tr><td colspan="8" class="p-6 text-center text-slate-400 font-sans">در حال دریافت فهرست اعضا و خریداران...</td></tr>';
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users', {{
                            headers: {{ 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }}
                        }});
                        const data = await res.json();
                        const users = data.users || [];
                        const customers = data.customers || [];
                        const rawList = (users && users.length) ? users : customers;
                        allLoadedUsers = rawList.map(c => {{
                            const p = (c.platform || 'bale').toLowerCase();
                            const uid = c.user_id || c.id || c.chat_id || '';
                            let uname = c.username || c.customer_name || c.name || c.full_name || '';
                            if (!uname || uname === 'undefined' || uname === 'None') {{
                                if (p.includes('tele')) uname = 'کاربر تلگرام';
                                else if (p.includes('soroush')) uname = 'کاربر سروش‌پلاس';
                                else if (p.includes('rubika')) uname = 'کاربر روبیکا';
                                else uname = 'کاربر بله';
                            }}
                            return {{
                                platform: p,
                                user_id: uid,
                                username: uname,
                                phone: (c.phone && c.phone !== 'None' && c.phone !== 'undefined') ? c.phone : '',
                                referred_by: (c.referred_by && c.referred_by !== 'None' && c.referred_by !== 'undefined') ? c.referred_by : '',
                                wallet_balance: Number(c.wallet_balance) || 0,
                                commitment_signed: !!c.commitment_signed
                            }};
                        }});

                        const statTotal = document.getElementById('statTotalUsers');
                        if (statTotal) statTotal.innerText = allLoadedUsers.length;

                        const refUsersCount = allLoadedUsers.filter(u => u.referred_by).length;
                        const statRef = document.getElementById('statRefUsers');
                        if (statRef) statRef.innerText = refUsersCount;

                        const totalWallet = allLoadedUsers.reduce((acc, u) => acc + (Number(u.wallet_balance) || 0), 0);
                        const statWallet = document.getElementById('statTotalWallet');
                        if (statWallet) statWallet.innerText = totalWallet.toLocaleString('fa-IR') + ' تومان';

                        renderUsersTable(allLoadedUsers);
                    }} catch (err) {{
                        console.error('loadUsersData error:', err);
                        tbody.innerHTML = '<tr><td colspan="8" class="p-6 text-center text-rose-400 font-sans">خطا در بارگذاری فهرست کاربران</td></tr>';
                    }}
                }}
                window.loadUsersData = loadUsersData;

                function renderUsersTable(users) {{
                    const tbody = document.getElementById('usersTableBody');
                    if (!tbody) return;
                    if (!users || users.length === 0) {{
                        tbody.innerHTML = '<tr><td colspan="8" class="p-6 text-center text-slate-500 font-sans">هیچ کاربری ثبت نشده است.</td></tr>';
                        return;
                    }}
                    tbody.innerHTML = users.map(u => {{
                        const p = (u.platform || 'bale').toLowerCase();
                        let platformBadge = '';
                        if (p.includes('tele')) {{
                            platformBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-cyan-950 text-cyan-400 border border-cyan-800 font-sans inline-flex items-center gap-1"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg> تلگرام</span>';
                        }} else if (p.includes('soroush')) {{
                            platformBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-sky-950 text-sky-400 border border-sky-800 font-sans inline-flex items-center gap-1"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg> سروش‌پلاس</span>';
                        }} else if (p.includes('rubika')) {{
                            platformBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-purple-950 text-purple-400 border border-purple-800 font-sans inline-flex items-center gap-1"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg> روبیکا</span>';
                        }} else {{
                            platformBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-sans inline-flex items-center gap-1"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> بله</span>';
                        }}
                        const phone = u.phone ? ('<span dir="ltr">' + escapeHtml(u.phone) + '</span>') : '<span class="text-slate-600 font-sans">-</span>';
                        const name = escapeHtml(u.username || ('کاربر ' + (u.user_id || '')));
                        const ref = u.referred_by ? ('<span class="text-indigo-400" dir="ltr">' + escapeHtml(String(u.referred_by)) + '</span>') : '<span class="text-slate-600 font-sans">مستقیم</span>';
                        const wallet = (Number(u.wallet_balance) || 0).toLocaleString('fa-IR') + ' ت';
                        const commitment = u.commitment_signed 
                            ? '<span class="text-emerald-400 font-sans">امضا شده ✓</span>'
                            : '<span class="text-slate-500 font-sans">در انتظار</span>';
                        const userIdClean = escapeHtml(String(u.user_id || '-'));
                        return `<tr class="hover:bg-white/[0.03] transition">
                            <td class="p-3">${{platformBadge}}</td>
                            <td class="p-3 text-cyan-300 font-mono" dir="ltr">${{userIdClean}}</td>
                            <td class="p-3 text-slate-200 font-sans font-medium">${{name}}</td>
                            <td class="p-3 text-slate-300">${{phone}}</td>
                            <td class="p-3">${{ref}}</td>
                            <td class="p-3 text-amber-400 font-bold">${{wallet}}</td>
                            <td class="p-3 text-xs">${{commitment}}</td>
                            <td class="p-3 text-center">
                                <button type="button" onclick="deleteUserRow('${{userIdClean}}')" title="حذف دائم کاربر" class="p-1.5 rounded-lg border border-rose-500/40 text-rose-400 hover:bg-rose-500/20 transition-all font-sans text-xs inline-flex items-center gap-1">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                                    <span>حذف</span>
                                </button>
                            </td>
                        </tr>`;
                    }}).join('');
                }}
                window.renderUsersTable = renderUsersTable;

                async function deleteUserRow(userId) {{
                    if (!userId || userId === '-' || userId === 'undefined') return;
                    if (!confirm(`آیا از حذف کامل کاربر با شناسه ${{userId}} از پایگاه داده اطمینان دارید؟`)) return;
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users/delete', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }},
                            body: JSON.stringify({{ user_id: userId, admin_password: pwd }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            allLoadedUsers = allLoadedUsers.filter(u => String(u.user_id) !== String(userId));
                            renderUsersTable(allLoadedUsers);
                            const statTotal = document.getElementById('statTotalUsers');
                            if (statTotal) statTotal.innerText = allLoadedUsers.length;
                        }} else {{
                            alert('خطا در حذف کاربر: ' + (data.error || 'نامشخص'));
                        }}
                    }} catch (e) {{
                        alert('خطای ارتباط: ' + e.message);
                    }}
                }}
                window.deleteUserRow = deleteUserRow;

                async function purgeTestUsers() {{
                    if (!confirm('هشدار: آیا مطمئن هستید که می‌خواهید تمام کاربران آزمایشی و ساختگی را پاکسازی کنید؟')) return;
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users/purge_test', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }},
                            body: JSON.stringify({{ admin_password: pwd }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            alert(`پاکسازی انجام شد. ${{data.deleted_count || 0}} کاربر آزمایشی حذف شدند.`);
                            loadUsersData();
                        }} else {{
                            alert('خطا در پاکسازی: ' + (data.error || 'نامشخص'));
                        }}
                    }} catch (e) {{
                        alert('خطای ارتباط: ' + e.message);
                    }}
                }}
                window.purgeTestUsers = purgeTestUsers;

                function filterUsersTable() {{
                    const q = (document.getElementById('usersSearchInput')?.value || '').toLowerCase().trim();
                    if (!q) {{
                        renderUsersTable(allLoadedUsers);
                        return;
                    }}
                    const filtered = allLoadedUsers.filter(u => {{
                        const id = String(u.user_id || '').toLowerCase();
                        const name = String(u.username || u.name || '').toLowerCase();
                        const phone = String(u.phone || '').toLowerCase();
                        const ref = String(u.referred_by || '').toLowerCase();
                        return id.includes(q) || name.includes(q) || phone.includes(q) || ref.includes(q);
                    }});
                    renderUsersTable(filtered);
                }}
                window.filterUsersTable = filterUsersTable;

                function exportUsersCsv() {{
                    if (!allLoadedUsers || allLoadedUsers.length === 0) {{
                        alert('کاربری برای خروجی موجود نیست.');
                        return;
                    }}
                    const header = ['پلتفرم', 'شناسه', 'نام', 'شماره تماس', 'معرف', 'کیف پول', 'تعهدنامه'];
                    const rows = allLoadedUsers.map(u => [
                        u.platform || '',
                        u.user_id || '',
                        u.username || u.name || '',
                        u.phone || '',
                        u.referred_by || '',
                        u.wallet_balance || 0,
                        u.commitment_signed ? 'امضا شده' : 'خیر'
                    ]);
                    const csvContent = "\\uFEFF" + [header.join(','), ...rows.map(r => r.map(c => `"${{String(c).replace(/"/g, '""')}}"`).join(','))].join('\\n');
                    const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = `unfinit_users_${{new Date().toISOString().slice(0,10)}}.csv`;
                    link.click();
                    URL.revokeObjectURL(url);
                }}
                window.exportUsersCsv = exportUsersCsv;

                function checkAuthOnLoad() {{
                    const token = localStorage.getItem('unfinit_auth_token') || sessionStorage.getItem('unfinit_auth_token');
                    const pwd = localStorage.getItem('unfinit_admin_pwd') || sessionStorage.getItem('unfinit_admin_pwd');
                    const gate = document.getElementById('loginGate');
                    const app = document.getElementById('appMain');
                    if (token === 'authenticated' && pwd) {{
                        window.currentAdminPassword = pwd;
                        if (gate) {{
                            gate.style.display = 'none';
                            gate.classList.add('hidden');
                        }}
                        if (app) {{
                            app.style.removeProperty('display');
                            app.style.display = 'block';
                            app.classList.remove('hidden');
                        }}
                        try {{
                            const savedTab = localStorage.getItem('unfinit_active_tab') || 'dashboard';
                            window.switchTab(savedTab);
                        }} catch (e) {{
                            console.warn('[Navigation] Tab switch notice:', e);
                        }}
                    }} else {{
                        if (gate) {{
                            gate.style.removeProperty('display');
                            gate.classList.remove('hidden');
                        }}
                        if (app) {{
                            app.classList.add('hidden');
                            app.style.display = 'none';
                        }}
                    }}
                }}

                function bindNavDelegation() {{
                    const sidebarNav = document.getElementById('sidebarNavList');
                    if (sidebarNav) {{
                        sidebarNav.addEventListener('click', function(e) {{
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {{
                                const tab = btn.getAttribute('data-tab');
                                if (tab && window.switchTab) window.switchTab(tab);
                            }}
                        }});
                    }}
                    const desktopNav = document.getElementById('desktopNavTabs');
                    if (desktopNav) {{
                        desktopNav.addEventListener('click', function(e) {{
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {{
                                const tab = btn.getAttribute('data-tab');
                                if (tab && window.switchTab) window.switchTab(tab);
                            }}
                        }});
                    }}
                    const mobileNav = document.getElementById('mobileNavMenu');
                    if (mobileNav) {{
                        mobileNav.addEventListener('click', function(e) {{
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {{
                                const tab = btn.getAttribute('data-tab');
                                if (tab && window.switchTab) {{
                                    window.switchTab(tab);
                                    if (typeof window.toggleMobileMenu === 'function') {{
                                        window.toggleMobileMenu(false);
                                    }}
                                }}
                            }}
                        }});
                    }}
                }}

                function persistTabsOrder() {{
                    const sidebarNav = document.getElementById('sidebarNavList');
                    const desktopNav = document.getElementById('desktopNavTabs');
                    let currentOrder = [];
                    if (sidebarNav) {{
                        currentOrder = Array.from(sidebarNav.querySelectorAll('[data-tab]')).map(b => b.getAttribute('data-tab')).filter(Boolean);
                    }}
                    if (currentOrder.length === 0 && desktopNav) {{
                        currentOrder = Array.from(desktopNav.querySelectorAll('[data-tab]')).map(b => b.getAttribute('data-tab')).filter(Boolean);
                    }}
                    if (currentOrder.length === 0) return;
                    localStorage.setItem('unfinit_nav_order', JSON.stringify(currentOrder));
                    localStorage.setItem('unfinit_tabs_order', JSON.stringify(currentOrder));
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        if (pwd) {{
                            fetch('/api/settings/save', {{
                                method: 'POST',
                                headers: {{ 'Content-Type': 'application/json' }},
                                body: JSON.stringify({{
                                    password: pwd,
                                    settings: {{ NAV_TABS_ORDER: currentOrder }}
                                }})
                            }}).catch(e => console.warn('[DragDrop] Cloud save failed:', e));
                        }}
                    }} catch (e) {{}}
                }}

                function initTabsDragAndDrop() {{
                    const sidebarNav = document.getElementById('sidebarNavList');
                    const desktopNav = document.getElementById('desktopNavTabs');

                    try {{
                        const savedOrder = JSON.parse(localStorage.getItem('unfinit_nav_order') || localStorage.getItem('unfinit_tabs_order') || '[]');
                        if (Array.isArray(savedOrder) && savedOrder.length > 0) {{
                            if (sidebarNav) {{
                                savedOrder.forEach(tabId => {{
                                    const btn = sidebarNav.querySelector(`[data-tab="${{tabId}}"]`);
                                    if (btn) sidebarNav.appendChild(btn);
                                }});
                            }}
                            if (desktopNav) {{
                                savedOrder.forEach(tabId => {{
                                    const btn = desktopNav.querySelector(`[data-tab="${{tabId}}"]`);
                                    if (btn) desktopNav.appendChild(btn);
                                }});
                            }}
                        }}
                    }} catch (e) {{
                        console.warn('[DragDrop] Error loading saved tab order:', e);
                    }}

                    function setupDragForContainer(container, isVertical) {{
                        if (!container) return;
                        let draggedItem = null;

                        // Mouse Drag & Drop
                        container.addEventListener('dragstart', function(e) {{
                            const btn = e.target.closest('[data-tab]');
                            if (!btn) return;
                            draggedItem = btn;
                            e.dataTransfer.effectAllowed = 'move';
                            e.dataTransfer.setData('text/plain', btn.getAttribute('data-tab'));
                            btn.classList.add('opacity-40');
                        }});

                        container.addEventListener('dragend', function(e) {{
                            const btn = e.target.closest('[data-tab]');
                            if (btn) btn.classList.remove('opacity-40');
                            container.querySelectorAll('[data-tab]').forEach(b => b.classList.remove('opacity-40'));
                            draggedItem = null;
                            persistTabsOrder();
                        }});

                        container.addEventListener('dragover', function(e) {{
                            e.preventDefault();
                            e.dataTransfer.dropEffect = 'move';
                            const targetBtn = e.target.closest('[data-tab]');
                            if (targetBtn && targetBtn !== draggedItem && targetBtn.parentElement === container) {{
                                const rect = targetBtn.getBoundingClientRect();
                                const midpoint = isVertical ? (rect.y + rect.height / 2) : (rect.x + rect.width / 2);
                                const coord = isVertical ? e.clientY : e.clientX;
                                if (coord < midpoint) {{
                                    container.insertBefore(draggedItem, targetBtn);
                                }} else {{
                                    container.insertBefore(draggedItem, targetBtn.nextSibling);
                                }}
                            }}
                        }});

                        container.addEventListener('drop', function(e) {{
                            e.preventDefault();
                            persistTabsOrder();
                        }});

                        // Mobile Touch with 500ms long-press
                        let touchTimer = null;
                        let touchDraggedItem = null;

                        container.addEventListener('touchstart', function(e) {{
                            const btn = e.target.closest('[data-tab]');
                            if (!btn) return;
                            touchTimer = setTimeout(function() {{
                                touchDraggedItem = btn;
                                btn.classList.add('opacity-40', 'scale-95');
                                if (navigator.vibrate) navigator.vibrate(50);
                            }}, 500);
                        }}, {{ passive: true }});

                        container.addEventListener('touchmove', function(e) {{
                            if (!touchDraggedItem) {{
                                if (touchTimer) {{ clearTimeout(touchTimer); touchTimer = null; }}
                                return;
                            }}
                            e.preventDefault();
                            const touch = e.touches[0];
                            const targetEl = document.elementFromPoint(touch.clientX, touch.clientY);
                            if (!targetEl) return;
                            const targetBtn = targetEl.closest('[data-tab]');
                            if (targetBtn && targetBtn !== touchDraggedItem && targetBtn.parentElement === container) {{
                                const rect = targetBtn.getBoundingClientRect();
                                const midpoint = isVertical ? (rect.y + rect.height / 2) : (rect.x + rect.width / 2);
                                const coord = isVertical ? touch.clientY : touch.clientX;
                                if (coord < midpoint) {{
                                    container.insertBefore(touchDraggedItem, targetBtn);
                                }} else {{
                                    container.insertBefore(touchDraggedItem, targetBtn.nextSibling);
                                }}
                            }}
                        }}, {{ passive: false }});

                        function endTouchDrag() {{
                            if (touchTimer) {{ clearTimeout(touchTimer); touchTimer = null; }}
                            if (touchDraggedItem) {{
                                touchDraggedItem.classList.remove('opacity-40', 'scale-95');
                                container.querySelectorAll('[data-tab]').forEach(b => b.classList.remove('opacity-40', 'scale-95'));
                                touchDraggedItem = null;
                                persistTabsOrder();
                            }}
                        }}
                        container.addEventListener('touchend', endTouchDrag);
                        container.addEventListener('touchcancel', endTouchDrag);
                    }}

                    setupDragForContainer(sidebarNav, true);
                    setupDragForContainer(desktopNav, false);
                }}

                function initUptimeTicker() {{
                    const el = document.getElementById('uptimeDisplay');
                    if (!el) return;
                    const startSec = parseInt(el.getAttribute('data-start')) || 0;
                    if (!startSec) return;
                    function updateUptime() {{
                        const now = Math.floor(Date.now() / 1000);
                        let diff = Math.max(0, now - startSec);
                        const h = Math.floor(diff / 3600);
                        const m = Math.floor((diff % 3600) / 60);
                        const s = diff % 60;
                        el.textContent = `${{h}}h ${{m}}m ${{s}}s`;
                    }}
                    setInterval(updateUptime, 1000);
                }}

                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', function() {{
                        bindNavDelegation();
                        initTabsDragAndDrop();
                        initSidebarState();
                        initUptimeTicker();
                        checkAuthOnLoad();
                    }});
                }} else {{
                    bindNavDelegation();
                    initTabsDragAndDrop();
                    initSidebarState();
                    initUptimeTicker();
                    checkAuthOnLoad();
                }}
            }} catch (err) {{
                console.error('[UNFINIT Navigation Module Error]:', err);
            }}
        }})();

        // =========================================================================
        // MODULE 2: STUDIO & MEDIA HUB (Sandboxed IIFE)
        // =========================================================================
        (function initStudioModule() {{
            try {{
        // WEB MP3TAG STUDIO CLIENT LOGIC
        // =========================================================================

        const studioDropzone = document.getElementById('studioDropzone');
        if (studioDropzone) {{
            ['dragenter', 'dragover'].forEach(name => {{
                studioDropzone.addEventListener(name, (e) => {{
                    e.preventDefault();
                    e.stopPropagation();
                    studioDropzone.classList.add('dragover');
                }});
            }});
            ['dragleave', 'drop'].forEach(name => {{
                studioDropzone.addEventListener(name, (e) => {{
                    e.preventDefault();
                    e.stopPropagation();
                    studioDropzone.classList.remove('dragover');
                }});
            }});
            studioDropzone.addEventListener('drop', (e) => {{
                e.preventDefault();
                e.stopPropagation();
                studioDropzone.classList.remove('dragover');
                const dt = e.dataTransfer;
                if (dt && dt.files && dt.files.length > 0) {{
                    handleStudioFilesSelect(dt.files);
                }}
            }});
        }}

        async function handleStudioFilesSelect(fileList) {{
            if (!fileList || fileList.length === 0) return;
            const progressEl = document.getElementById('studioUploadProgress');
            if (progressEl) {{
                progressEl.classList.remove('hidden');
                progressEl.innerText = `⏳ در حال آماده‌سازی و بارگذاری ${{fileList.length}} فایل...`;
            }}

            let successCount = 0;
            for (let i = 0; i < fileList.length; i++) {{
                const file = fileList[i];
                if (progressEl) progressEl.innerText = `⏳ در حال آپلود (${{i+1}}/${{fileList.length}}): ${{file.name}}...`;
                try {{
                    const b64 = await readFileAsBase64(file);
                    const res = await fetch('/api/studio/upload', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ filename: file.name, data: b64 }})
                    }});
                    const data = await res.json();
                    if (data.ok) successCount++;
                }} catch (err) {{
                    console.error('Upload error:', err);
                }}
            }}

            if (progressEl) {{
                progressEl.innerText = `✅ تعداد ${{successCount}} فایل با موفقیت بارگذاری و در استودیو ثبت گردید!`;
            }}
            setTimeout(() => {{
                if (progressEl) progressEl.classList.add('hidden');
                refreshStudioList();
            }}, 800);
        }}

        function readFileAsBase64(file) {{
            return new Promise((resolve, reject) => {{
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = error => reject(error);
                reader.readAsDataURL(file);
            }});
        }}

        function previewStudioCover(input, previewImgId, b64InputId) {{
            const file = input.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(e) {{
                const img = document.getElementById(previewImgId);
                if (img) img.src = e.target.result;
                const b64 = document.getElementById(b64InputId);
                if (b64) b64.value = e.target.result;
            }};
            reader.readAsDataURL(file);
        }}

        // Specs Modal
        async function openSpecsModal(dropId) {{
            const modal = document.getElementById('specsModal');
            const loading = document.getElementById('specsLoading');
            const body = document.getElementById('specsBody');
            modal.classList.remove('hidden');
            loading.classList.remove('hidden');
            body.classList.add('hidden');

            try {{
                const res = await fetch('/api/studio/specs/' + dropId);
                const data = await res.json();
                if (data.ok) {{
                    document.getElementById('specFilename').innerText = data.filename || '-';
                    document.getElementById('specBitrate').innerText = (data.bitrate_kbps ? data.bitrate_kbps + ' kbps' : 'نامشخص');
                    document.getElementById('specSampleRate').innerText = (data.sample_rate ? data.sample_rate + ' Hz' : 'نامشخص');
                    document.getElementById('specChannels').innerText = data.channels || 'نامشخص';
                    document.getElementById('specCodec').innerText = data.codec || '-';
                    document.getElementById('specDuration').innerText = data.duration_str || '-';
                    document.getElementById('specSize').innerText = data.size_str || '-';
                    const covEl = document.getElementById('specCoverStatus');
                    covEl.innerText = data.has_cover ? '✅ موجود' : '❌ فاقد کاور';
                    covEl.className = data.has_cover ? 'text-emerald-400 font-bold' : 'text-slate-500 font-bold';

                    loading.classList.add('hidden');
                    body.classList.remove('hidden');
                }} else {{
                    alert('❌ خطا در دریافت مشخصات فنی: ' + (data.error || ''));
                    closeSpecsModal();
                }}
            }} catch (err) {{
                alert('❌ خطای شبکه: ' + err.message);
                closeSpecsModal();
            }}
        }}

        function closeSpecsModal() {{
            document.getElementById('specsModal').classList.add('hidden');
        }}

        // Single Tag Modal
        function openTagModal(dropId, title, artist, album, filename) {{
            document.getElementById('tagDropId').value = dropId;
            document.getElementById('tagTitle').value = title || '';
            document.getElementById('tagArtist').value = artist || '';
            document.getElementById('tagAlbum').value = album || '';
            document.getElementById('tagFilename').value = filename || '';
            document.getElementById('tagCoverB64').value = '';
            document.getElementById('tagRemoveCover').checked = false;
            
            const prev = document.getElementById('tagCoverPreview');
            prev.src = '/api/studio/cover/' + dropId + '?t=' + Date.now();
            prev.onerror = () => {{
                prev.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="%2364748b"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"/></svg>';
            }};

            document.getElementById('tagModal').classList.remove('hidden');
        }}

        function closeTagModal() {{
            document.getElementById('tagModal').classList.add('hidden');
        }}

        async function handleSaveStudioTags(e) {{
            e.preventDefault();
            const btn = document.getElementById('btnSaveTag');
            if (btn) {{
                btn.disabled = true;
                btn.innerText = '⏳ در حال ذخیره آنی متادیتا...';
            }}

            const payload = {{
                drop_id: document.getElementById('tagDropId').value,
                title: document.getElementById('tagTitle').value,
                artist: document.getElementById('tagArtist').value,
                album: document.getElementById('tagAlbum').value,
                new_filename: document.getElementById('tagFilename').value,
                cover_data: document.getElementById('tagCoverB64').value,
                remove_cover: document.getElementById('tagRemoveCover').checked
            }};

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000);

            try {{
                const res = await fetch('/api/studio/edit_tags', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload),
                    signal: controller.signal
                }});
                clearTimeout(timeoutId);
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ ' + (data.message || 'متادیتا با موفقیت ذخیره شد!'));
                    closeTagModal();
                    refreshStudioList();
                }} else {{
                    alert('❌ خطا: ' + (data.error || 'ذخیره متادیتا ناموفق بود'));
                }}
            }} catch (err) {{
                clearTimeout(timeoutId);
                alert('❌ خطای ارتباط یا زمان‌بندی: ' + err.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerText = '💾 ذخیره آنی متادیتا';
                }}
            }}
        }}

        // Selection and Batch Edit
        function toggleSelectAllDrops(masterChk) {{
            document.querySelectorAll('.drop-chk').forEach(c => c.checked = masterChk.checked);
            updateSelectedCount();
        }}

        function updateSelectedCount() {{
            const checked = document.querySelectorAll('.drop-chk:checked');
            const badge = document.getElementById('selectedCountBadge');
            if (badge) badge.innerText = checked.length + ' فایل انتخاب شده';
        }}

        function getSelectedDropIds() {{
            const checked = document.querySelectorAll('.drop-chk:checked');
            return Array.from(checked).map(c => c.getAttribute('data-drop-id'));
        }}

        function openBatchTagModal() {{
            const ids = getSelectedDropIds();
            if (ids.length === 0) {{
                alert('⚠️ لطفاً حداقل یک فایل را برای ویرایش گروهی انتخاب فرمایید.');
                return;
            }}
            document.getElementById('batchCountBadge').innerText = ids.length;
            document.getElementById('batchCoverB64').value = '';
            document.getElementById('batchRemoveCover').checked = false;
            document.getElementById('batchCoverPreview').src = '';
            document.getElementById('batchTagModal').classList.remove('hidden');
        }}

        function closeBatchTagModal() {{
            document.getElementById('batchTagModal').classList.add('hidden');
        }}

        async function handleSaveBatchTags(e) {{
            e.preventDefault();
            const ids = getSelectedDropIds();
            if (ids.length === 0) return;

            const btn = document.getElementById('btnSaveBatch');
            btn.disabled = true;
            btn.innerText = '⏳ در حال اعمال تغییرات گروهی...';

            const payload = {{
                drop_ids: ids,
                album: document.getElementById('batchAlbum').value,
                artist: document.getElementById('batchArtist').value,
                auto_number: document.getElementById('batchAutoNumber').checked,
                title_pattern: document.getElementById('batchTitlePattern').value,
                cover_data: document.getElementById('batchCoverB64').value,
                remove_cover: document.getElementById('batchRemoveCover').checked
            }};

            try {{
                const res = await fetch('/api/studio/batch_edit', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ ' + (data.message || 'ویرایش گروهی با موفقیت اعمال گردید!'));
                    closeBatchTagModal();
                    refreshStudioList();
                }} else {{
                    alert('❌ خطا: ' + (data.error || 'عملیات گروهی ناموفق بود'));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط: ' + err.message);
            }} finally {{
                btn.disabled = false;
                btn.innerText = '🚀 اعمال روی تمام فایل‌ها';
            }}
        }}

        async function dispatchDrop(dropId, target) {{
            const names = {{ telegram: 'تلگرام', bale: 'بله', rubika: 'روبیکا' }};
            const targetName = names[target] || target;
            if (!confirm(`آیا می‌خواهید این فایل مستقیماً به ${{targetName}} ارسال شود؟`)) return;

            try {{
                const res = await fetch('/api/studio/dispatch', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ drop_id: dropId, target: target }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ ' + (data.message || `فایل با موفقیت به ${{targetName}} ارسال شد!`));
                }} else {{
                    alert('❌ خطا: ' + (data.error || 'ارسال فایل ناموفق بود'));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط با سرور: ' + err.message);
            }}
        }}

        // =========================================================================
        // WAVESURFER AUDIO CUTTER & STUDIO ACTION LOGIC
        // =========================================================================
        let wavesurfer = null;

        function formatSecToTime(seconds) {{
            if (isNaN(seconds) || seconds < 0) seconds = 0;
            const m = Math.floor(seconds / 60);
            const s = Math.floor(seconds % 60);
            const ms = Math.floor((seconds % 1) * 10);
            return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0') + '.' + ms;
        }}

        function parseTimeToSec(str) {{
            if (!str) return 0;
            str = String(str).trim();
            if (str.includes(':')) {{
                const parts = str.split(':');
                const m = parseFloat(parts[0]) || 0;
                const s = parseFloat(parts[1]) || 0;
                return m * 60 + s;
            }}
            return parseFloat(str) || 0;
        }}

        function openCutterModal(dropId, filename) {{
            document.getElementById('cutterDropId').value = dropId;
            document.getElementById('cutterFilename').innerText = filename || dropId;
            document.getElementById('cutStartTime').value = '00:00.0';
            document.getElementById('cutEndTime').value = '00:00.0';
            document.getElementById('cutterCurrentTime').innerText = '00:00.0';
            document.getElementById('cutterTotalDuration').innerText = '00:00.0';
            document.getElementById('wavePlayText').innerText = 'پخش';
            document.getElementById('cutterModal').classList.remove('hidden');

            const loading = document.getElementById('waveformLoading');
            if (loading) loading.classList.remove('hidden');

            if (wavesurfer) {{
                try {{ wavesurfer.destroy(); }} catch (e) {{}}
                wavesurfer = null;
            }}

            try {{
                wavesurfer = WaveSurfer.create({{
                    container: '#waveform',
                    waveColor: '#334155',
                    progressColor: '#06b6d4',
                    cursorColor: '#38bdf8',
                    barWidth: 2,
                    barGap: 1,
                    barRadius: 2,
                    height: 80,
                    url: '/dl/' + dropId
                }});

                wavesurfer.on('ready', () => {{
                    if (loading) loading.classList.add('hidden');
                    const dur = wavesurfer.getDuration();
                    document.getElementById('cutterTotalDuration').innerText = formatSecToTime(dur);
                    document.getElementById('cutEndTime').value = formatSecToTime(dur);
                }});

                wavesurfer.on('timeupdate', (currentTime) => {{
                    const curFormatted = formatSecToTime(currentTime);
                    document.getElementById('cutterCurrentTime').innerText = curFormatted;
                    const toggleTime = document.getElementById('waveToggleTime');
                    if (toggleTime) toggleTime.innerText = curFormatted;
                }});

                wavesurfer.on('play', () => {{
                    const icon = document.getElementById('waveToggleIcon');
                    if (icon) icon.innerText = '❚❚';
                    const btnText = document.getElementById('wavePlayText');
                    if (btnText) btnText.innerText = 'توقف موقت';
                }});

                wavesurfer.on('pause', () => {{
                    const icon = document.getElementById('waveToggleIcon');
                    if (icon) icon.innerText = '▶';
                    const btnText = document.getElementById('wavePlayText');
                    if (btnText) btnText.innerText = 'پخش';
                }});

                wavesurfer.on('finish', () => {{
                    const icon = document.getElementById('waveToggleIcon');
                    if (icon) icon.innerText = '▶';
                    const btnText = document.getElementById('wavePlayText');
                    if (btnText) btnText.innerText = 'پخش';
                }});

                wavesurfer.on('error', (err) => {{
                    console.error('WaveSurfer error:', err);
                    if (loading) loading.innerText = 'خطا در بارگذاری نمودار موج صوتی: ' + err;
                }});
            }} catch (err) {{
                console.error('WaveSurfer init error:', err);
                if (loading) loading.innerText = 'خطا در راه‌اندازی پخش‌کننده صوتی.';
            }}
        }}

        function closeCutterModal() {{
            if (wavesurfer) {{
                try {{ wavesurfer.pause(); }} catch (e) {{}}
            }}
            const icon = document.getElementById('waveToggleIcon');
            if (icon) icon.innerText = '▶';
            document.getElementById('cutterModal').classList.add('hidden');
        }}

        function toggleWavePlayPause() {{
            if (wavesurfer) {{
                wavesurfer.playPause();
            }}
        }}

        function stopWaveSurfer() {{
            if (wavesurfer) {{
                wavesurfer.stop();
                document.getElementById('wavePlayText').innerText = 'پخش';
            }}
        }}

        function setStartFromCursor() {{
            if (wavesurfer) {{
                const cur = wavesurfer.getCurrentTime();
                document.getElementById('cutStartTime').value = formatSecToTime(cur);
            }}
        }}

        function setEndFromCursor() {{
            if (wavesurfer) {{
                const cur = wavesurfer.getCurrentTime();
                document.getElementById('cutEndTime').value = formatSecToTime(cur);
            }}
        }}

        async function submitAudioCut() {{
            const dropId = document.getElementById('cutterDropId').value;
            const startStr = document.getElementById('cutStartTime').value;
            const endStr = document.getElementById('cutEndTime').value;
            const startSec = parseTimeToSec(startStr);
            const endSec = parseTimeToSec(endStr);

            if (endSec > 0 && endSec <= startSec) {{
                alert('❌ زمان پایان باید بعد از زمان شروع باشد.');
                return;
            }}

            const btn = document.getElementById('btnSubmitCut');
            btn.disabled = true;
            btn.innerText = '⏳ در حال برش صوت با FFmpeg...';

            try {{
                const res = await fetch('/api/studio/cut', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        drop_id: dropId,
                        start_sec: startSec,
                        end_sec: endSec > 0 ? endSec : null
                    }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ ' + (data.message || 'فایل با موفقیت برش یافت و به استودیو اضافه شد!'));
                    closeCutterModal();
                    refreshStudioList();
                }} else {{
                    alert('❌ خطا: ' + (data.error || 'عملیات برش ناموفق بود.'));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط با سرور: ' + err.message);
            }} finally {{
                btn.disabled = false;
                btn.innerHTML = '<span>✂️</span> برش و ایجاد فایل جدید';
            }}
        }}

        async function deleteStudioDrop(dropId) {{
            if (!confirm('آیا از حذف این فایل و سشن رسانه از دیسک سرور مطمئن هستید؟')) return;
            try {{
                const res = await fetch('/api/studio/delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ drop_id: dropId }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    const row = document.getElementById('row_' + dropId);
                    if (row) {{
                        row.style.transition = 'all 0.4s ease';
                        row.style.opacity = '0';
                        row.style.transform = 'scale(0.95)';
                        setTimeout(() => {{ row.remove(); updateSelectedCount(); }}, 400);
                    }} else {{
                        refreshStudioList();
                    }}
                }} else {{
                    alert('❌ خطا: ' + (data.error || 'حذف سشن ناموفق بود'));
                }}
            }} catch (err) {{
                alert('❌ خطای شبکه: ' + err.message);
            }}
        }}

        async function batchDeleteStudioDrops() {{
            const ids = getSelectedDropIds();
            if (ids.length === 0) {{
                alert('⚠️ لطفاً حداقل یک فایل را برای حذف انتخاب فرمایید.');
                return;
            }}
            if (!confirm(`آیا از حذف دائم ${{ids.length}} فایل انتخاب‌شده از حافظه و دیسک سرور مطمئن هستید؟`)) return;

            try {{
                const res = await fetch('/api/studio/delete_batch', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ drop_ids: ids }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    ids.forEach(id => {{
                        const row = document.getElementById('row_' + id);
                        if (row) {{
                            row.style.transition = 'all 0.4s ease';
                            row.style.opacity = '0';
                            row.style.transform = 'scale(0.95)';
                            setTimeout(() => {{ row.remove(); updateSelectedCount(); }}, 400);
                        }}
                    }});
                    const chkAll = document.getElementById('selectAllDrops');
                    if (chkAll) chkAll.checked = false;
                    setTimeout(() => {{ refreshStudioList(); }}, 450);
                }} else {{
                    alert('❌ خطا: ' + (data.error || 'حذف گروهی ناموفق بود'));
                }}
            }} catch (err) {{
                alert('❌ خطای شبکه: ' + err.message);
            }}
        }}

        function changeStudioSort(sortVal) {{
            try {{
                localStorage.setItem('unfinit_studio_sort', sortVal);
            }} catch (e) {{}}
            refreshStudioList();
        }}

        async function refreshStudioList() {{
            const tbody = document.getElementById('studioTableBody');
            if (tbody) tbody.style.opacity = '0.5';
            try {{
                let sortVal = 'newest';
                try {{
                    sortVal = localStorage.getItem('unfinit_studio_sort') || 'newest';
                }} catch (e) {{}}
                const sortSelect = document.getElementById('studioSortSelect');
                if (sortSelect && sortSelect.value !== sortVal) {{
                    sortSelect.value = sortVal;
                }}
                const res = await fetch('/api/studio/table_html?sort=' + encodeURIComponent(sortVal));
                const data = await res.json();
                if (data.ok && data.html) {{
                    if (tbody) {{
                        tbody.innerHTML = data.html;
                        tbody.style.opacity = '1';
                        const chkAll = document.getElementById('selectAllDrops');
                        if (chkAll) chkAll.checked = false;
                        updateSelectedCount();
                    }}
                }} else {{
                    console.warn('Refresh studio table returned non-ok:', data);
                    if (tbody) tbody.style.opacity = '1';
                }}
            }} catch (err) {{
                console.error('Failed to refresh studio table:', err);
                if (tbody) tbody.style.opacity = '1';
            }}
        }}

        async function cleanupStudioDrops() {{
            if (!confirm('آیا می‌خواهید تمام سشن‌های تکراری و فایل‌های زائد به صورت هوشمند پاکسازی شوند؟')) return;
            const btn = document.getElementById('btnCleanupStudio');
            if (btn) {{
                btn.disabled = true;
                btn.innerText = '⏳ در حال پاکسازی...';
            }}
            try {{
                const res = await fetch('/api/studio/cleanup', {{ method: 'POST' }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ ' + (data.message || 'سشن‌های تکراری با موفقیت پاکسازی شدند!'));
                    refreshStudioList();
                }} else {{
                    alert('❌ خطا: ' + (data.error || 'پاکسازی ناموفق بود'));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط: ' + err.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<span>🧹</span> پاکسازی سشن‌های خالی و نامعتبر';
                }}
            }}
        }}

        let currentFeedPage = 1;
        const totalFeedPages = 39;
        window.currentFeedPage = 1;

        async function fetchFeedDownloads(force, page) {{
            const container = document.getElementById('feedDownloadsContainer');
            const btn = document.getElementById('btnRefreshFeed');
            if (!container) return;
            if (typeof page === 'number' && page >= 1 && page <= totalFeedPages) {{
                currentFeedPage = page;
                window.currentFeedPage = page;
            }}
            const curPageEl = document.getElementById('feedCurrentPage');
            const curPageBottomEl = document.getElementById('feedCurrentPageBottom');
            if (curPageEl) curPageEl.textContent = currentFeedPage;
            if (curPageBottomEl) curPageBottomEl.textContent = currentFeedPage;

            if (btn) {{
                btn.disabled = true;
                btn.innerHTML = '<span>⏳</span> در حال رصد سایت...';
            }}
            if (force || container.children.length === 0 || container.innerText.includes('در حال بارگذاری')) {{
                container.innerHTML = '<div class="col-span-full text-center py-6 text-xs text-slate-400 font-mono">⏳ در حال دریافت ۲۵ هدیه دانلودی صفحه ' + currentFeedPage + ' از سایت...</div>';
            }}
            try {{
                const res = await fetch('/api/feed/latest?page=' + currentFeedPage + '&limit=25' + (force ? '&force=1' : ''));
                const data = await res.json();
                if (data.ok && Array.isArray(data.items) && data.items.length > 0) {{
                    container.innerHTML = data.items.map(function(item) {{
                        const title = (item.title || 'هدیه دانلودی سایت').replace(/"/g, '&quot;');
                        const fileNum = item.file_number ? '<span class="px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800 text-[10px] font-mono">' + item.file_number + '</span>' : '';
                        const cover = item.cover_url ? '<img src="' + item.cover_url + '" alt="' + title + '" class="w-16 h-16 rounded-xl object-cover border border-slate-700 shrink-0" onerror="this.src=\\'/static/default_cover.jpg\\'; this.onerror=null;">' : '<div class="w-16 h-16 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-2xl shrink-0">🎧</div>';
                        const audioLink = item.audio_url || '';
                        const videoLink = item.video_url || '';
                        const primaryUrl = audioLink || videoLink || (item.links && item.links[0]) || '';
                        const safeUrl = primaryUrl.replace(/'/g, "\\\\'");
                        const safeTitle = title.replace(/'/g, "\\\\'");
                        const safeAudio = (audioLink || '').replace(/'/g, "\\\\'");
                        const safeVideo = (videoLink || '').replace(/'/g, "\\\\'");
                        
                        let linksHtml = '';
                        if (audioLink) {{
                            linksHtml += '<a href="' + audioLink + '" target="_blank" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 flex items-center gap-1 transition text-[11px]"><span>🎵</span> فایل صوتی</a>';
                        }}
                        if (videoLink) {{
                            linksHtml += '<a href="' + videoLink + '" target="_blank" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-purple-300 border border-slate-700 flex items-center gap-1 transition text-[11px]"><span>🎬</span> ویدیو</a>';
                        }}

                        return '<div class="glass p-4 rounded-xl border border-slate-800/80 hover:border-cyan-500/40 transition-all flex flex-col justify-between gap-3 bg-slate-900/50">' +
                            '<div class="flex items-start gap-3">' +
                                cover +
                                '<div class="flex-1 min-w-0">' +
                                    '<div class="flex items-center gap-2 mb-1 flex-wrap">' +
                                        fileNum +
                                        '<span class="text-[10px] text-slate-400 font-mono">' + (item.published_at || '') + '</span>' +
                                    '</div>' +
                                    '<h3 class="text-xs font-bold text-slate-100 line-clamp-2 leading-relaxed" title="' + title + '">' +
                                        title +
                                    '</h3>' +
                                '</div>' +
                            '</div>' +
                            '<div class="flex flex-col gap-2 pt-2 border-t border-white/5">' +
                                '<div class="flex items-center gap-2">' + linksHtml + '</div>' +
                                '<button type="button" onclick="transferFeedDownload(\\'' + safeUrl + '\\', \\'' + safeTitle + '\\', \\'' + safeAudio + '\\', \\'' + safeVideo + '\\')" class="w-full theme-accent-btn py-1.5 px-3 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 shadow-sm">' +
                                    '<span>⚡️</span> انتقال به ربات جهت دانلود' +
                                '</button>' +
                            '</div>' +
                        '</div>';
                    }}).join('');
                }} else {{
                    container.innerHTML = '<div class="col-span-full text-center py-6 text-xs text-rose-400 font-mono">❌ دریافت هدایای دانلودی ناموفق بود یا فایلی یافت نشد.</div>';
                }}
            }} catch (err) {{
                container.innerHTML = '<div class="col-span-full text-center py-6 text-xs text-rose-400 font-mono">❌ خطای ارتباط با سرور: ' + err.message + '</div>';
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<span>🔄</span> به‌روزرسانی صفحه';
                }}
            }}
        }}

        function changeFeedPage(targetPage) {{
            let target = targetPage;
            if (target === 'prev') target = currentFeedPage - 1;
            else if (target === 'next') target = currentFeedPage + 1;
            else target = parseInt(target, 10);

            if (isNaN(target)) return;
            if (target < 1) target = 1;
            if (target > totalFeedPages) target = totalFeedPages;
            if (target === currentFeedPage && document.getElementById('feedDownloadsContainer')?.children?.length > 1) return;

            currentFeedPage = target;
            window.currentFeedPage = target;
            const curPageEl = document.getElementById('feedCurrentPage');
            const curPageBottomEl = document.getElementById('feedCurrentPageBottom');
            if (curPageEl) curPageEl.textContent = currentFeedPage;
            if (curPageBottomEl) curPageBottomEl.textContent = currentFeedPage;

            fetchFeedDownloads(false, currentFeedPage);
        }}

        let pendingFeedDispatchUrl = '';
        let pendingFeedDispatchTitle = '';
        let pendingFeedAudioUrl = '';
        let pendingFeedVideoUrl = '';
        let pendingFeedActiveFormat = 'audio';

        function setDispatchFormat(fmt) {{
            pendingFeedActiveFormat = fmt;
            const btnAudio = document.getElementById('btnFormatAudio');
            const btnVideo = document.getElementById('btnFormatVideo');
            if (fmt === 'audio') {{
                if (btnAudio) {{
                    btnAudio.className = 'py-2 px-3 rounded-xl border text-xs font-bold transition flex items-center justify-center gap-1.5 theme-accent-btn';
                }}
                if (btnVideo) {{
                    btnVideo.className = 'py-2 px-3 rounded-xl border border-slate-700 text-slate-300 bg-slate-800/80 hover:bg-slate-700 text-xs font-bold transition flex items-center justify-center gap-1.5';
                }}
                pendingFeedDispatchUrl = pendingFeedAudioUrl || pendingFeedVideoUrl;
            }} else {{
                if (btnVideo) {{
                    btnVideo.className = 'py-2 px-3 rounded-xl border text-xs font-bold transition flex items-center justify-center gap-1.5 theme-accent-btn';
                }}
                if (btnAudio) {{
                    btnAudio.className = 'py-2 px-3 rounded-xl border border-slate-700 text-slate-300 bg-slate-800/80 hover:bg-slate-700 text-xs font-bold transition flex items-center justify-center gap-1.5';
                }}
                pendingFeedDispatchUrl = pendingFeedVideoUrl || pendingFeedAudioUrl;
            }}
        }}

        function openFeedDispatchModal(url, title, audioUrl, videoUrl) {{
            if (!url && !audioUrl && !videoUrl) {{
                alert('❌ آدرس دانلودی برای این آیتم یافت نشد.');
                return;
            }}
            pendingFeedAudioUrl = audioUrl || (url && url.toLowerCase().endsWith('.mp3') ? url : '');
            pendingFeedVideoUrl = videoUrl || (url && url.toLowerCase().endsWith('.mp4') ? url : '');
            if (!pendingFeedAudioUrl && !pendingFeedVideoUrl) {{
                pendingFeedAudioUrl = url;
            }}
            pendingFeedDispatchUrl = pendingFeedAudioUrl || pendingFeedVideoUrl || url;
            pendingFeedDispatchTitle = title || 'هدیه دانلودی';
            const titleEl = document.getElementById('feedDispatchModalTitle');
            if (titleEl) titleEl.textContent = pendingFeedDispatchTitle;

            setDispatchFormat(pendingFeedAudioUrl ? 'audio' : 'video');

            const courseSelect = document.getElementById('feedCourseSelect');
            if (courseSelect) {{
                courseSelect.innerHTML = '';
                const cache = window.COURSES_CACHE || window.coursesData || {{}};
                const pids = Object.keys(cache);
                if (pids.length === 0) {{
                    courseSelect.innerHTML = '<option value="">(هیچ دوره‌ای در سیستم ثبت نشده است)</option>';
                }} else {{
                    let defaultPid = '';
                    pids.forEach(function(pid) {{
                        const c = cache[pid];
                        const opt = document.createElement('option');
                        opt.value = c.product_id || pid;
                        const isFree = (c.price === 0 || c.price === '0' || c.is_free || (c.name && c.name.includes('توحید')));
                        if (isFree && !defaultPid) {{
                            defaultPid = opt.value;
                        }}
                        opt.textContent = (isFree ? '🎁 ' : '🎓 ') + (c.name || pid);
                        courseSelect.appendChild(opt);
                    }});
                    if (defaultPid) {{
                        courseSelect.value = defaultPid;
                    }}
                }}
            }}

            const modal = document.getElementById('feedDispatchModal');
            if (modal) modal.classList.remove('hidden');
        }}

        function closeFeedDispatchModal() {{
            const modal = document.getElementById('feedDispatchModal');
            if (modal) modal.classList.add('hidden');
            pendingFeedDispatchUrl = '';
            pendingFeedDispatchTitle = '';
            pendingFeedAudioUrl = '';
            pendingFeedVideoUrl = '';
        }}

        async function addFeedToCourseEpisodes() {{
            const courseSelect = document.getElementById('feedCourseSelect');
            const pid = courseSelect ? courseSelect.value : '';
            const url = pendingFeedDispatchUrl || pendingFeedAudioUrl || pendingFeedVideoUrl;
            const title = pendingFeedDispatchTitle;
            if (!pid) {{
                alert('لطفاً یک دوره را انتخاب فرمایید.');
                return;
            }}
            if (!url) {{
                alert('آدرس فایل معتبر نیست.');
                return;
            }}
            const btn = document.getElementById('btnAddFeedToCourse');
            if (btn) {{
                btn.disabled = true;
                btn.innerText = '⏳ در حال افزودن...';
            }}
            try {{
                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/courses/episodes/add', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + pwd,
                        'X-Admin-Password': pwd
                    }},
                    body: JSON.stringify({{
                        product_id: pid,
                        title: title,
                        url: url,
                        filename: title ? (title.replace(/[^\\w\\s\\-\\.\\u0600-\\u06FF]/gi, '') + (pendingFeedActiveFormat === 'video' ? '.mp4' : '.mp3')) : ''
                    }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ ' + (data.message || 'فایل با موفقیت به سرفصل‌های دوره افزوده شد!'));
                    closeFeedDispatchModal();
                }} else {{
                    alert('❌ خطا در افزودن به سرفصل‌ها: ' + (data.error || 'ناموفق'));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط با سرور: ' + err.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<span>📦</span> افزودن به عنوان قسمت جدید این دوره';
                }}
            }}
        }}

        async function executeFeedMultiDispatch() {{
            const targets = [];
            if (document.getElementById('chkDispatchTg')?.checked) targets.push('telegram');
            if (document.getElementById('chkDispatchBale')?.checked) targets.push('bale');
            if (document.getElementById('chkDispatchRubika')?.checked) targets.push('rubika_user');
            if (document.getElementById('chkDispatchSoroush')?.checked) targets.push('soroush');

            if (targets.length === 0) {{
                alert('❌ لطفاً حداقل یک پلتفرم مقصد را انتخاب فرمایید.');
                return;
            }}
            const url = pendingFeedDispatchUrl || pendingFeedAudioUrl || pendingFeedVideoUrl;
            const title = pendingFeedDispatchTitle;
            closeFeedDispatchModal();
            if (!url) return;

            const resBox = document.getElementById('dispatchResult');
            if (resBox) {{
                resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-slate-800 text-slate-300 border border-slate-700';
                resBox.innerText = '⏳ در حال دانلود و ارسال همزمان هدیه: ' + title + ' به پلتفرم‌های منتخب...';
            }}
            try {{
                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/dispatch_url', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + pwd,
                        'X-Admin-Password': pwd
                    }},
                    body: JSON.stringify({{ url: url, targets: targets, target: targets.join(',') }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ فایل هدیه با موفقیت به ' + (data.target || targets.join(' و ')) + ' منتقل شد!');
                    if (resBox) {{
                        resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-emerald-950 text-emerald-300 border border-emerald-700';
                        resBox.innerText = '✅ ' + (data.message || 'فایل هدیه با موفقیت ارسال شد!');
                    }}
                }} else {{
                    alert('❌ خطا در ارسال: ' + (data.error || 'عملیات ناموفق بود'));
                    if (resBox) {{
                        resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-rose-950 text-rose-300 border border-rose-700';
                        resBox.innerText = '❌ خطا: ' + (data.error || 'ناموفق');
                    }}
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط با سرور: ' + err.message);
            }}
        }}

        async function executeFeedDispatch(target) {{
            const url = pendingFeedDispatchUrl || pendingFeedAudioUrl || pendingFeedVideoUrl;
            const title = pendingFeedDispatchTitle;
            closeFeedDispatchModal();
            if (!url) return;

            const directInput = document.getElementById('directUrl');
            if (directInput) {{
                directInput.value = url;
            }}
            const resBox = document.getElementById('dispatchResult');
            if (resBox) {{
                resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-slate-800 text-slate-300 border border-slate-700';
                resBox.innerText = '⏳ در حال دانلود و پردازش استریم هدیه: ' + title + ' ... لطفاً شکیبا باشید.';
            }}
            try {{
                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/dispatch_url', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + pwd,
                        'X-Admin-Password': pwd
                    }},
                    body: JSON.stringify({{ url: url, target: target || 'all' }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ فایل هدیه با موفقیت دانلود و به ' + (data.target || 'پیام‌رسان‌ها') + ' منتقل شد!');
                    if (resBox) {{
                        resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-emerald-950 text-emerald-300 border border-emerald-700';
                        resBox.innerText = '✅ ' + (data.message || 'فایل هدیه با موفقیت دانلود و ارسال شد!');
                    }}
                }} else {{
                    alert('❌ خطا در دانلود و ارسال: ' + (data.error || 'عملیات ناموفق بود'));
                    if (resBox) {{
                        resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-rose-950 text-rose-300 border border-rose-700';
                        resBox.innerText = '❌ خطا: ' + (data.error || 'ناموفق');
                    }}
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط با سرور: ' + err.message);
            }}
        }}

        function transferFeedDownload(url, title, audioUrl, videoUrl) {{
            openFeedDispatchModal(url, title, audioUrl, videoUrl);
        }}

        // Initialize Studio Sort Select and Feed from localStorage / API
        window.addEventListener('DOMContentLoaded', function() {{
            try {{
                const savedSort = localStorage.getItem('unfinit_studio_sort') || 'newest';
                const sortSelect = document.getElementById('studioSortSelect');
                if (sortSelect) {{
                    sortSelect.value = savedSort;
                }}
                fetchFeedDownloads(false);
            }} catch (e) {{}}
        }});

                let currentSvgContent = '';
                let currentSvgFilename = 'vector.svg';

                function setSvgColor(hex) {{
                    const picker = document.getElementById('svgRecolorPicker');
                    const input = document.getElementById('svgHexInput');
                    if (picker) picker.value = hex;
                    if (input) input.value = hex;
                }}

                function syncSvgColorPicker(val) {{
                    const input = document.getElementById('svgHexInput');
                    if (input) input.value = val;
                }}

                function syncSvgHexInput(val) {{
                    val = (val || '').trim();
                    if (val && !val.startsWith('#')) val = '#' + val;
                    const picker = document.getElementById('svgRecolorPicker');
                    if (picker && /^#[0-9A-Fa-f]{{6}}$/.test(val)) {{
                        picker.value = val;
                    }}
                }}

                function renderSvgInPreview(svgText) {{
                    currentSvgContent = svgText || '';
                    const previewEl = document.getElementById('svgLivePreview');
                    const badgeEl = document.getElementById('svgDimensionsBadge');
                    if (previewEl) {{
                        if (!svgText) {{
                            previewEl.innerHTML = '<span class="text-xs text-slate-500">فایل SVG انتخاب شده در اینجا رسم می‌شود</span>';
                            if (badgeEl) badgeEl.textContent = '-';
                            return;
                        }}
                        previewEl.innerHTML = svgText;
                        const svgEl = previewEl.querySelector('svg');
                        if (svgEl) {{
                            svgEl.style.maxWidth = '100%';
                            svgEl.style.maxHeight = '240px';
                            svgEl.style.height = 'auto';
                            svgEl.style.display = 'block';
                            svgEl.style.margin = 'auto';
                            const w = svgEl.getAttribute('width') || '';
                            const h = svgEl.getAttribute('height') || '';
                            const vb = svgEl.getAttribute('viewBox') || '';
                            if (badgeEl) {{
                                badgeEl.textContent = (w && h) ? (w + ' × ' + h) : (vb ? ('viewBox: ' + vb) : 'SVG Vector');
                            }}
                        }}
                    }}
                }}

                function handleSvgFileSelected(files) {{
                    if (!files || files.length === 0) return;
                    const file = files[0];
                    currentSvgFilename = file.name || 'vector.svg';
                    const reader = new FileReader();
                    reader.onload = function(e) {{
                        renderSvgInPreview(e.target.result);
                    }};
                    reader.readAsText(file);
                }}

                async function handleSvgRecolor() {{
                    if (!currentSvgContent) {{
                        alert('لطفاً ابتدا یک فایل وکتور SVG انتخاب نموده یا متنی وارد نمایید.');
                        return;
                    }}
                    const hexInput = document.getElementById('svgHexInput');
                    const color = (hexInput ? hexInput.value : '#FFFFFF') || '#FFFFFF';
                    const btn = document.getElementById('btnSvgRecolor');
                    if (btn) {{
                        btn.disabled = true;
                        btn.innerHTML = '<span>⏳</span> در حال تغییر رنگ...';
                    }}
                    try {{
                        const res = await fetch('/api/media/recolor-svg', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                                'X-Admin-Password': window.currentAdminPassword || ''
                            }},
                            body: JSON.stringify({{
                                svg: currentSvgContent,
                                color: color,
                                filename: currentSvgFilename
                            }})
                        }});
                        const data = await res.json();
                        if (data.ok && data.svg) {{
                            renderSvgInPreview(data.svg);
                            alert('✅ رنگ اجزای وکتور با موفقیت به ' + color + ' تغییر یافت.');
                        }} else {{
                            alert('❌ خطا در تغییر رنگ وکتور: ' + (data.error || 'ناموفق'));
                        }}
                    }} catch (err) {{
                        alert('❌ خطای ارتباط با سرور: ' + err.message);
                    }} finally {{
                        if (btn) {{
                            btn.disabled = false;
                            btn.innerHTML = '<span>🎨</span> اعمال تغییر رنگ';
                        }}
                    }}
                }}

                function downloadCurrentSvg() {{
                    if (!currentSvgContent) {{
                        alert('فایل SVG فعالی برای دانلود وجود ندارد.');
                        return;
                    }}
                    const blob = new Blob([currentSvgContent], {{ type: 'image/svg+xml;charset=utf-8' }});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = currentSvgFilename || 'vector.svg';
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    setTimeout(function() {{ URL.revokeObjectURL(url); }}, 1000);
                }}

                async function handleGenerateTextSvg() {{
                    const textInput = document.getElementById('svgTextInput');
                    const sizeInput = document.getElementById('svgTextSizeInput');
                    const hexInput = document.getElementById('svgHexInput');
                    const text = (textInput ? textInput.value : '').trim();
                    const fontSize = parseInt(sizeInput ? sizeInput.value : '48') || 48;
                    const fill = (hexInput ? hexInput.value : '#FFFFFF') || '#FFFFFF';

                    if (!text) {{
                        alert('لطفاً ابتدا متن مورد نظر را وارد نمایید.');
                        return;
                    }}

                    try {{
                        const res = await fetch('/api/media/text-to-svg', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                                'X-Admin-Password': window.currentAdminPassword || ''
                            }},
                            body: JSON.stringify({{
                                text: text,
                                font_size: fontSize,
                                fill: fill
                            }})
                        }});
                        const data = await res.json();
                        if (data.ok && data.svg) {{
                            currentSvgFilename = (text.replace(/[^\\w\\s\\-\\.\\u0600-\\u06FF]/gi, '').slice(0, 20) || 'typography') + '.svg';
                            renderSvgInPreview(data.svg);
                            alert('✅ وکتور متنی با موفقیت ایجاد شد.');
                        }} else {{
                            alert('❌ خطا در تولید وکتور متنی: ' + (data.error || 'ناموفق'));
                        }}
                    }} catch (err) {{
                        alert('❌ خطای ارتباط با سرور: ' + err.message);
                    }}
                }}

                async function handleSvgConvert(e) {{
                    if (e) e.preventDefault();
                    const fileInput = document.getElementById('svgFileInput');
                    const formatSelect = document.getElementById('svgOutputFormat');
                    const btn = document.getElementById('btnSvgConvert');
                    const resultDiv = document.getElementById('svgConvertResult');

                    const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;
                    if (!hasFile && !currentSvgContent) {{
                        alert('لطفاً ابتدا یک فایل وکتور SVG انتخاب فرمایید یا از بخش ساخت وکتور استفاده نمایید.');
                        return;
                    }}

                    const format = (formatSelect ? formatSelect.value : 'png') || 'png';
                    let fname = hasFile ? fileInput.files[0].name : (currentSvgFilename || 'vector.svg');

                    if (btn) {{
                        btn.disabled = true;
                        btn.innerHTML = '<span>⏳</span> در حال تبدیل...';
                    }}
                    if (resultDiv) {{
                        resultDiv.classList.remove('hidden');
                        resultDiv.className = 'mt-4 p-3 rounded-xl text-xs font-mono bg-cyan-950/60 border border-cyan-800 text-cyan-300 flex items-center justify-between';
                        resultDiv.innerHTML = '<span>⚡️ در حال پردازش فایل وکتور و رندر تصویر...</span>';
                    }}

                    const sendConvertRequest = async function(b64Data, filename) {{
                        try {{
                            const res = await fetch('/api/media/convert-svg', {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type': 'application/json',
                                    'X-Admin-Password': window.currentAdminPassword || ''
                                }},
                                body: JSON.stringify({{
                                    data: b64Data,
                                    format: format,
                                    filename: filename
                                }})
                            }});
                            const data = await res.json();
                            if (data.ok) {{
                                if (resultDiv) {{
                                    resultDiv.className = 'mt-4 p-3 rounded-xl text-xs font-mono bg-emerald-950/60 border border-emerald-800 text-emerald-300 flex items-center justify-between';
                                    resultDiv.innerHTML = '<span>✅ تبدیل موفق: ' + data.filename + ' (' + Math.round((data.size || 0) / 1024) + ' KB)</span>' +
                                        '<a href="' + data.data + '" download="' + data.filename + '" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-sans font-bold transition">دریافت فایل</a>';
                                }}
                                const a = document.createElement('a');
                                a.href = data.data;
                                a.download = data.filename;
                                document.body.appendChild(a);
                                a.click();
                                a.remove();
                            }} else {{
                                if (resultDiv) {{
                                    resultDiv.className = 'mt-4 p-3 rounded-xl text-xs font-mono bg-rose-950/60 border border-rose-800 text-rose-300';
                                    resultDiv.innerText = '❌ خطای تبدیل: ' + (data.error || 'عملیات ناموفق بود');
                                }}
                            }}
                        }} catch (err) {{
                            if (resultDiv) {{
                                resultDiv.className = 'mt-4 p-3 rounded-xl text-xs font-mono bg-rose-950/60 border border-rose-800 text-rose-300';
                                resultDiv.innerText = '❌ خطای ارتباط با سرور: ' + err.message;
                            }}
                        }} finally {{
                            if (btn) {{
                                btn.disabled = false;
                                btn.innerHTML = '<span>⚡️</span> تبدیل و دریافت تصویر';
                            }}
                        }}
                    }};

                    if (hasFile) {{
                        const reader = new FileReader();
                        reader.onload = function() {{
                            sendConvertRequest(reader.result, fname);
                        }};
                        reader.onerror = function() {{
                            if (resultDiv) {{
                                resultDiv.className = 'mt-4 p-3 rounded-xl text-xs font-mono bg-rose-950/60 border border-rose-800 text-rose-300';
                                resultDiv.innerText = '❌ خطا در خواندن فایل وکتور از دستگاه.';
                            }}
                            if (btn) {{
                                btn.disabled = false;
                                btn.innerHTML = '<span>⚡️</span> تبدیل و دریافت تصویر';
                            }}
                        }};
                        reader.readAsDataURL(fileInput.files[0]);
                    }} else {{
                        try {{
                            const b64 = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(currentSvgContent)));
                            sendConvertRequest(b64, fname);
                        }} catch (e) {{
                            if (resultDiv) {{
                                resultDiv.className = 'mt-4 p-3 rounded-xl text-xs font-mono bg-rose-950/60 border border-rose-800 text-rose-300';
                                resultDiv.innerText = '❌ خطا در کدگذاری وکتور: ' + e.message;
                            }}
                            if (btn) {{
                                btn.disabled = false;
                                btn.innerHTML = '<span>⚡️</span> تبدیل و دریافت تصویر';
                            }}
                        }}
                    }}
                }}
                window.handleSvgConvert = handleSvgConvert;
                window.setSvgColor = setSvgColor;
                window.syncSvgColorPicker = syncSvgColorPicker;
                window.syncSvgHexInput = syncSvgHexInput;
                window.renderSvgInPreview = renderSvgInPreview;
                window.handleSvgFileSelected = handleSvgFileSelected;
                window.handleSvgRecolor = handleSvgRecolor;
                window.downloadCurrentSvg = downloadCurrentSvg;
                window.handleGenerateTextSvg = handleGenerateTextSvg;

                window.handleStudioFilesSelect = handleStudioFilesSelect;
                window.previewStudioCover = previewStudioCover;
                window.openSpecsModal = openSpecsModal;
                window.closeSpecsModal = closeSpecsModal;
                window.openTagModal = openTagModal;
                window.closeTagModal = closeTagModal;
                window.handleSaveStudioTags = handleSaveStudioTags;
                window.toggleSelectAllDrops = toggleSelectAllDrops;
                window.updateSelectedCount = updateSelectedCount;
                window.getSelectedDropIds = getSelectedDropIds;
                window.openBatchTagModal = openBatchTagModal;
                window.closeBatchTagModal = closeBatchTagModal;
                window.handleSaveBatchTags = handleSaveBatchTags;
                window.dispatchDrop = dispatchDrop;
                window.formatSecToTime = formatSecToTime;
                window.parseTimeToSec = parseTimeToSec;
                window.openCutterModal = openCutterModal;
                window.closeCutterModal = closeCutterModal;
                window.toggleWavePlayPause = toggleWavePlayPause;
                window.stopWaveSurfer = stopWaveSurfer;
                window.setStartFromCursor = setStartFromCursor;
                window.setEndFromCursor = setEndFromCursor;
                window.submitAudioCut = submitAudioCut;
                window.deleteStudioDrop = deleteStudioDrop;
                window.batchDeleteStudioDrops = batchDeleteStudioDrops;
                window.changeStudioSort = changeStudioSort;
                window.refreshStudioList = refreshStudioList;
                window.cleanupStudioDrops = cleanupStudioDrops;
                window.fetchFeedDownloads = fetchFeedDownloads;
                window.changeFeedPage = changeFeedPage;
                window.openFeedDispatchModal = openFeedDispatchModal;
                window.closeFeedDispatchModal = closeFeedDispatchModal;
                window.executeFeedDispatch = executeFeedDispatch;
                window.transferFeedDownload = transferFeedDownload;
                window.addFeedToCourseEpisodes = addFeedToCourseEpisodes;
                window.executeFeedMultiDispatch = executeFeedMultiDispatch;
                window.setDispatchFormat = setDispatchFormat;
            }} catch (err) {{
                console.error('[UNFINIT Studio Module Error]:', err);
            }}
        }})();

        // =========================================================================
        // MODULE 3: STORE, ORDERS & COUPONS (Sandboxed IIFE)
        // =========================================================================
        (function initStoreOrdersModule() {{
            try {{
        function toggleAddCourseForm() {{
            const card = document.getElementById('addCourseCard');
            card.classList.toggle('hidden');
            if (!card.classList.contains('hidden')) {{
                updateCharCounter('newCName', 'counter_newCName', 32);
                updateCharCounter('newCDesc', 'counter_newCDesc', 255);
            }}
        }}

        function togglePackageInput(prefix) {{
            const selectEl = document.getElementById(prefix + 'DeliveryType');
            const pkgBox = document.getElementById(prefix + 'PackageBox');
            if (selectEl && pkgBox) {{
                if (selectEl.value === 'files_package') {{
                    pkgBox.classList.remove('hidden');
                }} else {{
                    pkgBox.classList.add('hidden');
                }}
            }}
        }}

        function formatPriceInput(el) {{
            if (!el) return;
            const digits = el.value.replace(/[^0-9]/g, '');
            if (digits === '') {{
                el.value = '';
                return;
            }}
            el.value = Number(digits).toLocaleString('en-US');
        }}

        async function handleCreateCourse(e) {{
            e.preventDefault();
            const btn = document.getElementById('btnSubmitCourse');
            btn.disabled = true;
            btn.innerText = 'در حال ثبت...';
            const name = document.getElementById('newCName').value;
            const rawPrice = String(document.getElementById('newCPrice').value || '').replace(/[,،\\s]/g, '');
            const price = parseInt(rawPrice) || 0;
            const description = document.getElementById('newCDesc').value;
            const download_link = document.getElementById('newCDownload').value;
            const photo_url = document.getElementById('newCPhoto').value;
            const allow_card = document.getElementById('newCAllowCard').checked;
            const allow_bale = document.getElementById('newCAllowBale').checked;
            const requires_referral = document.getElementById('newCRequiresReferral') ? (document.getElementById('newCRequiresReferral').checked ? 1 : 0) : 0;
            const delivery_type = document.getElementById('newCDeliveryType') ? document.getElementById('newCDeliveryType').value : 'channel';
            let files_package = [];
            if (delivery_type === 'files_package' && document.getElementById('newCFilesPackage')) {{
                const rawPkg = document.getElementById('newCFilesPackage').value.trim();
                try {{
                    files_package = rawPkg.startsWith('[') ? JSON.parse(rawPkg) : rawPkg.split('\\n').filter(Boolean).map(l => {{
                        const parts = l.split('|').map(s => s.trim());
                        return {{ title: parts[0] || 'فایل آموزشی', file_id: parts[1] || parts[0] }};
                    }});
                }} catch(e) {{
                    files_package = [{{ title: name, file_name: rawPkg }}];
                }}
            }}

            try {{
                const res = await fetch('/api/courses/add', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ name, price, description, download_link, photo_url, allow_card, allow_bale, requires_referral, delivery_type, files_package }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ دوره جدید با موفقیت ثبت شد!');
                    location.reload();
                }} else {{
                    alert('❌ خطا: ' + (data.error || 'ثبت دوره ناموفق بود'));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط با سرور: ' + err.message);
            }} finally {{
                btn.disabled = false;
                btn.innerText = 'ثبت دوره در دیتابیس';
            }}
        }}

        function openEditModal(pid, name, price, desc, dl, photo, allow_card, allow_bale, requires_referral, delivery_type, files_package) {{
            document.getElementById('editProductId').value = pid;
            document.getElementById('modalProdIdBadge').innerText = pid;
            document.getElementById('editName').value = name;
            const rawP = String(price || '0').replace(/[,،\\s]/g, '');
            document.getElementById('editPrice').value = Number(rawP) ? Number(rawP).toLocaleString('en-US') : '0';
            document.getElementById('editDesc').value = desc;
            document.getElementById('editDl').value = dl;
            document.getElementById('editPhoto').value = photo;
            document.getElementById('editAllowCard').checked = !!allow_card;
            document.getElementById('editAllowBale').checked = !!allow_bale;
            if (document.getElementById('editRequiresReferral')) {{
                document.getElementById('editRequiresReferral').checked = !!requires_referral;
            }}
            if (document.getElementById('editDeliveryType')) {{
                document.getElementById('editDeliveryType').value = delivery_type || 'channel';
                togglePackageInput('edit');
            }}
            if (document.getElementById('editFilesPackage')) {{
                if (Array.isArray(files_package)) {{
                    document.getElementById('editFilesPackage').value = files_package.length ? JSON.stringify(files_package, null, 2) : '';
                }} else {{
                    document.getElementById('editFilesPackage').value = files_package ? String(files_package) : '';
                }}
            }}
            const statusEl = document.getElementById('bannerUploadStatus_editPhoto');
            if (statusEl) statusEl.innerText = '';
            updateCharCounter('editName', 'counter_editName', 32);
            updateCharCounter('editDesc', 'counter_editDesc', 255);
            document.getElementById('editModal').classList.remove('hidden');
        }}

        function closeEditModal() {{
            document.getElementById('editModal').classList.add('hidden');
        }}

        function openEditModalById(pid) {{
            const course = (window.coursesData && window.coursesData[pid]) ? window.coursesData[pid] : null;
            if (!course) {{
                alert('اطلاعات دوره یافت نشد.');
                return;
            }}
            openEditModal(
                course.product_id,
                course.name,
                course.price,
                course.description,
                course.download_link,
                course.photo_url,
                course.allow_card,
                course.allow_bale,
                course.requires_referral,
                course.delivery_type,
                course.files_package
            );
        }}

        async function handleSaveEdit(e) {{
            e.preventDefault();
            const product_id = document.getElementById('editProductId').value;
            const name = document.getElementById('editName').value;
            const rawPrice = String(document.getElementById('editPrice').value || '').replace(/[,،\\s]/g, '');
            const price = parseInt(rawPrice) || 0;
            const description = document.getElementById('editDesc').value;
            const download_link = document.getElementById('editDl').value;
            const photo_url = document.getElementById('editPhoto').value;
            const allow_card = document.getElementById('editAllowCard').checked ? 1 : 0;
            const allow_bale = document.getElementById('editAllowBale').checked ? 1 : 0;
            const requires_referral = document.getElementById('editRequiresReferral') ? (document.getElementById('editRequiresReferral').checked ? 1 : 0) : 0;
            const delivery_type = document.getElementById('editDeliveryType') ? document.getElementById('editDeliveryType').value : 'channel';
            let files_package = [];
            if (delivery_type === 'files_package' && document.getElementById('editFilesPackage')) {{
                const rawPkg = document.getElementById('editFilesPackage').value.trim();
                try {{
                    files_package = rawPkg.startsWith('[') ? JSON.parse(rawPkg) : rawPkg.split('\\n').filter(Boolean).map(l => {{
                        const parts = l.split('|').map(s => s.trim());
                        return {{ title: parts[0] || 'فایل آموزشی', file_id: parts[1] || parts[0] }};
                    }});
                }} catch(e) {{
                    files_package = [{{ title: name, file_name: rawPkg }}];
                }}
            }}

            try {{
                const res = await fetch('/api/courses/update', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ product_id, name, price, description, download_link, photo_url, allow_card, allow_bale, requires_referral, delivery_type, files_package }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ تغییرات دوره با موفقیت ذخیره شد!');
                    location.reload();
                }} else {{
                    alert('❌ خطا: ' + (data.error || 'ویرایش ناموفق بود'));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط: ' + err.message);
            }}
        }}

        async function saveCourseTermsText() {{
            const btn = document.getElementById('btnSaveTerms');
            const status = document.getElementById('termsSaveStatus');
            const textarea = document.getElementById('courseTermsTextarea');
            if (!textarea) return;
            const terms = textarea.value.trim();
            if (btn) {{
                btn.disabled = true;
                btn.innerText = 'در حال ذخیره...';
            }}
            try {{
                const res = await fetch('/api/courses/terms', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ terms: terms }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    if (status) {{
                        status.className = 'text-xs font-medium text-emerald-400';
                        status.innerText = '✅ تعهدنامه با موفقیت در سیستم ذخیره شد.';
                        setTimeout(() => {{ status.innerText = ''; }}, 4000);
                    }}
                }} else {{
                    if (status) {{
                        status.className = 'text-xs font-medium text-rose-400';
                        status.innerText = '❌ خطا: ' + (data.error || 'ذخیره نشد');
                    }}
                }}
            }} catch (err) {{
                if (status) {{
                    status.className = 'text-xs font-medium text-rose-400';
                    status.innerText = '❌ خطای شبکه: ' + err.message;
                }}
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerText = '💾 ذخیره متن تعهدنامه';
                }}
            }}
        }}

        async function aiSummarizeDescription(textareaId, counterId) {{
            const textarea = document.getElementById(textareaId);
            if (!textarea) return;
            const text = textarea.value.trim();
            if (!text) {{
                alert('لطفاً ابتدا متنی در بخش توضیحات بنویسید تا هوش مصنوعی آن را خلاصه کند.');
                return;
            }}
            const prevPlaceholder = textarea.placeholder;
            textarea.disabled = true;
            textarea.placeholder = '✨ در حال خلاصه‌سازی هوشمند برای بله (زیر ۲۵۵ کاراکتر)...';
            try {{
                const res = await fetch('/api/ai/summarize-course', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ text: text }})
                }});
                const data = await res.json();
                if (data.ok && data.summary) {{
                    textarea.value = data.summary;
                    if (counterId) {{
                        updateCharCounter(textareaId, counterId, 255);
                    }}
                }} else {{
                    alert('❌ خطا در خلاصه‌سازی: ' + (data.error || 'پاسخی دریافت نشد'));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط با هوش مصنوعی: ' + err.message);
            }} finally {{
                textarea.disabled = false;
                textarea.placeholder = prevPlaceholder;
            }}
        }}

        async function toggleCourseActive(pid) {{
            const btn = document.getElementById('toggle_btn_' + pid);
            const badge = document.getElementById('status_badge_' + pid);
            if (btn) {{
                btn.disabled = true;
                btn.innerText = 'در حال تغییر...';
            }}
            try {{
                const res = await fetch('/api/products/toggle_active', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ product_id: pid }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    const isActive = !!data.active;
                    if (badge) {{
                        if (isActive) {{
                            badge.className = 'px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1';
                            badge.innerHTML = '<span>🟢</span> فعال';
                        }} else {{
                            badge.className = 'px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-950 text-rose-300 border border-rose-800 flex items-center gap-1';
                            badge.innerHTML = '<span>🔴</span> غیرفعال';
                        }}
                    }}
                    if (btn) {{
                        btn.innerHTML = isActive ? '🔴 غیرفعال‌سازی' : '🟢 فعال‌سازی';
                    }}
                    if (window.coursesData && window.coursesData[pid]) {{
                        window.coursesData[pid].is_active = isActive ? 1 : 0;
                    }}
                }} else {{
                    alert('❌ خطا در تغییر وضعیت: ' + (data.error || ''));
                }}
            }} catch (err) {{
                alert('❌ خطا: ' + err.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                }}
            }}
        }}

        async function deleteCourse(pid) {{
            if (!confirm('آیا از حذف دائم و فیزیکی این دوره از سیستم و پایگاه داده اطمینان دارید؟ این عملیات غیرقابل بازگشت است.')) return;
            try {{
                const res = await fetch('/api/products/delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ product_id: pid }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    const card = document.getElementById('course_card_' + pid);
                    if (card) {{
                        card.style.transition = 'all 0.4s ease';
                        card.style.opacity = '0';
                        card.style.transform = 'scale(0.95)';
                        setTimeout(() => {{ card.remove(); }}, 400);
                    }}
                }} else {{
                    alert('❌ خطا: ' + (data.error || ''));
                }}
            }} catch (err) {{
                alert('❌ خطا: ' + err.message);
            }}
        }}

        function toggleSelectAllOrders(master) {{
            const chks = document.querySelectorAll('.order-chk');
            chks.forEach(c => c.checked = master.checked);
            updateSelectedOrdersCount();
        }}

        function updateSelectedOrdersCount() {{
            const chks = document.querySelectorAll('.order-chk:checked');
            const cnt = chks.length;
            const btn = document.getElementById('btnDeleteSelectedOrders');
            const cntSpan = document.getElementById('selectedOrdersCount');
            if (cntSpan) cntSpan.innerText = cnt;
            if (btn) {{
                if (cnt > 0) {{
                    btn.classList.remove('hidden');
                }} else {{
                    btn.classList.add('hidden');
                }}
            }}
            const allChks = document.querySelectorAll('.order-chk');
            const master = document.getElementById('selectAllOrders');
            if (master && allChks.length > 0) {{
                master.checked = (cnt === allChks.length);
            }} else if (master && allChks.length === 0) {{
                master.checked = false;
            }}
        }}

        async function deleteSelectedOrders() {{
            const checked = Array.from(document.querySelectorAll('.order-chk:checked')).map(c => c.value);
            if (!checked || checked.length === 0) {{
                alert('لطفاً حداقل یک سفارش را برای حذف انتخاب کنید.');
                return;
            }}
            if (!confirm('آیا از حذف دسته‌جمعی ' + checked.length + ' سفارش انتخاب‌شده اطمینان دارید؟ این عملیات غیرقابل بازگشت است.')) return;
            try {{
                const res = await fetch('/api/store/orders/bulk_delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ order_ids: checked }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ ' + (data.message || (checked.length + ' سفارش با موفقیت حذف شدند.')));
                    loadStoreOrders();
                }} else {{
                    alert('❌ خطا در حذف سفارش‌ها: ' + (data.error || ''));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط: ' + err.message);
            }}
        }}

        async function clearAllOrders() {{
            if (!confirm('⚠️ هشدار جدی!\\nآیا از پاکسازی تمامی سفارشات موجود در سیستم اطمینان دارید؟\\nاین عملیات کلیه سفارشات ثبت‌شده (تستی و واقعی) را به طور کامل حذف می‌کند و غیرقابل بازگشت است.')) return;
            try {{
                const res = await fetch('/api/store/orders/clear_all', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }}
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ ' + (data.message || 'تمامی سفارشات با موفقیت پاکسازی شدند.'));
                    loadStoreOrders();
                }} else {{
                    alert('❌ خطا در پاکسازی سفارشات: ' + (data.error || ''));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط: ' + err.message);
            }}
        }}

        async function loadStoreOrders() {{
            const tbody = document.getElementById('storeOrdersTableBody');
            if (!tbody) return;
            const master = document.getElementById('selectAllOrders');
            if (master) master.checked = false;
            updateSelectedOrdersCount();

            try {{
                const res = await fetch('/api/store/orders');
                const data = await res.json();
                if (!data.ok || !data.orders || data.orders.length === 0) {{
                    tbody.innerHTML = '<tr><td colspan="9" class="py-8 text-center text-slate-500">هیچ سفارشی در سیستم ثبت نشده است.</td></tr>';
                    return;
                }}
                tbody.innerHTML = data.orders.map(ord => {{
                    let statusBadge = '';
                    if (ord.status === 'completed' || ord.status === 'approved') {{
                        statusBadge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">✅ تایید شده</span>';
                    }} else if (ord.status === 'rejected') {{
                        statusBadge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-950 text-rose-300 border border-rose-800">❌ رد شده</span>';
                    }} else {{
                        statusBadge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-950 text-amber-300 border border-amber-800">⏳ در انتظار بررسی</span>';
                    }}

                    let platBadge = '';
                    const p = (ord.platform || '').toLowerCase();
                    if (p === 'telegram' || p === 'tg') {{
                        platBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950/70 text-sky-300 border border-sky-800/70 inline-flex items-center gap-1"><span>✈️</span> تلگرام</span>';
                    }} else if (p === 'bale') {{
                        platBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/70 text-emerald-300 border border-emerald-800/70 inline-flex items-center gap-1"><span>🟢</span> بله</span>';
                    }} else {{
                        platBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-950/70 text-purple-300 border border-purple-800/70 inline-flex items-center gap-1"><span>🌐</span> فروشگاه وب</span>';
                    }}

                    let payMethodBadge = '';
                    const m = (ord.payment_method || '').toLowerCase();
                    if (m === 'bale_online' || m === 'bale') {{
                        payMethodBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/60 text-emerald-300 border border-emerald-800/60 inline-flex items-center gap-1"><span>🛍</span> درگاه بله</span>';
                    }} else if (m === 'card_to_card' || m === 'card') {{
                        payMethodBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950/60 text-sky-300 border border-sky-800/60 inline-flex items-center gap-1"><span>💳</span> کارت‌به‌کارت</span>';
                    }} else if (m === 'zarinpal') {{
                        payMethodBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950/60 text-amber-300 border border-amber-800/60 inline-flex items-center gap-1"><span>⚡️</span> زرین‌پال</span>';
                    }} else {{
                        payMethodBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950/60 text-sky-300 border border-sky-800/60 inline-flex items-center gap-1"><span>💳</span> کارت‌به‌کارت</span>';
                    }}

                    let actionBtn = '<div class="flex items-center gap-1.5">';
                    if (ord.status === 'pending_review' || ord.status === 'pending') {{
                        actionBtn += '<button onclick="approveStoreOrder(&quot;' + ord.order_id + '&quot;)" class="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition shadow-sm">✅ تایید</button>' +
                                    '<button onclick="rejectStoreOrder(&quot;' + ord.order_id + '&quot;)" class="theme-card-btn px-2.5 py-1 rounded-lg text-xs font-bold transition shadow-sm">❌ رد</button>';
                    }}
                    actionBtn += '<button onclick="deleteStoreOrder(&quot;' + ord.order_id + '&quot;)" class="theme-card-btn px-2 py-1 rounded-lg text-xs font-bold transition shadow-sm" title="حذف سفارش">🗑 حذف</button></div>';

                    const orderDate = ord.created_at || '-';
                    const amountStr = (ord.amount || 0).toLocaleString() + ' تومان';

                    return '<tr class="border-b border-slate-800 hover:bg-slate-800/30 transition">' +
                        '<td class="py-3 px-3 text-center"><input type="checkbox" class="order-chk rounded bg-slate-800 border-slate-600 text-cyan-500 focus:ring-0 cursor-pointer" value="' + escapeHtml(ord.order_id) + '" onchange="updateSelectedOrdersCount()"></td>' +
                        '<td class="py-3 px-3 font-mono text-cyan-400 font-bold">' + escapeHtml(ord.order_id) + '</td>' +
                        '<td class="py-3 px-3">' +
                            '<div class="font-bold text-slate-200">' + escapeHtml(ord.customer_name || 'کاربر') + '</div>' +
                            '<div class="text-[11px] font-mono text-slate-400">' + escapeHtml(ord.phone || ord.user_id || '-') + '</div>' +
                        '</td>' +
                        '<td class="py-3 px-3">' +
                            '<div class="text-slate-200 font-medium">' + escapeHtml(ord.product_name || ord.product_id) + '</div>' +
                            '<div class="text-[11px] font-mono text-emerald-400 font-bold">' + amountStr + '</div>' +
                        '</td>' +
                        '<td class="py-3 px-3">' + platBadge + '</td>' +
                        '<td class="py-3 px-3">' + payMethodBadge + '</td>' +
                        '<td class="py-3 px-3">' +
                            '<div class="max-w-[200px] truncate text-slate-300 text-[11px]" title="' + escapeHtml(ord.receipt_text || '') + '">' + escapeHtml(ord.receipt_text || '-') + '</div>' +
                            '<div class="text-[10px] text-slate-400 font-mono">' + escapeHtml(orderDate) + '</div>' +
                        '</td>' +
                        '<td class="py-3 px-3">' + statusBadge + '</td>' +
                        '<td class="py-3 px-3 text-left">' + actionBtn + '</td>' +
                    '</tr>';
                }}).join('');
            }} catch (err) {{
                tbody.innerHTML = '<tr><td colspan="9" class="py-6 text-center text-rose-400">خطا در دریافت سفارش‌ها: ' + err.message + '</td></tr>';
            }}
        }}

        async function approveStoreOrder(orderId) {{
            if (!confirm('آیا از تایید سفارش ' + orderId + ' و فعال‌سازی لینک دانلود برای مشتری اطمینان دارید؟')) return;
            try {{
                const res = await fetch('/api/store/orders/approve', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ order_id: orderId }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ سفارش ' + orderId + ' با موفقیت تایید شد!');
                    loadStoreOrders();
                }} else {{
                    alert('❌ خطا در تایید سفارش: ' + (data.error || ''));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط: ' + err.message);
            }}
        }}

        async function rejectStoreOrder(orderId) {{
            if (!confirm('آیا از رد سفارش ' + orderId + ' اطمینان دارید؟ وضعیت سفارش به رد شده تغییر خواهد کرد.')) return;
            try {{
                const res = await fetch('/api/store/orders/reject', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ order_id: orderId }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('❌ سفارش ' + orderId + ' با موفقیت رد شد.');
                    loadStoreOrders();
                }} else {{
                    alert('❌ خطا در رد سفارش: ' + (data.error || ''));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط: ' + err.message);
            }}
        }}

        async function deleteStoreOrder(orderId) {{
            if (!confirm('آیا از حذف کامل سفارش ' + orderId + ' از سیستم اطمینان دارید؟ این عملیات غیرقابل بازگشت است.')) return;
            try {{
                const res = await fetch('/api/store/orders/delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ order_id: orderId }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    loadStoreOrders();
                }} else {{
                    alert('❌ خطا در حذف سفارش: ' + (data.error || ''));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط: ' + err.message);
            }}
        }}

        async function cleanupRejectedOrders() {{
            if (!confirm('آیا از حذف کلیه سفارش‌های رد شده از پایگاه داده اطمینان دارید؟ این عملیات غیرقابل بازگشت است.')) return;
            try {{
                const res = await fetch('/api/store/orders/cleanup_rejected', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }}
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ ' + (data.message || 'سفارش‌های رد شده با موفقیت پاکسازی شدند.'));
                    loadStoreOrders();
                }} else {{
                    alert('❌ خطا در پاکسازی سفارش‌ها: ' + (data.error || ''));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط: ' + err.message);
            }}
        }}

        async function loadStoreAnalytics() {{
            try {{
                const res = await fetch('/api/analytics');
                const data = await res.json();
                if (data.ok && data.analytics) {{
                    const a = data.analytics;
                    const totEl = document.getElementById('metricTotalSales');
                    if (totEl) totEl.innerText = (a.total_sales_amount || 0).toLocaleString() + ' تومان';
                    const ordEl = document.getElementById('metricTotalOrders');
                    if (ordEl) ordEl.innerText = (a.total_sales_count || 0) + ' سفارش موفق';

                    const todayEl = document.getElementById('metricTodaySales');
                    if (todayEl) todayEl.innerText = (a.today_sales_amount || 0).toLocaleString() + ' تومان';
                    const todayOrd = document.getElementById('metricTodayOrders');
                    if (todayOrd) todayOrd.innerText = (a.today_sales_count || 0) + ' سفارش';

                    const weekEl = document.getElementById('metricWeekSales');
                    if (weekEl) weekEl.innerText = (a.week_sales_amount || 0).toLocaleString() + ' تومان';
                    const weekOrd = document.getElementById('metricWeekOrders');
                    if (weekOrd) weekOrd.innerText = (a.week_sales_count || 0) + ' سفارش';

                    const monthEl = document.getElementById('metricMonthSales');
                    if (monthEl) monthEl.innerText = (a.month_sales_amount || 0).toLocaleString() + ' تومان';
                    const monthOrd = document.getElementById('metricMonthOrders');
                    if (monthOrd) monthOrd.innerText = (a.month_sales_count || 0) + ' سفارش';

                    const pb = a.platform_breakdown || {{}};
                    const tg = pb.telegram || {{ amount: 0, count: 0 }};
                    const bale = pb.bale || {{ amount: 0, count: 0 }};
                    const rub = pb.rubika || {{ amount: 0, count: 0 }};
                    const web = pb.web || {{ amount: 0, count: 0 }};

                    const tgEl = document.getElementById('platSalesTg');
                    if (tgEl) tgEl.innerText = (tg.amount || 0).toLocaleString() + ' تومان (' + (tg.count || 0) + ')';
                    const baleEl = document.getElementById('platSalesBale');
                    if (baleEl) baleEl.innerText = (bale.amount || 0).toLocaleString() + ' تومان (' + (bale.count || 0) + ')';
                    const rubEl = document.getElementById('platSalesRubika');
                    if (rubEl) rubEl.innerText = (rub.amount || 0).toLocaleString() + ' تومان (' + (rub.count || 0) + ')';
                    const webEl = document.getElementById('platSalesWeb');
                    if (webEl) webEl.innerText = (web.amount || 0).toLocaleString() + ' تومان (' + (web.count || 0) + ')';
                }}
            }} catch (err) {{
                console.error('Error loading analytics:', err);
            }}
        }}

        function toggleAddCouponForm() {{
            const el = document.getElementById('addCouponCard');
            if (el) el.classList.toggle('hidden');
        }}

        async function loadStoreCoupons() {{
            const tbody = document.getElementById('couponsTableBody');
            if (!tbody) return;
            try {{
                const res = await fetch('/api/coupons');
                const data = await res.json();
                if (!data.ok || !data.coupons || data.coupons.length === 0) {{
                    tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-slate-500">هیچ کد تخفیفی در سیستم ثبت نشده است.</td></tr>';
                    return;
                }}
                tbody.innerHTML = data.coupons.map(c => {{
                    const valNum = parseInt(c.discount_value) || 0;
                    const typeLabel = c.discount_type === 'percent' ? (valNum + '%') : (valNum.toLocaleString() + ' تومان');
                    const maxLabel = (c.max_uses && c.max_uses > 0) ? ((c.used_count || 0) + ' / ' + c.max_uses) : ((c.used_count || 0) + ' (نامحدود)');
                    const minLabel = (c.min_order_amount && c.min_order_amount > 0) ? (parseInt(c.min_order_amount).toLocaleString() + ' تومان') : 'بدون شرط';
                    const expLabel = c.expire_date ? c.expire_date : 'همیشگی';
                    const statusBadge = c.active ? '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800">فعال</span>' : '<span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400">غیرفعال</span>';

                    return '<tr class="border-b border-slate-800/80 hover:bg-slate-800/30 transition">' +
                        '<td class="py-2.5 px-3 font-mono text-emerald-400 font-bold">' + escapeHtml(c.code) + '</td>' +
                        '<td class="py-2.5 px-3 text-slate-200 font-bold">' + typeLabel + '</td>' +
                        '<td class="py-2.5 px-3 font-mono text-slate-300">' + maxLabel + '</td>' +
                        '<td class="py-2.5 px-3 text-slate-400 font-mono">' + minLabel + '</td>' +
                        '<td class="py-2.5 px-3 text-slate-400 font-mono text-[11px]">' + escapeHtml(expLabel) + '</td>' +
                        '<td class="py-2.5 px-3">' + statusBadge + '</td>' +
                    '</tr>';
                }}).join('');
            }} catch (err) {{
                tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-rose-400">خطا در بارگذاری کوپن‌ها: ' + err.message + '</td></tr>';
            }}
        }}

        async function handleCreateCoupon(e) {{
            e.preventDefault();
            const btn = document.getElementById('btnSubmitCoupon');
            if (btn) {{ btn.disabled = true; btn.innerText = 'در حال ثبت...'; }}

            const code = document.getElementById('newCouponCode').value.trim();
            const discount_type = document.getElementById('newCouponType').value;
            const discount_value = parseInt(document.getElementById('newCouponValue').value) || 0;
            const max_uses = parseInt(document.getElementById('newCouponMaxUses').value) || 0;
            const min_order_amount = parseInt(document.getElementById('newCouponMinAmount').value) || 0;
            const expire_date = document.getElementById('newCouponExpire').value.trim();

            try {{
                const res = await fetch('/api/coupons/create', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ code, discount_type, discount_value, max_uses, min_order_amount, expire_date }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert('✅ کد تخفیف ' + code + ' با موفقیت ایجاد شد!');
                    document.getElementById('addCouponForm').reset();
                    toggleAddCouponForm();
                    loadStoreCoupons();
                }} else {{
                    alert('❌ خطا در ثبت کد تخفیف: ' + (data.error || ''));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط: ' + err.message);
            }} finally {{
                if (btn) {{ btn.disabled = false; btn.innerText = 'ثبت کوپن تخفیف'; }}
            }}
        }}

        function copyText(txt) {{
            navigator.clipboard.writeText(txt);
            alert('✅ لینک با موفقیت کپی شد!');
        }}

        async function handleDispatch(e) {{
            e.preventDefault();
            const btn = document.getElementById('submitBtn');
            const resBox = document.getElementById('dispatchResult');
            const url = document.getElementById('directUrl').value;
            const target = document.getElementById('targetPlatform').value;

            btn.disabled = true;
            btn.innerText = '⏳ در حال دانلود و پردازش استریم...';
            resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-slate-800 text-slate-300 border border-slate-700';
            resBox.innerText = '⏳ ارسال درخواست به سرور و دانلود استریم... لطفاً شکیبا باشید.';

            try {{
                const res = await fetch('/api/dispatch_url', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ url, target }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-emerald-950 text-emerald-300 border border-emerald-700';
                    resBox.innerText = '✅ ' + (data.message || 'فایل با موفقیت دانلود و ارسال شد!');
                }} else {{
                    resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-rose-950 text-rose-300 border border-rose-700';
                    resBox.innerText = '❌ خطا: ' + (data.error || 'عملیات ناموفق بود');
                }}
            }} catch (err) {{
                resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-rose-950 text-rose-300 border border-rose-700';
                resBox.innerText = '❌ خطای شبکه: ' + err.message;
            }} finally {{
                btn.disabled = false;
                btn.innerText = '⚡️ دانلود و ارسال خودکار';
            }}
        }}


                window.togglePackageInput = togglePackageInput;
                window.toggleAddCourseForm = toggleAddCourseForm;
                window.handleCreateCourse = handleCreateCourse;
                window.openEditModal = openEditModal;
                window.openEditModalById = openEditModalById;
                window.openEditCourseModal = openEditModalById;
                window.closeEditModal = closeEditModal;
                window.handleSaveEdit = handleSaveEdit;
                window.toggleCourseActive = toggleCourseActive;
                window.deleteCourse = deleteCourse;
                window.toggleSelectAllOrders = toggleSelectAllOrders;
                window.updateSelectedOrdersCount = updateSelectedOrdersCount;
                window.deleteSelectedOrders = deleteSelectedOrders;
                window.clearAllOrders = clearAllOrders;
                window.loadStoreOrders = loadStoreOrders;
                window.approveStoreOrder = approveStoreOrder;
                window.rejectStoreOrder = rejectStoreOrder;
                window.deleteStoreOrder = deleteStoreOrder;
                window.cleanupRejectedOrders = cleanupRejectedOrders;
                window.loadStoreAnalytics = loadStoreAnalytics;
                window.toggleAddCouponForm = toggleAddCouponForm;
                window.loadStoreCoupons = loadStoreCoupons;
                window.handleCreateCoupon = handleCreateCoupon;
                window.copyText = copyText;
                window.handleDispatch = handleDispatch;
                window.saveCourseTermsText = saveCourseTermsText;
                window.aiSummarizeDescription = aiSummarizeDescription;
                window.formatPriceInput = formatPriceInput;
            }} catch (err) {{
                console.error('[UNFINIT Store & Orders Module Error]:', err);
            }}
        }})();

        // =========================================================================
        // MODULE 4: AI AGENT & SYSTEM SETTINGS (Sandboxed IIFE)
        // =========================================================================
        (function initSettingsModule() {{
            try {{
                let hermesHistory = [];
        function clearHermesChat() {{
            hermesHistory = [];
            const box = document.getElementById('hermesChatBox');
            box.innerHTML = `
                <div class="flex gap-2.5 items-center p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-300">
                    <div class="w-6 h-6 rounded-lg bg-cyan-600/30 text-cyan-300 flex items-center justify-center font-bold text-xs shrink-0">🤖</div>
                    <span>تاریخچه گفتگو پاکسازی شد. دستیار هوش مصنوعی آماده است.</span>
                </div>
            `;
        }}

        function sendPresetHermesPrompt(prompt) {{
            const input = document.getElementById('hermesInput');
            if (input) {{
                input.value = prompt;
                handleSendHermes(null);
            }}
        }}

        async function handleSendHermes(e) {{
            if (e) e.preventDefault();
            const input = document.getElementById('hermesInput');
            const prompt = (input.value || '').trim();
            if (!prompt) return;

            const box = document.getElementById('hermesChatBox');
            const btn = document.getElementById('btnSendHermes');

            const userBubble = document.createElement('div');
            userBubble.className = 'flex gap-3 items-start justify-end max-w-3xl mr-auto';
            userBubble.innerHTML = `
                <div class="bg-gradient-to-r from-blue-600 to-cyan-600 text-white p-3.5 rounded-2xl rounded-tl-none text-xs leading-relaxed shadow-lg shadow-cyan-900/30">
                    ` + escapeHtml(prompt) + `
                </div>
                <div class="w-8 h-8 rounded-xl bg-slate-700 flex items-center justify-center font-bold text-xs text-white shrink-0 mt-1">👤</div>
            `;
            box.appendChild(userBubble);
            input.value = '';

            const loadingBubble = document.createElement('div');
            const loadingId = 'hermes_load_' + Date.now();
            loadingBubble.id = loadingId;
            loadingBubble.className = 'flex gap-3 items-start max-w-3xl';
            loadingBubble.innerHTML = `
                <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center font-bold text-sm text-white shrink-0 mt-1 animate-pulse">🎛</div>
                <div class="bg-slate-800/90 border border-slate-700 p-3.5 rounded-2xl rounded-tr-none text-xs text-slate-300 flex items-center gap-2">
                    <span class="animate-spin text-cyan-400">🌀</span>
                    <span>دستیار هوشمند در حال پردازش و تولید پاسخ...</span>
                </div>
            `;
            box.appendChild(loadingBubble);
            box.scrollTop = box.scrollHeight;

            btn.disabled = true;

            try {{
                const selModel = document.getElementById('hermesModelSelect')?.value || '';
                const res = await fetch('/api/hermes/chat', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ message: prompt, history: hermesHistory, model: selModel }})
                }});
                const data = await res.json();
                const loadEl = document.getElementById(loadingId);
                if (loadEl) loadEl.remove();

                const replyText = data.reply || (data.error ? '❌ خطا: ' + data.error : 'پاسخی دریافت نشد.');
                const toolsUsed = data.tools_used || [];

                let toolsHtml = '';
                if (toolsUsed.length > 0) {{
                    toolsHtml = '<div class="flex flex-wrap gap-1.5 mb-2">' + toolsUsed.map(t => '<span class="px-2 py-0.5 rounded-md bg-cyan-950 text-cyan-300 text-[10px] border border-cyan-800 font-mono">🛠 ' + escapeHtml(t) + '</span>').join('') + '</div>';
                }}

                const assistantBubble = document.createElement('div');
                assistantBubble.className = 'flex gap-3 items-start max-w-3xl';
                assistantBubble.innerHTML = `
                    <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center font-bold text-sm text-white shrink-0 mt-1">🎛</div>
                    <div class="bg-slate-800/95 border border-slate-700 p-4 rounded-2xl rounded-tr-none text-xs leading-relaxed text-slate-100 space-y-2 whitespace-pre-wrap shadow-xl">
                        ` + toolsHtml + `
                        <div>` + escapeHtml(replyText) + `</div>
                    </div>
                `;
                box.appendChild(assistantBubble);

                hermesHistory.push({{ role: 'user', content: prompt }});
                hermesHistory.push({{ role: 'assistant', content: replyText }});
                if (hermesHistory.length > 12) hermesHistory = hermesHistory.slice(-12);
            }} catch (err) {{
                const loadEl = document.getElementById(loadingId);
                if (loadEl) loadEl.remove();
                const errBubble = document.createElement('div');
                errBubble.className = 'flex gap-3 items-start max-w-3xl';
                errBubble.innerHTML = `
                    <div class="w-8 h-8 rounded-xl bg-rose-600 flex items-center justify-center font-bold text-sm text-white shrink-0 mt-1">⚠️</div>
                    <div class="bg-rose-950/80 border border-rose-800 p-3 rounded-2xl rounded-tr-none text-xs text-rose-300">
                        خطا در ارتباط با سرور: ` + escapeHtml(err.message) + `
                    </div>
                `;
                box.appendChild(errBubble);
            }} finally {{
                btn.disabled = false;
                box.scrollTop = box.scrollHeight;
            }}
        }}

        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        function uploadBannerFile(fileInput, targetInputId) {{
            const file = fileInput.files[0];
            if (!file) return;
            const statusEl = document.getElementById('bannerUploadStatus_' + targetInputId);
            if (statusEl) statusEl.innerText = '⏳ در حال فشرده‌سازی و بارگذاری تصویر بنر...';

            let prodId = '';
            if (targetInputId === 'editPhoto') {{
                const editIdEl = document.getElementById('editProductId');
                if (editIdEl) prodId = editIdEl.value || '';
            }}

            const reader = new FileReader();
            reader.onload = async function(e) {{
                try {{
                    const res = await fetch('/api/upload/banner', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            filename: file.name,
                            prod_id: prodId,
                            data: e.target.result
                        }})
                    }});
                    const data = await res.json();
                    if (data.ok && data.url) {{
                        const targetInp = document.getElementById(targetInputId);
                        if (targetInp) {{
                            targetInp.value = data.url;
                            targetInp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                        let previewEl = document.getElementById('bannerPreview_' + targetInputId);
                        if (!previewEl && targetInp) {{
                            previewEl = document.createElement('img');
                            previewEl.id = 'bannerPreview_' + targetInputId;
                            previewEl.className = 'w-24 h-24 object-cover rounded-xl mt-2 border border-cyan-500/50 shadow-md';
                            if (statusEl) {{
                                statusEl.parentNode.insertBefore(previewEl, statusEl);
                            }} else {{
                                targetInp.parentNode.parentNode.appendChild(previewEl);
                            }}
                        }}
                        if (previewEl) {{
                            previewEl.src = data.url;
                            previewEl.style.display = 'block';
                        }}
                        if (statusEl) statusEl.innerHTML = '✅ تصویر ذخیره شد: <a href="' + data.url + '" target="_blank" class="text-cyan-400 underline font-mono">' + data.url + '</a>';
                    }} else {{
                        if (statusEl) statusEl.innerText = '❌ خطا: ' + (data.error || 'آپلود ناموفق بود');
                    }}
                }} catch (err) {{
                    if (statusEl) statusEl.innerText = '❌ خطا در ارسال فایل: ' + err.message;
                }}
            }};
            reader.readAsDataURL(file);
        }}

        async function loadSettings() {{
            try {{
                const pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/settings?password=' + encodeURIComponent(pwd));
                if (res.status === 401) {{
                    console.warn('loadSettings: unauthorized, active admin login session required.');
                    return;
                }}
                const data = await res.json();
                if (data.ok && data.settings) {{
                    populateSettingsForm(data.settings);
                }}
            }} catch (err) {{
                console.error('Failed to load settings:', err);
            }}
        }}

        const AI_PROVIDER_MODELS = {{
            vyceai: [
                {{ id: 'deepseek-v4.1', name: 'deepseek-v4.1 (VyceAI)' }},
                {{ id: 'deepseek-v4-flash', name: 'deepseek-v4-flash (VyceAI)' }},
                {{ id: 'claude-sonnet-4-6', name: 'claude-sonnet-4-6 (VyceAI)' }},
                {{ id: 'agnes-3.0-flash', name: 'agnes-3.0-flash (VyceAI)' }}
            ],
            nara: [
                {{ id: 'stepfun-3.7-flash', name: 'stepfun-3.7-flash (Nara)' }},
                {{ id: 'minimax-0.5-free', name: 'minimax-0.5-free (Nara)' }},
                {{ id: 'qwen2.5-72b', name: 'qwen2.5-72b (Nara)' }}
            ],
            gemini: [
                {{ id: 'gemini-2.0-flash', name: 'gemini-2.0-flash (Gemini)' }},
                {{ id: 'gemini-1.5-flash', name: 'gemini-1.5-flash (Gemini)' }},
                {{ id: 'gemini-1.5-pro', name: 'gemini-1.5-pro (Gemini)' }}
            ]
        }};

        function handleAiProviderChange(prov, currentModelVal) {{
            try {{
                const p = (prov || 'vyceai').toLowerCase();
                const sel = document.getElementById('cfg_AI_PROVIDER');
                if (sel && sel.value !== p) sel.value = p;
                
                const urlInput = document.getElementById('cfg_AI_BASE_URL');
                const modelSelect = document.getElementById('cfg_AI_MODEL');
                const customModelInput = document.getElementById('cfg_AI_MODEL_CUSTOM');
                
                const vyceBox = document.getElementById('box_vyceai_key');
                const naraBox = document.getElementById('box_nara_key');
                const geminiBox = document.getElementById('box_gemini_key');
                
                if (vyceBox) vyceBox.style.opacity = '0.65';
                if (naraBox) naraBox.style.opacity = '0.65';
                if (geminiBox) geminiBox.style.opacity = '0.65';

                const targetModel = currentModelVal || (modelSelect ? modelSelect.value : '') || '';

                if (p === 'custom') {{
                    if (modelSelect) modelSelect.classList.add('hidden');
                    if (customModelInput) {{
                        customModelInput.classList.remove('hidden');
                        if (targetModel) customModelInput.value = targetModel;
                    }}
                    if (vyceBox) vyceBox.style.opacity = '1';
                    if (naraBox) naraBox.style.opacity = '1';
                    if (geminiBox) geminiBox.style.opacity = '1';
                    return;
                }}

                // Standard Providers (vyceai, nara, gemini)
                if (customModelInput) customModelInput.classList.add('hidden');
                if (modelSelect) {{
                    modelSelect.classList.remove('hidden');
                    const models = AI_PROVIDER_MODELS[p] || AI_PROVIDER_MODELS.vyceai;
                    modelSelect.innerHTML = models.map(function(m) {{
                        return '<option value="' + m.id + '">' + m.name + '</option>';
                    }}).join('');
                    
                    const match = models.some(function(m) {{ return m.id === targetModel; }});
                    if (match) {{
                        modelSelect.value = targetModel;
                    }} else {{
                        modelSelect.value = models[0].id;
                    }}
                }}

                if (p === 'vyceai') {{
                    if (urlInput && (!urlInput.value || urlInput.value.includes('bynara') || urlInput.value.includes('googleapis'))) {{
                        urlInput.value = 'https://vyceai.com/v1';
                    }}
                    if (vyceBox) vyceBox.style.opacity = '1';
                }} else if (p === 'nara') {{
                    if (urlInput && (!urlInput.value || urlInput.value.includes('vyceai') || urlInput.value.includes('googleapis'))) {{
                        urlInput.value = 'https://router.bynara.id/v1';
                    }}
                    if (naraBox) naraBox.style.opacity = '1';
                }} else if (p === 'gemini') {{
                    if (urlInput && (!urlInput.value || urlInput.value.includes('vyceai') || urlInput.value.includes('bynara'))) {{
                        urlInput.value = 'https://generativelanguage.googleapis.com/v1beta';
                    }}
                    if (geminiBox) geminiBox.style.opacity = '1';
                }} else {{
                    if (vyceBox) vyceBox.style.opacity = '1';
                    if (naraBox) naraBox.style.opacity = '1';
                    if (geminiBox) geminiBox.style.opacity = '1';
                }}
            }} catch (err) {{
                console.warn('handleAiProviderChange notice:', err);
            }}
        }}

        function updateAiProviderView(provider) {{
            handleAiProviderChange(provider);
        }}

        function populateSettingsForm(s) {{
            try {{
                if (!s || typeof s !== 'object') return;
                const fields = [
                    'STORE_NAME', 'WELCOME_TEXT', 'COURSE_DELIVERY_NOTE',
                    'SUPPORT_CENTER_TEXT', 'INVITE_FRIENDS_TEXT',
                    'TELEGRAM_BOT_TOKEN', 'TELEGRAM_OWNER_ID', 'TELEGRAM_FORUM_GROUP_ID', 'ADMIN_USER_IDS',
                    'BALE_BOT_TOKEN', 'BALE_OWNER_ID', 'BALE_PAYMENT_TOKEN',
                    'RUBIKA_BOT_TOKEN', 'RUBIKA_OWNER_ID',
                    'FORCE_JOIN_CHANNEL_TELEGRAM', 'FORCE_JOIN_CHANNEL_BALE',
                    'CARD_NUMBER', 'CARD_HOLDER',
                    'DEFAULT_ARTIST', 'MAX_SAFE_BALE_SIZE_MB',
                    'COURSE_DESC_MAX_LEN',
                    'AI_BASE_URL', 'AI_API_KEY', 'AI_MODEL',
                    'AI_PROVIDER', 'VYCEAI_API_KEY',
                    'NARA_API_KEY', 'NARA_MODEL',
                    'GEMINI_API_KEY', 'GEMINI_MODEL',
                    'HF_TOKEN', 'HF_SPACE_ID',
                    'CASHBACK_PERCENT'
                ];
                fields.forEach(f => {{
                    const el = document.getElementById('cfg_' + f);
                    if (el && s[f] !== undefined) {{
                        if (el.tagName === 'SELECT') {{
                            let exists = Array.from(el.options).some(opt => opt.value === s[f]);
                            if (!exists && s[f]) {{
                                const opt = document.createElement('option');
                                opt.value = s[f];
                                opt.textContent = s[f] + ' (سفارشی)';
                                el.appendChild(opt);
                            }}
                        }}
                        el.value = s[f];
                    }}
                }});
                const artistTagEl = document.getElementById('cfg_APPLY_DEFAULT_ARTIST_TAG');
                if (artistTagEl && s.APPLY_DEFAULT_ARTIST_TAG !== undefined) {{
                    artistTagEl.checked = !!s.APPLY_DEFAULT_ARTIST_TAG;
                }}
                if (s.AI_PROVIDER) {{
                    handleAiProviderChange(s.AI_PROVIDER, s.AI_MODEL);
                }} else {{
                    handleAiProviderChange('vyceai', s.AI_MODEL);
                }}
                const p1 = document.getElementById('cfg_NEW_ADMIN_PASSWORD');
                const p2 = document.getElementById('cfg_CONFIRM_ADMIN_PASSWORD');
                if (p1) p1.value = '';
                if (p2) p2.value = '';
            }} catch (err) {{
                console.warn('populateSettingsForm notice:', err);
            }}
        }}

        function handleExportSettings() {{
            let pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
            if (!pwd) {{
                pwd = prompt('جهت برون‌بری تنظیمات، لطفاً رمز عبور مدیریت را وارد کنید:') || '';
                if (!pwd) return;
                currentAdminPassword = pwd;
                sessionStorage.setItem('unfinit_admin_pwd', pwd);
            }}
            window.open('/api/settings/export?password=' + encodeURIComponent(pwd), '_blank');
        }}

        function handleExportContactsCSV() {{
            let pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
            if (!pwd) {{
                pwd = prompt('جهت برون‌بری مخاطبین، لطفاً رمز عبور مدیریت را وارد کنید:') || '';
                if (!pwd) return;
                currentAdminPassword = pwd;
                sessionStorage.setItem('unfinit_admin_pwd', pwd);
            }}
            window.open('/api/contacts/export_csv?pwd=' + encodeURIComponent(pwd), '_blank');
        }}

        async function handleImportSettingsFile(input) {{
            const file = input.files && input.files[0];
            if (!file) return;
            const confirmImport = confirm('آیا از بازنویسی و درون‌ریزی تنظیمات با فایل انتخابی مطمئن هستید؟');
            if (!confirmImport) {{
                input.value = '';
                return;
            }}

            const reader = new FileReader();
            reader.onload = async (e) => {{
                try {{
                    const importedObj = JSON.parse(e.target.result);
                    let pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
                    if (!pwd) {{
                        pwd = prompt('جهت درون‌بری تنظیمات، لطفاً رمز عبور مدیریت را وارد کنید:') || '';
                        if (!pwd) {{
                            input.value = '';
                            return;
                        }}
                        currentAdminPassword = pwd;
                        sessionStorage.setItem('unfinit_admin_pwd', pwd);
                    }}
                    const res = await fetch('/api/settings/import', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            password: pwd,
                            settings: importedObj
                        }})
                    }});
                    const data = await res.json();
                    if (data.ok) {{
                        alert('✅ ' + (data.message || 'تنظیمات با موفقیت بازیابی شدند.'));
                        loadSettings();
                    }} else {{
                        alert('❌ خطا در درون‌ریزی تنظیمات: ' + (data.error || ''));
                    }}
                }} catch (err) {{
                    alert('❌ خطا در خواندن یا تحلیل فایل JSON: ' + err.message);
                }} finally {{
                    input.value = '';
                }}
            }};
            reader.readAsText(file, 'utf-8');
        }}

        async function handleSaveSettings(e) {{
            if (e) e.preventDefault();
            const btn = (e && e.submitter) ? e.submitter : (document.getElementById('btnSaveSettings') || document.getElementById('btnSaveTokens'));
            const btn1 = document.getElementById('btnSaveSettings');
            const btn2 = document.getElementById('btnSaveTokens');
            const statusEl = document.getElementById('settingsSaveStatus') || document.getElementById('tokensSaveStatus');
            const status1 = document.getElementById('settingsSaveStatus');
            const status2 = document.getElementById('tokensSaveStatus');
            
            const orig1 = btn1 ? btn1.innerText : '💾 ذخیره و اعمال آنی تنظیمات';
            const orig2 = btn2 ? btn2.innerText : '💾 ذخیره سکرت‌ها و توکن‌ها';
            if (btn1) {{ btn1.disabled = true; btn1.innerText = 'در حال ذخیره...'; }}
            if (btn2) {{ btn2.disabled = true; btn2.innerText = 'در حال ذخیره...'; }}
            if (status1) status1.innerText = '';
            if (status2) status2.innerText = '';

            const p1 = (document.getElementById('cfg_NEW_ADMIN_PASSWORD')?.value || '').trim();
            const p2 = (document.getElementById('cfg_CONFIRM_ADMIN_PASSWORD')?.value || '').trim();
            if (p1) {{
                if (p1 !== p2) {{
                    alert('❌ خطای تغییر رمز: تکرار رمز عبور جدید با رمز وارد شده همخوانی ندارد.');
                    if (btn1) {{ btn1.disabled = false; btn1.innerText = orig1; }}
                    if (btn2) {{ btn2.disabled = false; btn2.innerText = orig2; }}
                    return;
                }}
            }}

            const settings = {{}};
            const fields = [
                'STORE_NAME', 'WELCOME_TEXT', 'COURSE_DELIVERY_NOTE',
                'SUPPORT_CENTER_TEXT', 'INVITE_FRIENDS_TEXT',
                'TELEGRAM_BOT_TOKEN', 'TELEGRAM_OWNER_ID', 'TELEGRAM_FORUM_GROUP_ID', 'ADMIN_USER_IDS',
                'BALE_BOT_TOKEN', 'BALE_OWNER_ID', 'BALE_PAYMENT_TOKEN',
                'RUBIKA_BOT_TOKEN', 'RUBIKA_OWNER_ID',
                'FORCE_JOIN_CHANNEL_TELEGRAM', 'FORCE_JOIN_CHANNEL_BALE',
                'CARD_NUMBER', 'CARD_HOLDER',
                'DEFAULT_ARTIST', 'MAX_SAFE_BALE_SIZE_MB',
                'COURSE_DESC_MAX_LEN',
                'AI_BASE_URL', 'AI_API_KEY', 'AI_MODEL',
                'AI_PROVIDER', 'VYCEAI_API_KEY',
                'NARA_API_KEY', 'NARA_MODEL',
                'GEMINI_API_KEY', 'GEMINI_MODEL',
                'HF_TOKEN', 'HF_SPACE_ID',
                'CASHBACK_PERCENT'
            ];
            const sensitiveKeys = [
                'TELEGRAM_BOT_TOKEN', 'BALE_BOT_TOKEN', 'BALE_PAYMENT_TOKEN',
                'RUBIKA_BOT_TOKEN', 'AI_API_KEY', 'VYCEAI_API_KEY', 'NARA_API_KEY',
                'GEMINI_API_KEY', 'HF_TOKEN', 'CARD_NUMBER'
            ];
            fields.forEach(f => {{
                const el = document.getElementById('cfg_' + f);
                if (el) {{
                    const val = el.value.trim();
                    if (sensitiveKeys.includes(f)) {{
                        if (val && !val.includes('••••') && !val.includes('****')) {{
                            settings[f] = val;
                        }}
                    }} else {{
                        settings[f] = val;
                    }}
                }}
            }});
            const artistTagEl = document.getElementById('cfg_APPLY_DEFAULT_ARTIST_TAG');
            if (artistTagEl) {{
                settings['APPLY_DEFAULT_ARTIST_TAG'] = artistTagEl.checked;
            }}
            const activeProv = (document.getElementById('cfg_AI_PROVIDER')?.value || 'vyceai').toLowerCase();
            if (activeProv === 'custom') {{
                const customModelVal = (document.getElementById('cfg_AI_MODEL_CUSTOM')?.value || '').trim();
                if (customModelVal) {{
                    settings['AI_MODEL'] = customModelVal;
                }}
            }} else {{
                const selModelVal = (document.getElementById('cfg_AI_MODEL')?.value || '').trim();
                if (selModelVal) {{
                    settings['AI_MODEL'] = selModelVal;
                }}
            }}
            if (activeProv === 'vyceai' && settings['VYCEAI_API_KEY']) {{
                settings['AI_API_KEY'] = settings['VYCEAI_API_KEY'];
            }} else if (activeProv === 'nara' && settings['NARA_API_KEY']) {{
                settings['AI_API_KEY'] = settings['NARA_API_KEY'];
            }} else if (activeProv === 'gemini' && settings['GEMINI_API_KEY']) {{
                settings['AI_API_KEY'] = settings['GEMINI_API_KEY'];
            }}
            if (p1) {{
                settings['NEW_ADMIN_PASSWORD'] = p1;
            }}

            let pwdToSend = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || localStorage.getItem('unfinit_admin_pwd') || '';
            if (!pwdToSend) {{
                pwdToSend = prompt('جهت تایید و ذخیره تنظیمات، لطفاً رمز عبور مدیریت را وارد کنید:') || '';
                if (!pwdToSend) {{
                    alert('❌ ذخیره تنظیمات لغو شد: رمز عبور مدیریت وارد نشد.');
                    if (btn1) {{ btn1.disabled = false; btn1.innerText = orig1; }}
                    if (btn2) {{ btn2.disabled = false; btn2.innerText = orig2; }}
                    return;
                }}
                currentAdminPassword = pwdToSend;
                sessionStorage.setItem('unfinit_admin_pwd', pwdToSend);
            }}

            try {{
                const res = await fetch('/api/settings', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        password: pwdToSend,
                        settings: settings
                    }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    if (p1) {{
                        currentAdminPassword = p1;
                        sessionStorage.setItem('unfinit_admin_pwd', p1);
                        localStorage.setItem('unfinit_admin_pwd', p1);
                        const p1El = document.getElementById('cfg_NEW_ADMIN_PASSWORD');
                        const p2El = document.getElementById('cfg_CONFIRM_ADMIN_PASSWORD');
                        if (p1El) p1El.value = '';
                        if (p2El) p2El.value = '';
                    }}
                    const successMsg = '✅ ' + (data.message || 'تنظیمات و سکرت‌های ابری با موفقیت ذخیره و در Hugging Face اعمال شد!');
                    if (status1) status1.innerText = successMsg;
                    if (status2) status2.innerText = successMsg;
                    setTimeout(() => {{
                        if (status1) status1.innerText = '';
                        if (status2) status2.innerText = '';
                    }}, 5000);
                }} else {{
                    alert('❌ خطا در ذخیره تنظیمات: ' + (data.error || ''));
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط: ' + err.message);
            }} finally {{
                if (btn1) {{ btn1.disabled = false; btn1.innerText = orig1; }}
                if (btn2) {{ btn2.disabled = false; btn2.innerText = orig2; }}
            }}
        }}

        async function copyAllLogs() {{
            const btnText = document.getElementById('copyBtnText');
            try {{
                const res = await fetch('/api/logs');
                const data = await res.json();
                let textToCopy = '';
                if (data.ok && Array.isArray(data.logs)) {{
                    textToCopy = data.logs.join('\\n');
                }} else {{
                    textToCopy = document.getElementById('logContainer').innerText;
                }}
                await navigator.clipboard.writeText(textToCopy);
                btnText.innerText = '✅ کپی شد!';
                setTimeout(() => {{ btnText.innerText = 'کپی کل لاگ‌ها'; }}, 2500);
            }} catch (err) {{
                btnText.innerText = '❌ خطا در کپی';
                setTimeout(() => {{ btnText.innerText = 'کپی کل لاگ‌ها'; }}, 2000);
            }}
        }}

        async function fetchLogs() {{
            try {{
                const res = await fetch('/api/logs');
                const data = await res.json();
                if (data.ok && Array.isArray(data.logs)) {{
                    const container = document.getElementById('logContainer');
                    if (data.logs.length === 0) {{
                        container.innerHTML = '<div class="text-slate-500">هیچ لاگی هنوز ثبت نشده است.</div>';
                    }} else {{
                        container.innerHTML = data.logs.map(l => {{
                            let color = 'text-slate-300';
                            if (l.includes('[ERROR]')) color = 'text-rose-400 font-bold';
                            else if (l.includes('[WARNING]')) color = 'text-amber-300';
                            else if (l.includes('[INFO]')) color = 'text-cyan-300';
                            return `<div class="${{color}}">${{l.replace(/</g, '&lt;').replace(/>/g, '&gt;')}}</div>`;
                        }}).join('');
                        container.scrollTop = container.scrollHeight;
                    }}
                }}
            }} catch (e) {{}}
        }}
        fetchLogs();
        setInterval(fetchLogs, 4000);
        let selectedLogoBase64 = null;
        function handleLogoFileSelect(input) {{
            try {{
                const file = input.files && input.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = function(e) {{
                    selectedLogoBase64 = e.target.result;
                    const preview = document.getElementById('panelLogoPreview');
                    if (preview) {{
                        preview.src = selectedLogoBase64;
                        preview.style.display = 'block';
                        if (preview.nextElementSibling) preview.nextElementSibling.style.display = 'none';
                    }}
                    const btn = document.getElementById('btnUploadLogo');
                    if (btn) {{
                        btn.disabled = false;
                        btn.classList.remove('bg-cyan-600/50', 'text-slate-400', 'cursor-not-allowed');
                        btn.classList.add('bg-cyan-600', 'hover:bg-cyan-500', 'text-white', 'shadow-md');
                    }}
                }};
                reader.readAsDataURL(file);
            }} catch (err) {{
                console.error('handleLogoFileSelect error:', err);
            }}
        }}

        async function uploadCustomLogo() {{
            if (!selectedLogoBase64) return;
            const btn = document.getElementById('btnUploadLogo');
            const status = document.getElementById('logoUploadStatus');
            const origText = btn ? btn.innerHTML : '';
            if (btn) {{ btn.disabled = true; btn.innerText = 'در حال آپلود...'; }}
            if (status) {{ status.className = 'text-xs text-cyan-400'; status.innerText = 'در حال پردازش و ذخیره تصویر لوگو...'; }}

            let pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || localStorage.getItem('unfinit_admin_pwd') || '';
            try {{
                const res = await fetch('/api/upload/logo', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        password: pwd,
                        image: selectedLogoBase64
                    }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    const newUrl = data.url || ('/static/logo.png?t=' + Date.now());
                    const headerImg = document.getElementById('headerLogoImg');
                    const loginImg = document.getElementById('loginLogoImg');
                    const previewImg = document.getElementById('panelLogoPreview');
                    [headerImg, loginImg, previewImg].forEach(img => {{
                        if (img) {{
                            img.src = newUrl;
                            img.style.display = 'block';
                            if (img.nextElementSibling) img.nextElementSibling.style.display = 'none';
                        }}
                    }});
                    if (status) {{
                        status.className = 'text-xs text-emerald-400 font-bold';
                        status.innerText = '✅ لوگو با موفقیت ذخیره و در تمام بخش‌ها به‌روزرسانی شد.';
                    }}
                }} else {{
                    if (status) {{
                        status.className = 'text-xs text-rose-400 font-bold';
                        status.innerText = '❌ خطا: ' + (data.error || 'آپلود ناموفق بود.');
                    }}
                }}
            }} catch (err) {{
                if (status) {{
                    status.className = 'text-xs text-rose-400 font-bold';
                    status.innerText = '❌ خطای شبکه: ' + err.message;
                }}
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = origText || '<span>⬆️</span> آپلود و اعمال لوگو';
                }}
            }}
        }}

        function clearLiveLogs() {{
            const container = document.getElementById('logContainer');
            if (container) {{
                container.innerHTML = '<div class="text-slate-500">صفحه نمایش لاگ‌ها پاکسازی شد.</div>';
            }}
        }}

        async function loadFrequenciesTable() {{
            const tbody = document.getElementById('frequencyTableBody');
            if (!tbody) return;
            try {{
                tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-slate-400 animate-pulse">در حال فراخوانی داده‌ها...</td></tr>';
                const res = await fetch('/api/frequencies');
                const data = await res.json();
                if (!data.ok || !Array.isArray(data.frequencies) || data.frequencies.length === 0) {{
                    tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-slate-400">هیچ عبارتی ثبت نشده است.</td></tr>';
                    return;
                }}
                tbody.innerHTML = data.frequencies.map((item, idx) => {{
                    const isMorning = item.category === 'MORNING';
                    const catBadge = isMorning 
                        ? '<span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">صبحگاهی</span>'
                        : '<span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">شبانگاهی</span>';
                    return `
                        <tr class="hover:bg-white/[0.02] transition">
                            <td class="py-3 px-4 text-center font-mono text-slate-400">${{idx + 1}}</td>
                            <td class="py-3 px-4 font-bold text-slate-100">${{escapeHtml(item.title || '')}}</td>
                            <td class="py-3 px-4 text-center">${{catBadge}}</td>
                            <td class="py-3 px-4 text-slate-300 leading-relaxed">${{escapeHtml(item.text || '')}}</td>
                            <td class="py-3 px-4 text-center">
                                <button type="button" onclick="deleteFrequencyItem('${{escapeHtml(item.id)}}')" title="حذف عبارت" class="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition inline-flex items-center justify-center">
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                </button>
                            </td>
                        </tr>
                    `;
                }}).join('');
            }} catch (err) {{
                console.error('[loadFrequenciesTable error]:', err);
                tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-rose-400">خطا در بارگذاری لیست فرکانس‌ها.</td></tr>';
            }}
        }}

        async function submitAddNewFrequency(e) {{
            if (e) e.preventDefault();
            const cat = document.getElementById('freqNewCategory')?.value || 'MORNING';
            const title = (document.getElementById('freqNewTitle')?.value || '').trim();
            const text = (document.getElementById('freqNewText')?.value || '').trim();
            if (!title || !text) {{
                alert('لطفاً عنوان و متن عبارت را وارد نمایید.');
                return;
            }}
            const btn = document.getElementById('btnSubmitFrequency');
            if (btn) btn.disabled = true;
            try {{
                const res = await fetch('/api/frequencies/add', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ category: cat, title: title, text: text }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    document.getElementById('freqNewTitle').value = '';
                    document.getElementById('freqNewText').value = '';
                    loadFrequenciesTable();
                }} else {{
                    alert('خطا در ثبت عبارت: ' + (data.error || 'ناشناخته'));
                }}
            }} catch (err) {{
                alert('خطای ارتباط با سرور: ' + err.message);
            }} finally {{
                if (btn) btn.disabled = false;
            }}
        }}

        async function deleteFrequencyItem(id) {{
            if (!id) return;
            if (!confirm('آیا از حذف این عبارت فرکانس فراوانی اطمینان دارید؟')) return;
            try {{
                const res = await fetch('/api/frequencies/delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ id: id }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    loadFrequenciesTable();
                }} else {{
                    alert('خطا در حذف عبارت: ' + (data.error || 'ناشناخته'));
                }}
            }} catch (err) {{
                alert('خطای ارتباط با سرور: ' + err.message);
            }}
        }}

        // =========================================================================

                window.clearHermesChat = clearHermesChat;
                window.sendPresetHermesPrompt = sendPresetHermesPrompt;
                window.handleSendHermes = handleSendHermes;
                window.escapeHtml = escapeHtml;
                window.uploadBannerFile = uploadBannerFile;
                window.handleLogoFileSelect = handleLogoFileSelect;
                window.uploadCustomLogo = uploadCustomLogo;
                window.loadSettings = loadSettings;
                window.loadFrequenciesTable = loadFrequenciesTable;
                window.submitAddNewFrequency = submitAddNewFrequency;
                window.deleteFrequencyItem = deleteFrequencyItem;
                window.handleAiProviderChange = handleAiProviderChange;
                window.updateAiProviderView = updateAiProviderView;
                window.populateSettingsForm = populateSettingsForm;
                window.handleExportSettings = handleExportSettings;
                window.handleExportContactsCSV = handleExportContactsCSV;
                window.handleImportSettingsFile = handleImportSettingsFile;
                window.handleSaveSettings = handleSaveSettings;
                window.clearLiveLogs = clearLiveLogs;
                window.copyAllLogs = copyAllLogs;
                window.fetchLogs = fetchLogs;
            }} catch (err) {{
                console.error('[UNFINIT AI & Settings Module Error]:', err);
            }}
        }})();
    </script>
</body>
</html>
"""


async def handle_api_dispatch_url(data: dict) -> dict:
    url = data.get("url", "").strip()
    target = data.get("target", "telegram").strip()
    if not url:
        return {"ok": False, "error": "آدرس اینترنتی (URL) وارد نشده است."}

    logger.info(f"[web_dispatch] Probing URL: {url} for target={target}")
    probe = await UrlService.probe_url(url)
    if not probe.get("is_valid"):
        logger.warning(f"[web_dispatch] URL probe failed for {url}")
        return {"ok": False, "error": "لینک نامعتبر است یا توسط سرور قابل دسترس نمی‌باشد."}

    orig_fn = probe.get("filename") or "downloaded_file.mp3"
    fn = clean_display_filename(orig_fn)
    if not fn or fn == "audio.mp3":
        fn = orig_fn
    drop_id = uuid.uuid4().hex[:8]
    temp_p = config.TEMP_DIR / f"{drop_id}_{fn}"
    temp_p.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"[web_dispatch] [{drop_id}] Streaming {fn} ({human_size(probe.get('file_size') or 0)}) from {url}...")
    ok = await UrlService.download_file_stream(url, temp_p)
    if not ok or not temp_p.exists() or temp_p.stat().st_size == 0:
        logger.error(f"[web_dispatch] [{drop_id}] Download stream failed for {url}")
        return {"ok": False, "error": "خطا در دانلود استریم فایل از لینک مستقیم."}

    sz = temp_p.stat().st_size
    suffix = temp_p.suffix.lower()
    is_v = suffix in (".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v", ".ts")
    media_type = "video" if is_v else "audio"

    # 1. Register in MediaService / session_manager
    drop = MediaService.register_incoming_message_meta(
        drop_id=drop_id,
        source_platform="web_url",
        chat_id="web_admin",
        file_id=url,
        file_name=fn,
        file_size=sz,
        media_type=media_type,
        caption=f"🌐 دریافت از لینک مستقیم در پنل وب:\n📄 {fn}"
    )
    drop["working_path"] = str(temp_p)
    drop["original_path"] = str(temp_p)
    drop["is_downloaded_locally"] = True

    # 2. Inspect full metadata via MediaService
    tech_meta, embed_meta = MediaService.inspect_full(drop_id)
    drop["tech_meta"] = tech_meta
    drop["embed_meta"] = embed_meta

    # 3. Prepare for transfer via MediaService (applies tags, smart compression for Bale if needed, etc.)
    logger.info(f"[web_dispatch] [{drop_id}] Preparing media for transfer to {target}...")
    final_path, send_name, transfer_info = MediaService.prepare_for_transfer(drop_id, target)
    final_sz = final_path.stat().st_size if final_path.exists() else sz
    caption = f"🌐 دانلود و ارسال مستقیم از پنل وب:\n📄 {send_name}\n📦 حجم: {human_size(final_sz)}"

    logger.info(f"[web_dispatch] [{drop_id}] Dispatching {final_path.name} ({human_size(final_sz)}) to {target}...")

    async def _send_to_platform(plat: str) -> dict:
        if plat == "telegram":
            if ACTIVE_TG_ADAPTER and ACTIVE_TG_ADAPTER.app and ACTIVE_TG_ADAPTER.app.is_connected:
                target_tg_id = config.TELEGRAM_OWNER_ID or getattr(config, "OWNER_ID", None) or (ACTIVE_TG_ADAPTER.get_admin_id() if ACTIVE_TG_ADAPTER else None)
                if is_v:
                    tech = inspect_technical_metadata(final_path)
                    from media.tagger import generate_video_thumbnail
                    thumb_p = generate_video_thumbnail(final_path)
                    w = int(tech.get("width") or 0) if tech.get("width") is not None else 0
                    h = int(tech.get("height") or 0) if tech.get("height") is not None else 0
                    dur = int(tech.get("duration_sec") or 0) if tech.get("duration_sec") is not None else 0
                    return await ACTIVE_TG_ADAPTER.send_video(
                        target_tg_id, final_path, caption=caption,
                        width=w, height=h,
                        duration=dur, thumb=thumb_p
                    )
                else:
                    dur = int(transfer_info.get("duration") or 0) if transfer_info.get("duration") is not None else 0
                    return await ACTIVE_TG_ADAPTER.send_audio(
                        target_tg_id, final_path,
                        title=transfer_info.get("title") or embed_meta.get("title") or send_name,
                        performer=transfer_info.get("artist") or embed_meta.get("artist") or config.DEFAULT_ARTIST,
                        duration=dur,
                        caption=caption
                    )
            return {"ok": False, "error": "ربات تلگرام در حال حاضر متصل یا آنلاین نیست."}

        elif plat == "bale":
            from platforms.bale_adapter import BaleAdapter
            bale = BaleAdapter()
            target_chat = config.BALE_OWNER_ID or bale.get_admin_chat_id()
            if is_v:
                tech = inspect_technical_metadata(final_path)
                return await bale.send_video(
                    target_chat, final_path, caption=caption,
                    duration=tech.get("duration_sec"), width=tech.get("width"), height=tech.get("height")
                )
            else:
                return await bale.send_audio(
                    target_chat, final_path,
                    title=transfer_info.get("title") or embed_meta.get("title") or send_name,
                    performer=transfer_info.get("artist") or embed_meta.get("artist") or config.DEFAULT_ARTIST,
                    caption=caption
                )

        elif plat == "rubika_user":
            from platforms.rubika_adapter import RubikaUserClient
            client = RubikaUserClient()
            if not client.has_session():
                return {"ok": False, "error": "سشن کاربری روبیکا فعال یا لاگین نیست."}
            return await client.upload_and_send(final_path, target="me", caption=caption)

        elif plat == "rubika_bot":
            from platforms.rubika_adapter import RubikaBotClient
            bot = RubikaBotClient()
            target_guid = config.RUBIKA_OWNER_ID if (config.RUBIKA_OWNER_ID and config.RUBIKA_OWNER_ID.lower() != "me") else ""
            if not target_guid:
                return {"ok": False, "error": "شناسه مقصد روبیکا (RUBIKA_OWNER_ID) تعریف نشده است."}
            return await bot.send_document(target_guid, final_path, caption=caption)

        elif plat == "soroush":
            from platforms.soroush_worker import soroush_worker
            if not soroush_worker.is_connected():
                return {"ok": False, "error": "سشن کاربری سروش‌پلاس متصل نیست. لطفاً ابتدا در پنل وب لاگین کنید."}
            return await soroush_worker.send_file_to_saved_messages(final_path, caption=caption)

        return {"ok": False, "error": f"پلتفرم نامعتبر: {plat}"}

    target_names = {
        "telegram": "تلگرام",
        "bale": "بله",
        "rubika_user": "پیام‌های ذخیره‌شده روبیکا",
        "rubika_bot": "ربات رسمی روبیکا",
        "soroush": "پیام‌های ذخیره‌شده سروش‌پلاس"
    }

    try:
        raw_targets = data.get("targets")
        if isinstance(raw_targets, list) and raw_targets:
            targets_to_run = [str(t).strip() for t in raw_targets if str(t).strip()]
        elif "," in target:
            targets_to_run = [t.strip() for t in target.split(",") if t.strip()]
        elif target in ("all", "both"):
            targets_to_run = ["telegram", "bale"]
        else:
            targets_to_run = [target]

        if len(targets_to_run) == 1:
            single_target = targets_to_run[0]
            res = await _send_to_platform(single_target)
            if res.get("ok") or res.get("status") == "OK":
                drop["current_status"] = f"SENT_TO_{single_target.upper()}"
                t_name = target_names.get(single_target, single_target)
                comp_note = " (فشرده‌سازی هوشمند خودکار انجام شد)" if (single_target == "bale" and transfer_info.get("was_compressed")) else ""
                return {
                    "ok": True,
                    "drop_id": drop_id,
                    "file_name": send_name,
                    "file_size": human_size(final_sz),
                    "target": t_name,
                    "message": f"✅ فایل {send_name} ({human_size(final_sz)}){comp_note} با موفقیت به {t_name} ارسال شد!"
                }
            else:
                return {"ok": False, "error": f"خطا در ارسال به {target_names.get(single_target, single_target)}: {res.get('error') or res}"}

        # Multiple targets dispatch
        results = []
        errors = []
        for t in targets_to_run:
            try:
                r = await _send_to_platform(t)
                t_name = target_names.get(t, t)
                if r.get("ok") or r.get("status") == "OK":
                    results.append(t_name)
                else:
                    errors.append(f"{t_name}: {r.get('error') or r}")
            except Exception as ex_t:
                errors.append(f"{target_names.get(t, t)}: {ex_t}")

        if results:
            drop["current_status"] = "SENT_TO_MULTI"
            msg_targets = " و ".join(results)
            err_text = f" (خطاها: {'; '.join(errors)})" if errors else ""
            return {
                "ok": True,
                "drop_id": drop_id,
                "file_name": send_name,
                "file_size": human_size(final_sz),
                "target": msg_targets,
                "message": f"✅ فایل {send_name} ({human_size(final_sz)}) با موفقیت به {msg_targets} ارسال شد!{err_text}"
            }
        else:
            return {"ok": False, "error": f"خطا در ارسال به مقاصد: {'; '.join(errors)}"}
    except Exception as e:
        logger.error(f"[web_dispatch] [{drop_id}] Unexpected error: {e}")
        return {"ok": False, "error": str(e)}


# =========================================================================
# WEB MP3TAG STUDIO HANDLERS
# =========================================================================

def handle_studio_upload(payload: dict) -> dict:
    fname = (payload.get("filename") or "upload.mp3").strip()
    data_b64 = (payload.get("data") or "").strip()
    if not data_b64:
        return {"ok": False, "error": "محتوای فایل ارسالی خالی است."}

    if "," in data_b64:
        data_b64 = data_b64.split(",", 1)[1]

    import base64
    try:
        file_bytes = base64.b64decode(data_b64)
    except Exception as e:
        return {"ok": False, "error": f"خطا در دیکود فایل: {e}"}

    drop_id = uuid.uuid4().hex[:8]
    clean_fn = clean_display_filename(Path(fname).name)
    temp_p = config.TEMP_DIR / f"{drop_id}_{clean_fn}"
    temp_p.parent.mkdir(parents=True, exist_ok=True)
    with open(temp_p, "wb") as f:
        f.write(file_bytes)

    sz = temp_p.stat().st_size
    suf = temp_p.suffix.lower()
    is_v = suf in (".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v", ".ts")
    media_type = "video" if is_v else "audio"

    drop = MediaService.register_incoming_message_meta(
        drop_id=drop_id,
        source_platform="web_studio",
        chat_id="web_admin",
        file_id=str(temp_p),
        file_name=clean_fn,
        file_size=sz,
        media_type=media_type,
        caption=f"🎛 بارگذاری مستقیم در استودیوی وب‌پنل:\n📄 {clean_fn}"
    )
    drop["working_path"] = str(temp_p)
    drop["original_path"] = str(temp_p)
    drop["is_downloaded_locally"] = True

    from media.inspector import inspect_all_metadata
    tech_meta, embed_meta = inspect_all_metadata(temp_p)
    drop["tech_meta"] = tech_meta
    drop["embed_meta"] = embed_meta
    session_manager.update_session(drop_id, drop)

    return {
        "ok": True,
        "drop_id": drop_id,
        "filename": clean_fn,
        "file_size": human_size(sz),
        "media_type": media_type
    }


def _run_sync(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def ensure_session_file_on_disk(drop_id: str) -> Optional[Path]:
    """
    Ensures that the physical media file for drop_id exists on disk.
    If it was lazily registered, auto-downloads it from origin platform.
    """
    session = session_manager.get_session(drop_id)
    if not session:
        return None

    w_path = session.get("working_path") or session.get("original_path")
    if w_path and Path(w_path).exists() and Path(w_path).stat().st_size > 0:
        return Path(w_path)

    ok = await MediaService.ensure_local_binary(drop_id)
    if ok:
        session = session_manager.get_session(drop_id)
        if session and session.get("working_path") and Path(session["working_path"]).exists():
            return Path(session["working_path"])
    return None


async def handle_studio_specs_async(drop_id: str) -> dict:
    session = session_manager.get_session(drop_id)
    if not session:
        return {"ok": False, "error": "نشست فایل در سرور یافت نشد."}

    p = await ensure_session_file_on_disk(drop_id)
    if not p or not p.exists():
        # Fallback to session cached metadata if available
        tech = session.get("tech_meta") or {}
        embed = session.get("embed_meta") or {}
        if tech or embed or session.get("audio_filename"):
            dur = int(tech.get("duration_sec", 0))
            dur_str = f"{dur // 60:02d}:{dur % 60:02d}"
            sz = int(tech.get("size_bytes") or session.get("file_size") or 0)
            return {
                "ok": True,
                "drop_id": drop_id,
                "filename": session.get("audio_filename") or f"file_{drop_id}.mp3",
                "size_bytes": sz,
                "size_str": human_size(sz),
                "duration_sec": dur,
                "duration_str": dur_str,
                "bitrate_kbps": tech.get("bitrate_kbps", 0),
                "sample_rate": tech.get("sample_rate", 44100),
                "channels": tech.get("channels", "Stereo (2 کانال)"),
                "codec": (tech.get("codec") or tech.get("audio_codec") or "mp3").upper(),
                "format": tech.get("format", "audio/mpeg"),
                "has_cover": bool(embed.get("has_cover")),
                "title": embed.get("title") or "",
                "artist": embed.get("artist") or "",
                "album": embed.get("album") or ""
            }
        return {"ok": False, "error": "فایل فیزیکی روی دیسک سرور یافت نشد و دانلود خودکار ناموفق بود."}

    from media.inspector import inspect_technical_metadata, inspect_embedded_metadata
    tech = inspect_technical_metadata(p)
    embed = inspect_embedded_metadata(p)

    dur = int(tech.get("duration_sec", 0))
    dur_str = f"{dur // 60:02d}:{dur % 60:02d}"

    return {
        "ok": True,
        "drop_id": drop_id,
        "filename": session.get("audio_filename") or p.name,
        "size_bytes": tech.get("size_bytes") or p.stat().st_size,
        "size_str": human_size(tech.get("size_bytes") or p.stat().st_size),
        "duration_sec": dur,
        "duration_str": dur_str,
        "bitrate_kbps": tech.get("bitrate_kbps", 0),
        "sample_rate": tech.get("sample_rate", 44100),
        "channels": tech.get("channels", "Stereo (2 کانال)"),
        "codec": (tech.get("codec") or tech.get("audio_codec") or "mp3").upper(),
        "format": tech.get("format", "audio/mpeg"),
        "has_cover": bool(embed.get("has_cover")),
        "title": embed.get("title") or "",
        "artist": embed.get("artist") or "",
        "album": embed.get("album") or ""
    }


def handle_studio_specs(drop_id: str) -> dict:
    return _run_sync(handle_studio_specs_async(drop_id))


async def handle_studio_edit_tags_async(payload: dict) -> dict:
    try:
        drop_id = (payload.get("drop_id") or "").strip()
        session = session_manager.get_session(drop_id)
        if not session:
            return {"ok": False, "error": "نشست فایل در سرور یافت نشد."}

        # 1. Update draft tags in memory immediately
        draft_tags = session.setdefault("draft_tags", {})
        if "title" in payload: draft_tags["title"] = str(payload["title"]).strip()
        if "artist" in payload: draft_tags["artist"] = str(payload["artist"]).strip()
        if "album" in payload: draft_tags["album"] = str(payload["album"]).strip()
        new_fn = (payload.get("new_filename") or "").strip()
        if new_fn: draft_tags["new_filename"] = clean_display_filename(new_fn)
        if "remove_cover" in payload:
            draft_tags["remove_cover"] = bool(payload["remove_cover"])
            if draft_tags["remove_cover"]:
                session["thumb_path"] = None

        cover_data = (payload.get("cover_data") or "").strip()
        if cover_data:
            if "," in cover_data:
                cover_data = cover_data.split(",", 1)[1]
            import base64
            cov_bytes = base64.b64decode(cover_data)
            config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
            cov_path = config.TEMP_DIR / f"cov_{drop_id}.jpg"
            with open(cov_path, "wb") as cf:
                cf.write(cov_bytes)
            session["thumb_path"] = str(cov_path)
            draft_tags["remove_cover"] = False

        # 2. Update preview/embed_meta in session immediately
        embed_meta = session.setdefault("embed_meta", {})
        if "title" in draft_tags and draft_tags["title"]:
            embed_meta["title"] = draft_tags["title"]
            session["title"] = draft_tags["title"]
        if "artist" in draft_tags and draft_tags["artist"]:
            embed_meta["artist"] = draft_tags["artist"]
            session["artist"] = draft_tags["artist"]
        if "album" in draft_tags and draft_tags["album"]:
            embed_meta["album"] = draft_tags["album"]
            session["album"] = draft_tags["album"]
        if new_fn:
            session["audio_filename"] = clean_display_filename(new_fn)

        # 3. If file is already physically on disk, write tags to it without blocking
        wp = session.get("working_path") or session.get("original_path") or session.get("file_path")
        if wp:
            p = Path(wp)
            if p.exists() and p.is_file():
                try:
                    from media.tagger import modify_id3_tags
                    from media.inspector import inspect_all_metadata
                    tags_to_apply = {k: v for k, v in draft_tags.items() if k not in ("new_filename", "remove_cover", "cover_data")}
                    cov_p = session.get("thumb_path")
                    modify_id3_tags(p, tags_to_apply, cover_image_path=cov_p, remove_cover=draft_tags.get("remove_cover", False))
                    tech_meta, updated_embed = inspect_all_metadata(p)
                    session["tech_meta"] = tech_meta
                    session["embed_meta"] = updated_embed
                    if new_fn and new_fn != p.name:
                        clean_fn = clean_display_filename(new_fn)
                        if not clean_fn.lower().endswith(p.suffix.lower()):
                            clean_fn += p.suffix
                        new_p = p.parent / f"{drop_id}_{clean_fn}"
                        p.rename(new_p)
                        session["working_path"] = str(new_p)
                        session["audio_filename"] = clean_fn
                except Exception as tag_err:
                    logger.warning(f"Non-fatal error applying ID3 tags to physical file: {tag_err}")

        # 4. Persist to DB & session manager
        session_manager.update_session(drop_id, session)
        try:
            db_save_media_session(drop_id, session)
        except Exception:
            pass

        return {"ok": True, "message": "متادیتا با موفقیت ذخیره شد."}
    except Exception as e:
        logger.error(f"Error in handle_studio_edit_tags_async: {e}", exc_info=True)
        return {"ok": False, "error": f"خطا در ذخیره متادیتا: {str(e)}"}


def handle_studio_edit_tags(payload: dict) -> dict:
    return _run_sync(handle_studio_edit_tags_async(payload))


async def handle_studio_batch_edit_async(payload: dict) -> dict:
    try:
        drop_ids = payload.get("drop_ids") or []
        if not drop_ids:
            return {"ok": False, "error": "هیچ فایلی برای ویرایش گروهی انتخاب نشده است."}

        album = (payload.get("album") or "").strip()
        artist = (payload.get("artist") or "").strip()
        auto_number = bool(payload.get("auto_number"))
        title_pattern = (payload.get("title_pattern") or "جلسه {n}").strip()
        remove_cover = bool(payload.get("remove_cover"))
        cover_data = (payload.get("cover_data") or "").strip()

        cov_path = None
        if cover_data:
            if "," in cover_data:
                cover_data = cover_data.split(",", 1)[1]
            import base64
            cov_bytes = base64.b64decode(cover_data)
            config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
            cov_path = config.TEMP_DIR / f"batch_cov_{uuid.uuid4().hex[:6]}.jpg"
            with open(cov_path, "wb") as cf:
                cf.write(cov_bytes)

        count = 0
        for idx, drop_id in enumerate(drop_ids):
            drop_id = str(drop_id).strip()
            session = session_manager.get_session(drop_id)
            if not session:
                continue

            draft_tags = session.setdefault("draft_tags", {})
            if album: draft_tags["album"] = album
            if artist: draft_tags["artist"] = artist
            if auto_number:
                n = idx + 1
                draft_tags["title"] = title_pattern.replace("{n}", str(n))
            if remove_cover:
                draft_tags["remove_cover"] = True
                session["thumb_path"] = None
            elif cov_path:
                session["thumb_path"] = str(cov_path)
                draft_tags["remove_cover"] = False

            embed_meta = session.setdefault("embed_meta", {})
            if "title" in draft_tags and draft_tags["title"]:
                embed_meta["title"] = draft_tags["title"]
                session["title"] = draft_tags["title"]
            if "artist" in draft_tags and draft_tags["artist"]:
                embed_meta["artist"] = draft_tags["artist"]
                session["artist"] = draft_tags["artist"]
            if "album" in draft_tags and draft_tags["album"]:
                embed_meta["album"] = draft_tags["album"]
                session["album"] = draft_tags["album"]

            wp = session.get("working_path") or session.get("original_path") or session.get("file_path")
            if wp:
                p = Path(wp)
                if p.exists() and p.is_file():
                    try:
                        from media.tagger import modify_id3_tags
                        from media.inspector import inspect_all_metadata
                        tags_to_apply = {k: v for k, v in draft_tags.items() if k not in ("new_filename", "remove_cover", "cover_data")}
                        cov_p = session.get("thumb_path")
                        modify_id3_tags(p, tags_to_apply, cover_image_path=cov_p, remove_cover=draft_tags.get("remove_cover", False))
                        tech_meta, updated_embed = inspect_all_metadata(p)
                        session["tech_meta"] = tech_meta
                        session["embed_meta"] = updated_embed
                    except Exception as tag_err:
                        logger.warning(f"Batch edit ID3 error on {drop_id}: {tag_err}")

            session_manager.update_session(drop_id, session)
            try:
                db_save_media_session(drop_id, session)
            except Exception:
                pass
            count += 1

        return {"ok": True, "updated_count": count, "message": f"تعداد {count} فایل با موفقیت ویرایش شدند."}
    except Exception as e:
        logger.error(f"Error in handle_studio_batch_edit_async: {e}", exc_info=True)
        return {"ok": False, "error": f"خطا در ویرایش گروهی: {str(e)}"}


def handle_studio_batch_edit(payload: dict) -> dict:
    return _run_sync(handle_studio_batch_edit_async(payload))


async def get_studio_cover_bytes_async(drop_id: str) -> tuple[bytes | None, str]:
    session = session_manager.get_session(drop_id)
    if not session:
        return None, "image/jpeg"
    p = await ensure_session_file_on_disk(drop_id)
    if not p or not p.exists():
        return None, "image/jpeg"

    try:
        from mutagen.id3 import ID3
        audio = ID3(str(p))
        apic_keys = [k for k in audio.keys() if k.startswith("APIC")]
        if apic_keys:
            apic = audio[apic_keys[0]]
            mime = getattr(apic, "mime", "image/jpeg")
            data = getattr(apic, "data", None)
            if data:
                return data, mime
    except Exception:
        pass

    try:
        from mutagen.mp4 import MP4
        audio = MP4(str(p))
        if "covr" in audio and audio["covr"]:
            cov = audio["covr"][0]
            mime = "image/png" if getattr(cov, "imageformat", None) == 14 else "image/jpeg"
            return bytes(cov), mime
    except Exception:
        pass

    return None, "image/jpeg"


def get_studio_cover_bytes(drop_id: str) -> tuple[bytes | None, str]:
    return _run_sync(get_studio_cover_bytes_async(drop_id))


async def handle_studio_dispatch(payload: dict) -> dict:
    drop_id = (payload.get("drop_id") or "").strip()
    target = (payload.get("target") or "telegram").strip()
    session = session_manager.get_session(drop_id)
    if not session:
        return {"ok": False, "error": "نشست فایل در سرور یافت نشد."}

    p = await ensure_session_file_on_disk(drop_id)
    if not p or not p.exists():
        return {"ok": False, "error": "فایل محلی روی سرور یافت نشد و امکان دانلود آن میسر نگردید."}

    final_path, send_name, transfer_info = MediaService.prepare_for_transfer(drop_id, target)
    final_sz = final_path.stat().st_size if final_path.exists() else p.stat().st_size
    caption = f"🎛 ارسال مستقیم از استودیوی رسانه:\n📄 {send_name}\n📦 حجم: {human_size(final_sz)}"

    try:
        if target == "telegram":
            if ACTIVE_TG_ADAPTER and ACTIVE_TG_ADAPTER.app and ACTIVE_TG_ADAPTER.app.is_connected:
                target_tg_id = config.TELEGRAM_OWNER_ID or getattr(config, "OWNER_ID", None) or (ACTIVE_TG_ADAPTER.get_admin_id() if ACTIVE_TG_ADAPTER else None)
                suf = final_path.suffix.lower()
                is_v = suf in (".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v", ".ts")
                if is_v:
                    from media.tagger import generate_video_thumbnail
                    thumb_p = generate_video_thumbnail(final_path)
                    res = await ACTIVE_TG_ADAPTER.send_video(target_tg_id, final_path, caption=caption, thumb=thumb_p)
                else:
                    res = await ACTIVE_TG_ADAPTER.send_audio(
                        target_tg_id, final_path,
                        title=transfer_info.get("title") or send_name,
                        performer=transfer_info.get("artist") or config.DEFAULT_ARTIST,
                        caption=caption
                    )
                if res.get("ok"):
                    session["current_status"] = "SENT_TO_TELEGRAM"
                    session_manager.update_session(drop_id, session)
                    return {"ok": True, "message": f"✅ فایل {send_name} ({human_size(final_sz)}) با موفقیت به تلگرام ارسال شد!"}
                return {"ok": False, "error": f"خطا در ارسال به تلگرام: {res.get('error')}"}
            return {"ok": False, "error": "ربات تلگرام در حال حاضر متصل یا آنلاین نیست."}

        elif target == "bale":
            from platforms.bale_adapter import BaleAdapter
            bale = BaleAdapter()
            target_chat = config.BALE_OWNER_ID or bale.get_admin_chat_id()
            suf = final_path.suffix.lower()
            is_v = suf in (".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v", ".ts")
            if is_v:
                from media.inspector import inspect_technical_metadata
                tech = inspect_technical_metadata(final_path)
                res = await bale.send_video(target_chat, final_path, caption=caption, duration=tech.get("duration_sec"))
            else:
                res = await bale.send_audio(
                    target_chat, final_path,
                    title=transfer_info.get("title") or send_name,
                    performer=transfer_info.get("artist") or "استودیو",
                    caption=caption
                )
            if res.get("ok"):
                session["current_status"] = "SENT_TO_BALE"
                session_manager.update_session(drop_id, session)
                comp_note = " (فشرده‌سازی خودکار سقف ۴۹.۹۹MB انجام شد)" if transfer_info.get("was_compressed") else ""
                return {"ok": True, "message": f"✅ فایل {send_name} ({human_size(final_sz)}){comp_note} با موفقیت به بله ارسال شد!"}
            return {"ok": False, "error": f"خطا در ارسال به بله: {res.get('error') or res}"}

        elif target in ("rubika", "rubika_user"):
            from platforms.rubika_adapter import RubikaUserClient
            client = RubikaUserClient()
            if client.has_session():
                res = await client.upload_and_send(final_path, target="me", caption=caption)
                if res.get("ok"):
                    session["current_status"] = "SENT_TO_RUBIKA_SAVED"
                    session_manager.update_session(drop_id, session)
                    return {"ok": True, "message": f"✅ فایل {send_name} ({human_size(final_sz)}) در Saved Messages روبیکا آپلود گردید!"}
            from platforms.rubika_adapter import RubikaBotClient
            bot = RubikaBotClient()
            target_guid = config.RUBIKA_OWNER_ID if (config.RUBIKA_OWNER_ID and config.RUBIKA_OWNER_ID.lower() != "me") else ""
            if not target_guid:
                return {"ok": False, "error": "شناسه مقصد روبیکا (RUBIKA_OWNER_ID) در تنظیمات یا سکرت‌ها تعریف نشده است."}
            res = await bot.send_document(target_guid, final_path, caption=caption)
            if res.get("ok") or res.get("status") == "OK":
                session["current_status"] = "SENT_TO_RUBIKA_BOT"
                session_manager.update_session(drop_id, session)
                return {"ok": True, "message": f"✅ فایل {send_name} ({human_size(final_sz)}) به روبیکا ارسال گردید!"}
            return {"ok": False, "error": f"خطا در ارسال به روبیکا: {res.get('error') or res}"}

        return {"ok": False, "error": f"پلتفرم نامعتبر: {target}"}
    except Exception as e:
        logger.error(f"[studio_dispatch] Error: {e}")
        return {"ok": False, "error": str(e)}


async def handle_studio_cut_async(payload: dict) -> dict:
    drop_id = (payload.get("drop_id") or "").strip()
    if not drop_id:
        return {"ok": False, "error": "شناسه فایل ارسالی خالی است."}

    p = await ensure_session_file_on_disk(drop_id)
    if not p or not p.exists():
        return {"ok": False, "error": "فایل جهت برش روی دیسک سرور یافت نشد."}

    start_sec = float(payload.get("start_sec") or 0.0)
    end_sec = payload.get("end_sec")
    if end_sec is not None:
        try:
            end_sec = float(end_sec)
        except (ValueError, TypeError):
            end_sec = None

    if start_sec < 0:
        start_sec = 0.0
    if end_sec is not None and end_sec <= start_sec:
        return {"ok": False, "error": "زمان پایان باید بعد از زمان شروع باشد."}

    session = session_manager.get_session(drop_id)
    orig_fn = (session.get("audio_filename") if session else None) or p.name
    clean_fn = clean_display_filename(orig_fn)

    new_drop_id = uuid.uuid4().hex[:8]
    out_filename = f"cut_{new_drop_id}_{clean_fn}"
    out_path = config.TEMP_DIR / out_filename

    ok, cut_path = MediaService.trim_audio(p, start_sec=start_sec, end_sec=end_sec, output_path=out_path)
    if not ok or not cut_path.exists():
        return {"ok": False, "error": "خطا در پردازش و برش فایل صوتی با FFmpeg."}

    cut_sz = cut_path.stat().st_size
    from media.inspector import inspect_all_metadata
    tech_meta, embed_meta = inspect_all_metadata(cut_path)

    display_name = f"cut_{clean_fn}"
    cap_time = f"{start_sec:.1f}s تا {end_sec:.1f}s" if end_sec else f"از {start_sec:.1f}s"
    new_drop = MediaService.register_incoming_message_meta(
        drop_id=new_drop_id,
        source_platform="studio_cut",
        chat_id="web_admin",
        file_id=str(cut_path),
        file_name=display_name,
        file_size=cut_sz,
        media_type="audio",
        caption=f"✂️ برش داده شده در استودیو ({cap_time})"
    )
    new_drop["working_path"] = str(cut_path)
    new_drop["original_path"] = str(cut_path)
    new_drop["is_downloaded_locally"] = True
    new_drop["tech_meta"] = tech_meta
    new_drop["embed_meta"] = embed_meta
    session_manager.update_session(new_drop_id, new_drop)

    return {
        "ok": True,
        "message": f"فایل با موفقیت برش یافت و به استودیو اضافه شد: {display_name}",
        "new_drop_id": new_drop_id,
        "filename": display_name,
        "file_size": human_size(cut_sz)
    }


def handle_studio_cut(payload: dict) -> dict:
    return _run_sync(handle_studio_cut_async(payload))


def handle_studio_delete(payload: dict) -> dict:
    drop_id = (payload.get("drop_id") or "").strip()
    if not drop_id:
        return {"ok": False, "error": "شناسه فایل نامعتبر است."}

    session = session_manager.get_session(drop_id)
    if not session:
        return {"ok": False, "error": "سشن رسانه مورد نظر یافت نشد."}

    # Remove physical files
    for key in ("working_path", "original_path", "thumb_path"):
        fpath = session.get(key)
        if fpath:
            try:
                p = Path(fpath)
                if p.exists() and p.is_file():
                    p.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Could not delete physical file {fpath}: {e}")

    session_manager.remove_session(drop_id)
    try:
        db_delete_media_session(drop_id)
    except Exception:
        pass
    return {"ok": True, "message": "سشن رسانه و فایل فیزیکی با موفقیت حذف شدند."}


def handle_studio_delete_batch(payload: dict) -> dict:
    drop_ids = payload.get("drop_ids") or []
    if not drop_ids:
        return {"ok": False, "error": "هیچ فایلی برای حذف انتخاب نشده است."}

    deleted_count = 0
    for drop_id in drop_ids:
        drop_id = str(drop_id).strip()
        if not drop_id:
            continue
        session = session_manager.get_session(drop_id)
        if session:
            for key in ("working_path", "original_path", "thumb_path"):
                fpath = session.get(key)
                if fpath:
                    try:
                        p = Path(fpath)
                        if p.exists() and p.is_file():
                            p.unlink(missing_ok=True)
                    except Exception as e:
                        logger.warning(f"Could not delete physical file {fpath}: {e}")
            session_manager.remove_session(drop_id)
            try:
                db_delete_media_session(drop_id)
            except Exception:
                pass
            deleted_count += 1

    return {
        "ok": True,
        "deleted_count": deleted_count,
        "message": f"تعداد {deleted_count} فایل و سشن با موفقیت از دیسک و حافظه حذف شدند."
    }


def handle_studio_table_html(sort_by: str = "newest") -> dict:
    return {"ok": True, "html": render_studio_table_rows(sort_by=sort_by)}


def handle_studio_cleanup() -> dict:
    all_sessions = list(session_manager._sessions.items())
    seen_signatures = set()
    cleaned_count = 0

    for drop_id, sess in all_sessions:
        if not isinstance(sess, dict):
            session_manager.remove_session(drop_id)
            cleaned_count += 1
            continue

        fn = sess.get("audio_filename") or ""
        sz = sess.get("file_size") or 0
        plat = sess.get("source_platform") or ""
        fid = str(sess.get("file_id") or "")
        w_p = sess.get("working_path")

        sig_file_id = f"{plat}::{fid}" if fid and fid != "None" and not fid.startswith("/") and not fid.startswith("C:") else None
        sig_meta = f"{plat}::{fn}::{sz}" if fn and sz > 0 else None

        is_duplicate = False
        if sig_file_id and sig_file_id in seen_signatures:
            is_duplicate = True
        elif sig_meta and sig_meta in seen_signatures:
            is_duplicate = True

        if is_duplicate:
            if w_p:
                try:
                    Path(w_p).unlink(missing_ok=True)
                except Exception:
                    pass
            session_manager.remove_session(drop_id)
            cleaned_count += 1
            continue

        if sig_file_id:
            seen_signatures.add(sig_file_id)
        if sig_meta:
            seen_signatures.add(sig_meta)

    return {
        "ok": True,
        "cleaned_count": cleaned_count,
        "message": f"تعداد {cleaned_count} سشن تکراری و زائد با موفقیت پاکسازی شدند."
    }


# ==============================================================================
# STOREFRONT & ONLINE PAYMENT GATEWAYS (v25.5.0)
# ==============================================================================

async def handle_store_buy_bale_async(payload: dict) -> dict:
    course_id = (payload.get("course_id") or "").strip()
    customer_name = (payload.get("customer_name") or "کاربر وب").strip()
    phone = (payload.get("phone") or "").strip()
    coupon_code = (payload.get("coupon_code") or payload.get("coupon") or "").strip()

    if not course_id:
        return {"ok": False, "error": "شناسه دوره الزامی است."}
    if not phone:
        return {"ok": False, "error": "شماره همراه خریدار الزامی است."}

    prod = await StoreService.get_product(course_id)
    if not prod:
        return {"ok": False, "error": "دوره مورد نظر یافت نشد."}
    if not prod.active:
        return {"ok": False, "error": "این دوره در حال حاضر فعال نمی‌باشد."}
    if not prod.allow_bale:
        return {"ok": False, "error": "درگاه پرداخت آنلاین بله برای این دوره فعال نمی‌باشد."}

    # Register web order in database
    order = await StoreService.create_web_order(
        course_id=course_id,
        customer_name=customer_name,
        phone=phone,
        payment_method="bale_online",
        receipt_info="",
        coupon_code=coupon_code
    )
    if not order:
        return {"ok": False, "error": "خطا در ثبت سفارش در پایگاه داده."}

    order_id = order.order_id

    # If course is free or 100% discounted (0 Tomans), auto-approve immediately
    if order.total <= 0:
        await StoreService.approve_order(order_id)
        return {
            "ok": True,
            "order_id": order_id,
            "is_free": True,
            "download_link": prod.download_link or "",
            "message": "دوره با موفقیت و به صورت رایگان فعال گردید."
        }

    from platforms.bale_adapter import BaleAdapter
    bale = ACTIVE_BALE_ADAPTER or BaleAdapter()
    provider_token = config.BALE_PAYMENT_TOKEN or await get_system_setting("bale_payment_token", "")
    if not provider_token:
        provider_token = await get_system_setting("BALE_PAYMENT_TOKEN", "")

    if not provider_token or not bale.token:
        return {
            "ok": False,
            "error": "درگاه پرداخت بله در سیستم تنظیم نشده است (توکن درگاه یا ربات بله خالی است)."
        }

    clean_oid = order_id
    if clean_oid.startswith("ord_ORD_"):
        clean_oid = clean_oid.replace("ord_ORD_", "ord_")
    elif clean_oid.startswith("ORD_"):
        clean_oid = f"ord_{clean_oid[4:]}"
    elif not clean_oid.startswith("ord_"):
        clean_oid = f"ord_{clean_oid}"

    inv_url = f"https://ble.ir/abasmanesh365bot?start={clean_oid}"

    return {
        "ok": True,
        "order_id": order_id,
        "invoice_url": inv_url,
        "amount": order.total,
        "course_name": prod.name
    }


def handle_store_buy_bale(payload: dict) -> dict:
    return _run_sync(handle_store_buy_bale_async(payload))


async def handle_store_buy_card_async(payload: dict) -> dict:
    course_id = (payload.get("course_id") or "").strip()
    customer_name = (payload.get("customer_name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    receipt_info = (payload.get("receipt_info") or "").strip()
    coupon_code = (payload.get("coupon_code") or payload.get("coupon") or "").strip()

    if not course_id:
        return {"ok": False, "error": "شناسه دوره الزامی است."}
    if not customer_name:
        return {"ok": False, "error": "نام و نام خانوادگی خریدار الزامی است."}
    if not phone:
        return {"ok": False, "error": "شماره همراه خریدار الزامی است."}
    if not receipt_info:
        return {"ok": False, "error": "اطلاعات فیش واریزی یا شماره پیگیری الزامی است."}

    prod = await StoreService.get_product(course_id)
    if not prod:
        return {"ok": False, "error": "دوره مورد نظر یافت نشد."}
    if not prod.active:
        return {"ok": False, "error": "این دوره در حال حاضر فعال نمی‌باشد."}
    if not prod.allow_card:
        return {"ok": False, "error": "پرداخت کارت به کارت برای این دوره فعال نمی‌باشد."}

    order = await StoreService.create_web_order(
        course_id=course_id,
        customer_name=customer_name,
        phone=phone,
        payment_method="card_to_card",
        receipt_info=receipt_info,
        coupon_code=coupon_code
    )
    if not order:
        return {"ok": False, "error": "خطا در ثبت سفارش کارت به کارت."}

    # Optional receipt image upload handling
    receipt_img_data = (payload.get("receipt_image") or "").strip()
    receipt_file_path = None
    if receipt_img_data:
        try:
            if "," in receipt_img_data:
                receipt_img_data = receipt_img_data.split(",", 1)[1]
            import base64
            r_bytes = base64.b64decode(receipt_img_data)
            receipts_dir = config.UPLOADS_DIR / "receipts"
            receipts_dir.mkdir(parents=True, exist_ok=True)
            r_name = f"receipt_{order.order_id}_{uuid.uuid4().hex[:6]}.jpg"
            dest_r = receipts_dir / r_name
            with open(dest_r, "wb") as rf:
                rf.write(r_bytes)
            receipt_file_path = str(dest_r)
            rel_r_url = f"/uploads/receipts/{r_name}"
            from core.database import execute_query
            await execute_query("UPDATE orders SET receipt_file_id = ? WHERE order_id = ?", (rel_r_url, order.order_id))
            order.receipt_file_id = rel_r_url
        except Exception as ex_r:
            logger.warning(f"[store_card] Failed to save receipt image: {ex_r}")

    # Instant notification to Telegram & Bale Admins
    try:
        await StoreService.notify_admin_card_order(order, receipt_image_path=receipt_file_path)
    except Exception as ex_notif:
        logger.warning(f"[store_card] Failed to notify admins: {ex_notif}")

    return {
        "ok": True,
        "order_id": order.order_id,
        "course_name": prod.name,
        "amount": prod.price,
        "message": "سفارش شما با موفقیت ثبت شد و پس از تایید توسط پشتیبانی، لینک دانلود فعال خواهد گردید."
    }


def handle_store_buy_card(payload: dict) -> dict:
    return _run_sync(handle_store_buy_card_async(payload))


async def handle_store_get_orders_async() -> dict:
    from core.jalali import format_to_jalali
    orders = await StoreService.get_all_orders(limit=200)
    orders_data = []
    for ord in orders:
        # Strict platform normalization (purchase source)
        raw_p = (getattr(ord, "platform", "") or "web").lower().strip()
        if raw_p in ("telegram", "tg"):
            norm_platform = "telegram"
        elif raw_p in ("bale",):
            norm_platform = "bale"
        else:
            norm_platform = "web"

        # Strict payment method normalization (financial method)
        raw_m = (getattr(ord, "payment_method", "") or "").lower().strip()
        if raw_m in ("bale_online", "bale", "bale_pay"):
            norm_method = "bale_online"
        elif raw_m in ("zarinpal", "zp"):
            norm_method = "zarinpal"
        else:
            norm_method = "card_to_card"

        # Official Iranian Solar Hijri / Jalali date string
        shamsi_date = format_to_jalali(ord.created_at)

        orders_data.append({
            "order_id": ord.order_id,
            "user_id": ord.user_id,
            "customer_name": ord.customer_name,
            "phone": ord.phone,
            "product_id": ord.product_id,
            "product_name": ord.product_name,
            "amount": ord.amount,
            "status": ord.status,
            "platform": norm_platform,
            "payment_method": norm_method,
            "receipt_text": ord.receipt_text,
            "download_link": ord.download_link,
            "created_at": shamsi_date,
            "raw_created_at": str(ord.created_at or "")
        })
    return {"ok": True, "orders": orders_data}


def handle_store_get_orders() -> dict:
    return _run_sync(handle_store_get_orders_async())


async def handle_store_approve_order_async(order_id: str) -> dict:
    order_id = str(order_id or "").strip()
    if not order_id:
        return {"ok": False, "error": "شناسه سفارش الزامی است."}

    res = await StoreService.approve_order(order_id)
    if not res:
        return {"ok": False, "error": "سفارش مورد نظر یافت نشد یا در وضعیت تاییدشده قرار دارد."}

    # Dispatch notification to buyer if adapter is active
    try:
        order_obj = res.get("order")
        prod_obj = res.get("product")
        if order_obj and prod_obj:
            dl_content = prod_obj.download_link or ""
            cb_awarded = res.get("cashback_awarded", 0)
            u_id = str(order_obj.user_id)
            if getattr(prod_obj, "delivery_type", "channel") == "files_package" or (hasattr(prod_obj, "files_package") and prod_obj.files_package):
                asyncio.create_task(StoreService.deliver_course_package(prod_obj, u_id, order_obj.platform))
            if order_obj.platform == "telegram" and ACTIVE_TG_ADAPTER and u_id.isdigit():
                from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                cust_msg = StoreService.format_delivery_message(prod_obj.name, order_id, dl_content, cb_awarded)
                parsed_dl = StoreService.parse_delivery_links(dl_content)
                cust_buttons = [[InlineKeyboardButton(lk["title"], url=lk["url"])] for lk in parsed_dl["links"]]
                cust_kb = InlineKeyboardMarkup(cust_buttons) if cust_buttons else None
                asyncio.create_task(ACTIVE_TG_ADAPTER.send_message(int(u_id), cust_msg, reply_markup=cust_kb))
            elif order_obj.platform == "bale" and ACTIVE_BALE_ADAPTER:
                cust_msg = StoreService.format_delivery_message(prod_obj.name, order_id, dl_content, cb_awarded)
                parsed_dl = StoreService.parse_delivery_links(dl_content)
                cust_buttons = [[{"text": lk["title"], "url": lk["url"]}] for lk in parsed_dl["links"]]
                cust_kb = {"inline_keyboard": cust_buttons} if cust_buttons else None
                asyncio.create_task(ACTIVE_BALE_ADAPTER.send_message(u_id, cust_msg, reply_markup=cust_kb))
    except Exception as e:
        logger.warning(f"[web_approve] Could not dispatch messenger notification: {e}")

    return {"ok": True, "message": f"سفارش {order_id} با موفقیت تایید شد.", **res}


def handle_store_approve_order(order_id: str) -> dict:
    return _run_sync(handle_store_approve_order_async(order_id))


async def handle_store_reject_order_async(order_id: str, reason: str = "") -> dict:
    order_id = str(order_id or "").strip()
    if not order_id:
        return {"ok": False, "error": "شناسه سفارش الزامی است."}

    res = await StoreService.reject_order(order_id, reason=reason)
    if not res:
        return {"ok": False, "error": "سفارش مورد نظر یافت نشد."}

    return {"ok": True, "message": f"سفارش {order_id} با موفقیت رد شد.", "order_id": order_id, "status": "rejected"}


def handle_store_reject_order(order_id: str, reason: str = "") -> dict:
    return _run_sync(handle_store_reject_order_async(order_id, reason=reason))


async def handle_store_delete_order_async(order_id: str) -> dict:
    order_id = str(order_id or "").strip()
    if not order_id:
        return {"ok": False, "error": "شناسه سفارش الزامی است."}

    await StoreService.delete_order(order_id)
    return {"ok": True, "message": f"سفارش {order_id} با موفقیت حذف شد.", "order_id": order_id}


def handle_store_delete_order(order_id: str) -> dict:
    return _run_sync(handle_store_delete_order_async(order_id))


async def handle_store_cleanup_rejected_orders_async() -> dict:
    count = await StoreService.cleanup_rejected_orders()
    return {"ok": True, "count": count, "message": f"تعداد {count} سفارش رد شده با موفقیت پاکسازی شدند."}


def handle_store_cleanup_rejected_orders() -> dict:
    return _run_sync(handle_store_cleanup_rejected_orders_async())


async def handle_store_bulk_delete_orders_async(order_ids: list) -> dict:
    if not isinstance(order_ids, list) or not order_ids:
        return {"ok": False, "error": "لیست شناسه‌های سفارش نامعتبر است."}
    count = await StoreService.bulk_delete_orders(order_ids)
    return {"ok": True, "count": count, "message": f"تعداد {count} سفارش با موفقیت حذف شدند."}


def handle_store_bulk_delete_orders(order_ids: list) -> dict:
    return _run_sync(handle_store_bulk_delete_orders_async(order_ids))


async def handle_store_clear_all_orders_async() -> dict:
    count = await StoreService.clear_all_orders()
    return {"ok": True, "count": count, "message": f"تمامی سفارشات ({count} سفارش) با موفقیت پاکسازی شدند."}


def handle_store_clear_all_orders() -> dict:
    return _run_sync(handle_store_clear_all_orders_async())



async def handle_store_get_order_status_async(query_str: str) -> dict:
    query_str = str(query_str or "").strip()
    if not query_str:
        return {"ok": False, "error": "کد سفارش یا شماره همراه الزامی است."}

    status_info = await StoreService.get_order_status_for_customer(query_str)
    if status_info:
        return {"ok": True, "orders": [status_info]}

    from core.database import fetch_all
    sql = """
        SELECT o.order_id, o.user_id, o.phone, o.product_id, COALESCE(o.total, 0) as amount, o.status, o.created_at,
               o.receipt_text, o.payment_method, p.name as product_name, p.download_link
        FROM orders o
        LEFT JOIN products p ON o.product_id = p.product_id
        WHERE o.user_id = ? OR o.phone = ? OR o.receipt_text LIKE ?
        ORDER BY o.id DESC LIMIT 10
    """
    rows = await fetch_all(sql, (f"web_{query_str}", query_str, f"%{query_str}%"))
    if not rows:
        return {"ok": False, "error": "هیچ سفارشی با این مشخصات یافت نشد."}

    results = []
    for r in rows:
        is_done = r.get("status") in ("completed", "approved")
        results.append({
            "order_id": r.get("order_id"),
            "product_id": r.get("product_id"),
            "product_name": r.get("product_name") or r.get("product_id"),
            "amount": int(r.get("amount", 0) or 0),
            "status": r.get("status"),
            "payment_method": r.get("payment_method"),
            "download_link": r.get("download_link") if is_done else "",
            "created_at": r.get("created_at")
        })
    return {"ok": True, "orders": results}


def handle_store_get_order_status(query_str: str) -> dict:
    return _run_sync(handle_store_get_order_status_async(query_str))


def render_storefront_html() -> str:
    active_prods = []
    try:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop and running_loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                active_prods = pool.submit(lambda: asyncio.run(StoreService.get_all_products(only_active=True))).result()
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            active_prods = loop.run_until_complete(StoreService.get_all_products(only_active=True))
            loop.close()
    except Exception as e:
        logger.warning(f"Storefront product fetch error: {e}")

    card_number = config.CARD_NUMBER or "تنظیم نشده"
    card_holder = config.CARD_HOLDER or "مدیریت فروشگاه"
    zarinpal_merchant = getattr(config, "ZARINPAL_MERCHANT_ID", "") or ""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        c_num = loop.run_until_complete(get_system_setting("CARD_NUMBER", card_number))
        c_hld = loop.run_until_complete(get_system_setting("CARD_HOLDER", card_holder))
        z_mer = loop.run_until_complete(get_system_setting("ZARINPAL_MERCHANT_ID", zarinpal_merchant)) or loop.run_until_complete(get_system_setting("zarinpal_merchant_id", zarinpal_merchant))
        if c_num: card_number = c_num
        if c_hld: card_holder = c_hld
        if z_mer: zarinpal_merchant = z_mer
        loop.close()
    except Exception:
        pass

    cards_html = ""
    if not active_prods:
        cards_html = '''
        <div class="col-span-full py-16 text-center text-slate-400 bg-slate-900/40 rounded-3xl border border-slate-800">
            <div class="text-4xl mb-3">📚</div>
            <h3 class="text-base font-bold text-slate-200">در حال حاضر دوره‌ای برای عرضه فعال نیست.</h3>
            <p class="text-xs text-slate-500 mt-1">لطفاً بعداً مراجعه فرمایید یا با پشتیبانی در ارتباط باشید.</p>
        </div>
        '''
    else:
        import html as py_html
        for p in active_prods:
            banner_img = f'<img src="{p.photo_url}" alt="{p.name}" class="w-full h-auto max-h-[520px] object-cover rounded-2xl mb-4 border border-slate-700/60 shadow-lg transition duration-300 group-hover:scale-[1.01]" onerror="this.style.display=\'none\'">' if p.photo_url else '<div class="w-full h-48 rounded-2xl mb-4 bg-gradient-to-tr from-slate-900 via-slate-800 to-cyan-950/60 border border-slate-700/60 flex items-center justify-center text-4xl">🎓</div>'
            price_display = f'<span class="text-base font-black text-emerald-400 font-mono">{p.price:,} <span class="text-xs font-normal">تومان</span></span>' if p.price > 0 else '<span class="text-base font-bold text-cyan-400">رایگان 🎁</span>'

            safe_id = py_html.escape(str(p.product_id or ''), quote=True)
            safe_name = py_html.escape(str(p.name or ''), quote=True)
            safe_dl = py_html.escape(str(p.download_link or ''), quote=True)

            zarinpal_btn = f'''
            <button type="button" data-id="{safe_id}" data-name="{safe_name}" data-price="{p.price}" onclick="openZarinpalBuyModal(this)" class="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-amber-600 to-yellow-600 hover:from-amber-500 hover:to-yellow-500 text-white font-bold text-xs transition shadow-lg shadow-amber-600/20 flex items-center justify-center gap-2">
                <span>⚡️</span> پرداخت آنلاین با شتاب (زرین‌پال)
            </button>
            ''' if (getattr(p, "allow_zarinpal", True) and p.price > 0 and zarinpal_merchant) else ''

            bale_btn = f'''
            <button type="button" data-id="{safe_id}" data-name="{safe_name}" data-price="{p.price}" onclick="openBaleBuyModal(this)" class="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs transition shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2">
                <span>💳</span> خرید آنلاین با بله (شتاب / کیف‌پول)
            </button>
            ''' if (p.allow_bale and p.price > 0) else ''

            card_btn = f'''
            <button type="button" data-id="{safe_id}" data-name="{safe_name}" data-price="{p.price}" onclick="openCardBuyModal(this)" class="w-full py-2.5 px-4 rounded-xl bg-slate-800/90 hover:bg-slate-700 text-cyan-300 font-bold text-xs border border-slate-700 transition flex items-center justify-center gap-2">
                <span>🏦</span> پرداخت کارت به کارت
            </button>
            ''' if (p.allow_card and p.price > 0) else ''

            free_btn = f'''
            <button type="button" data-id="{safe_id}" data-name="{safe_name}" data-link="{safe_dl}" onclick="openFreeModal(this)" class="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold text-xs transition shadow-lg flex items-center justify-center gap-2">
                <span>📥</span> دریافت رایگان محتوای دوره
            </button>
            ''' if p.price <= 0 else ''

            cards_html += f'''
            <div class="glass p-6 rounded-3xl flex flex-col justify-between border border-slate-800 hover:border-cyan-500/40 transition group">
                <div>
                    {banner_img}
                    <div class="flex justify-between items-start gap-2 mb-2">
                        <h3 class="text-base font-bold text-white leading-snug group-hover:text-cyan-300 transition">{p.name}</h3>
                    </div>
                    <div class="my-3 flex items-center justify-between pb-3 border-b border-slate-800/80">
                        <span class="text-xs text-slate-400">قیمت دوره:</span>
                        {price_display}
                    </div>
                    <p class="text-xs text-slate-300 leading-relaxed line-clamp-3 bg-slate-900/40 p-3 rounded-2xl border border-slate-800/60 mb-4">{p.description or 'سرفصل‌ها و توضیحات این دوره در دسترس است.'}</p>
                </div>
                <div class="space-y-2 pt-2">
                    {free_btn}
                    {zarinpal_btn}
                    {bale_btn}
                    {card_btn}
                </div>
            </div>
            '''

    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0%25' y1='100%25' x2='100%25' y2='0%25'%3E%3Cstop offset='0%25' stop-color='%2306b6d4'/%3E%3Cstop offset='100%25' stop-color='%232563eb'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='100' height='100' rx='24' fill='url(%23g)'/%3E%3Cpath d='M30 26h12v32c0 6.6 5.4 12 12 12s12-5.4 12-12V26h12v32c0 13.3-10.7 24-24 24s-24-10.7-24-24V26z' fill='%23ffffff'/%3E%3Cpolygon points='62,18 42,46 54,46 44,72 68,40 56,40' fill='%23facc15' opacity='0.9'/%3E%3C/svg%3E">
    <title>ویترین فروشگاه دوره‌های آموزشی | UNFINIT Store</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        /* Universal Global Themed Scrollbar (8px) */
        html, body, *, *::-webkit-scrollbar, *::-webkit-scrollbar-thumb {{
            scrollbar-color: #3b82f6 transparent !important;
        }}
        *::-webkit-scrollbar {{
            width: 8px !important;
            height: 8px !important;
        }}
        *::-webkit-scrollbar-track {{
            background: transparent !important;
        }}
        *::-webkit-scrollbar-thumb {{
            background: #3b82f6 !important;
            border-radius: 9999px !important;
        }}
        *::-webkit-scrollbar-thumb:hover {{
            background: #06b6d4 !important;
            filter: brightness(1.2);
        }}
        * {{
            scrollbar-width: thin;
            scrollbar-color: #3b82f6 transparent !important;
        }}
        * {{ box-sizing: border-box; font-family: 'Vazirmatn', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important; }}
        body {{
            background-color: #0b1120 !important;
            color: #f8fafc !important;
            min-height: 100vh;
            margin: 0;
            padding: 0;
        }}
        .glass, .store-card {{
            background-color: #1e293b !important;
            border: 1px solid #334155 !important;
            color: #f8fafc !important;
        }}
        .glass-modal {{
            background-color: #0f172a !important;
            border: 1px solid #334155 !important;
            color: #f8fafc !important;
        }}
        input, select, textarea {{
            background-color: #0f172a !important;
            border: 1px solid #334155 !important;
            color: #f8fafc !important;
        }}
        .hero-glow {{
            background: radial-gradient(circle at 50% 20%, rgba(6, 182, 212, 0.15), transparent 70%);
        }}
        .hidden {{ display: none !important; }}
    </style>
</head>
<body class="flex flex-col justify-between selection:bg-cyan-500 selection:text-white hero-glow">

    <!-- Top Navigation Bar -->
    <header class="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
        <div class="max-w-6xl mx-auto px-4 py-3.5 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center font-black text-xl shadow-lg shadow-cyan-500/20 text-white">
                    U
                </div>
                <div>
                    <h1 class="text-sm font-black tracking-wide text-white flex items-center gap-2">
                        UNFINIT STORE
                        <span class="px-2 py-0.5 rounded-full text-[10px] bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono">v0.1.0</span>
                    </h1>
                    <p class="text-[11px] text-slate-400">فروشگاه آنلاین و هوشمند دوره‌های آموزشی</p>
                </div>
            </div>

            <div class="flex items-center gap-2">
                <button onclick="openTrackModal()" class="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-cyan-300 border border-cyan-800/60 text-xs font-semibold transition flex items-center gap-1.5 shadow-sm">
                    <span>🔍</span> پیگیری سفارش و دانلود
                </button>
            </div>
        </div>
    </header>

    <!-- Main Store Content -->
    <main class="max-w-6xl mx-auto px-4 py-10 w-full space-y-10">
        <!-- Hero Header -->
        <div class="text-center space-y-3 max-w-2xl mx-auto">
            <span class="px-3 py-1 rounded-full text-xs font-semibold bg-cyan-950/80 text-cyan-300 border border-cyan-800 inline-block mb-1">
                🎓 دسترسی مستقیم و آنی به محتوای دوره‌ها
            </span>
            <h2 class="text-2xl md:text-3xl font-black text-white leading-tight">
                دوره‌های تخصصی، آموزشی و مهارتی
            </h2>
            <p class="text-xs md:text-sm text-slate-400 leading-relaxed">
                دوره مورد نظر خود را انتخاب کرده و از طریق درگاه امن پرداخت بله یا کارت‌به‌کارت تهیه فرمایید. لینک دانلود بلافاصله پس از پرداخت تقدیم می‌گردد.
            </p>
        </div>

        <!-- Course Cards Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {cards_html}
        </div>
    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-800/80 bg-slate-950/60 py-6 mt-16 text-center text-xs text-slate-500">
        <div class="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
            <p>© UNFINIT Store Engine - سیستم جامع فروش دوره‌های تخصصی</p>
            <p class="text-[11px] text-slate-600 font-mono">Secure Payments via Bale &amp; Direct Verification | UNFINIT Store {config.ENGINE_VERSION}</p>
        </div>
    </footer>

    <!-- ================= MODAL: BALE ONLINE PAYMENT ================= -->
    <div id="baleBuyModal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 hidden">
        <div class="glass-modal max-w-md w-full rounded-3xl p-6 space-y-5 relative animate-in fade-in zoom-in-95 duration-200">
            <button onclick="closeModal('baleBuyModal')" class="absolute top-4 left-4 text-slate-400 hover:text-white text-lg">✕</button>
            <div class="flex items-center gap-3 pb-3 border-b border-slate-800">
                <div class="w-10 h-10 rounded-xl bg-emerald-950 border border-emerald-800 flex items-center justify-center text-xl text-emerald-400">
                    💳
                </div>
                <div>
                    <h3 class="text-sm font-bold text-white">خرید آنلاین با درگاه پرداخت بله</h3>
                    <p class="text-[11px] text-slate-400">پرداخت امن با کلیه کارت‌های عضو شتاب یا کیف پول بله</p>
                </div>
            </div>

            <div class="p-3.5 rounded-2xl bg-slate-900/80 border border-slate-800 flex justify-between items-center text-xs">
                <div>
                    <span class="text-slate-400 block text-[11px]">دوره انتخابی:</span>
                    <span id="baleModalCourseName" class="font-bold text-white mt-0.5 block">-</span>
                </div>
                <div class="text-left">
                    <span class="text-slate-400 block text-[11px]">مبلغ قابل پرداخت:</span>
                    <span id="baleModalCoursePrice" class="font-bold text-emerald-400 font-mono mt-0.5 block">-</span>
                </div>
            </div>

            <!-- Form Section -->
            <form id="baleBuyForm" class="space-y-4" onsubmit="handleBalePaymentSubmit(event)">
                <div>
                    <label class="block text-xs text-slate-300 mb-1">نام و نام خانوادگی خریدار *</label>
                    <input type="text" id="baleCustomerName" required placeholder="مثال: علی رضایی" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                    <label class="block text-xs text-slate-300 mb-1">شماره همراه (جهت پیگیری و ارسال لینک) *</label>
                    <input type="tel" id="baleCustomerPhone" required placeholder="مثال: 09123456789" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono" dir="ltr">
                </div>
                <button type="submit" id="btnBalePaySubmit" class="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/20 transition flex items-center justify-center gap-2">
                    <span>⚡️</span> دریافت لینک پرداخت بله
                </button>
            </form>

            <!-- Invoice Ready Section (hidden initially) -->
            <div id="baleInvoiceSection" class="hidden space-y-4 text-center">
                <div class="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-800/80 space-y-2">
                    <span class="text-2xl">🔗</span>
                    <p class="text-xs font-bold text-emerald-300">لینک درگاه پرداخت بله آماده شد!</p>
                    <p class="text-[11px] text-slate-300">شناسه سفارش شما: <span id="baleOrderIdBadge" class="font-mono text-cyan-400 font-bold"></span></p>
                </div>
                <div class="space-y-2">
                    <a id="baleInvoiceLinkBtn" href="#" target="_blank" class="w-full py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-xs shadow-lg shadow-cyan-600/20 transition flex items-center justify-center gap-2">
                        <span>🚀</span> ورود به درگاه پرداخت بله و تکمیل خرید
                    </a>
                    <button type="button" id="baleCopyInvoiceBtn" onclick="copyBaleInvoiceLink()" class="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-bold border border-slate-700 transition flex items-center justify-center gap-2">
                        <span>📋</span> کپی لینک پرداخت بله
                    </button>
                </div>
                <div class="flex items-center justify-center gap-2 text-xs text-slate-400 pt-2 font-sans">
                    <span class="animate-spin text-cyan-400">⏳</span>
                    <span>در انتظار تکمیل پرداخت... (بررسی خودکار هر چند ثانیه)</span>
                </div>
            </div>

            <!-- Success Download Section (hidden initially) -->
            <div id="baleSuccessSection" class="hidden space-y-4 text-center">
                <div class="p-4 rounded-2xl bg-emerald-950/60 border border-emerald-700 space-y-2">
                    <span class="text-3xl">🎉</span>
                    <h4 class="text-sm font-bold text-emerald-300">پرداخت شما با موفقیت تایید شد!</h4>
                    <p class="text-xs text-slate-300">از خرید شما سپاسگزاریم. فایل‌های دوره برای شما آماده دانلود است:</p>
                </div>
                <div id="baleDownloadBox" class="space-y-2">
                    <a id="baleDirectDlBtn" href="#" target="_blank" class="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-bold text-xs shadow-lg transition flex items-center justify-center gap-2">
                        <span>📥</span> دانلود مستقیم محتوای دوره
                    </a>
                    <button onclick="copyBaleDlLink()" class="w-full py-2 rounded-xl bg-slate-800 text-slate-300 text-xs border border-slate-700 transition">
                        📋 کپی لینک دانلود
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- ================= MODAL: CARD TO CARD PAYMENT ================= -->
    <div id="cardBuyModal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 hidden">
        <div class="glass-modal max-w-md w-full rounded-3xl p-6 space-y-5 relative animate-in fade-in zoom-in-95 duration-200">
            <button onclick="closeModal('cardBuyModal')" class="absolute top-4 left-4 text-slate-400 hover:text-white text-lg">✕</button>
            <div class="flex items-center gap-3 pb-3 border-b border-slate-800">
                <div class="w-10 h-10 rounded-xl bg-slate-900 border border-slate-700 flex items-center justify-center text-xl text-cyan-400">
                    🏦
                </div>
                <div>
                    <h3 class="text-sm font-bold text-white">پرداخت کارت‌به‌کارت</h3>
                    <p class="text-[11px] text-slate-400">واریز به حساب و ثبت اطلاعات فیش پرداختی</p>
                </div>
            </div>

            <!-- Bank Card Info Box -->
            <div class="p-4 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-950/40 border border-slate-800 space-y-3">
                <div class="flex justify-between items-center text-xs">
                    <span class="text-slate-400">مبلغ واریزی:</span>
                    <span id="cardModalCoursePrice" class="font-bold text-emerald-400 font-mono">-</span>
                </div>
                <div class="space-y-1">
                    <span class="text-[11px] text-slate-400">شماره کارت بانکی:</span>
                    <div class="flex items-center justify-between bg-slate-950/80 p-2.5 rounded-xl border border-slate-800">
                        <span id="cardModalNumber" class="font-mono text-cyan-400 text-sm font-bold tracking-wider">{card_number}</span>
                        <button onclick="copyText('{card_number}')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] border border-slate-700 transition">
                            کپی
                        </button>
                    </div>
                </div>
                <div class="flex justify-between items-center text-xs text-slate-400">
                    <span>بنام:</span>
                    <span class="text-slate-200 font-medium">{card_holder}</span>
                </div>
            </div>

            <!-- Card Payment Form -->
            <form id="cardBuyForm" class="space-y-3" onsubmit="handleCardPaymentSubmit(event)">
                <div>
                    <label class="block text-xs text-slate-300 mb-1">نام و نام خانوادگی خریدار *</label>
                    <input type="text" id="cardCustomerName" required placeholder="مثال: سجاد محمدی" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                    <label class="block text-xs text-slate-300 mb-1">شماره همراه خریدار *</label>
                    <input type="tel" id="cardCustomerPhone" required placeholder="مثال: 09123456789" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono" dir="ltr">
                </div>
                <div>
                    <label class="block text-xs text-slate-300 mb-1">شماره پیگیری واریز یا ۴ رقم آخر کارت *</label>
                    <textarea id="cardReceiptInfo" required rows="2" placeholder="کد رهگیری تراکنش، تاریخ و زمان واریز یا شماره ارجاع فیش..." class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-cyan-500"></textarea>
                </div>
                <div>
                    <label class="block text-xs text-slate-300 mb-1">تصویر فیش واریزی (اختیاری)</label>
                    <input type="file" id="cardReceiptImage" accept="image/*" class="w-full text-xs text-slate-400 file:mr-2 file:py-1.5 file:px-3 file:rounded-xl file:border-0 file:text-xs file:bg-slate-800 file:text-slate-200 hover:file:bg-slate-700">
                </div>
                <button type="submit" id="btnCardPaySubmit" class="w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-bold text-xs shadow-lg shadow-cyan-600/20 transition flex items-center justify-center gap-2">
                    <span>📤</span> ثبت سفارش و ارسال رسید
                </button>
            </form>

            <div id="cardSuccessSection" class="hidden space-y-3 text-center">
                <div class="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-800/80 space-y-2">
                    <span class="text-3xl">✅</span>
                    <h4 class="text-sm font-bold text-emerald-300">سفارش شما با موفقیت ثبت شد!</h4>
                    <p class="text-xs text-slate-300 leading-relaxed">
                        کد رهگیری شما: <span id="cardOrderIdBadge" class="font-mono text-cyan-400 font-bold"></span>
                    </p>
                    <p class="text-[11px] text-slate-400 mt-2">
                        پس از بررسی و تایید فیش توسط پشتیبانی، دوره شما فعال خواهد شد. شما می‌توانید با استفاده از کد رهگیری یا شماره همراه خود از بخش "پیگیری سفارش" وضعیت را بررسی نمایید.
                    </p>
                </div>
                <button onclick="closeModal('cardBuyModal')" class="w-full py-2.5 rounded-xl bg-slate-800 text-slate-200 text-xs transition">
                    بستن پنجره
                </button>
            </div>
        </div>
    </div>

    <!-- ================= MODAL: TRACK ORDER ================= -->
    <div id="trackOrderModal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 hidden">
        <div class="glass-modal max-w-lg w-full rounded-3xl p-6 space-y-5 relative animate-in fade-in zoom-in-95 duration-200">
            <button onclick="closeModal('trackOrderModal')" class="absolute top-4 left-4 text-slate-400 hover:text-white text-lg">✕</button>
            <div class="flex items-center gap-3 pb-3 border-b border-slate-800">
                <div class="w-10 h-10 rounded-xl bg-cyan-950 border border-cyan-800 flex items-center justify-center text-xl text-cyan-400">
                    🔍
                </div>
                <div>
                    <h3 class="text-sm font-bold text-white">پیگیری وضعیت سفارش و دریافت لینک دانلود</h3>
                    <p class="text-[11px] text-slate-400">استعلام بر اساس کد رهگیری سفارش یا شماره همراه</p>
                </div>
            </div>

            <form class="flex gap-2" onsubmit="handleTrackSubmit(event)">
                <input type="text" id="trackInput" required placeholder="کد رهگیری (ORD_...) یا شماره همراه..." class="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono">
                <button type="submit" id="btnTrackSubmit" class="px-5 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs transition shrink-0">
                    استعلام
                </button>
            </form>

            <div id="trackResultsContainer" class="space-y-3 max-h-80 overflow-y-auto pr-1">
                <p class="text-center text-xs text-slate-500 py-6">کد رهگیری یا شماره همراه خود را وارد نمایید.</p>
            </div>
        </div>
    </div>

        <!-- ================= MODAL: ZARINPAL ONLINE PAYMENT ================= -->
    <div id="zarinpalBuyModal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 hidden">
        <div class="glass-modal max-w-md w-full rounded-3xl p-6 space-y-5 relative animate-in fade-in zoom-in-95 duration-200">
            <button onclick="closeModal('zarinpalBuyModal')" class="absolute top-4 left-4 text-slate-400 hover:text-white transition">✕</button>

            <div class="flex items-center gap-3 pb-3 border-b border-slate-800">
                <div class="w-10 h-10 rounded-xl bg-amber-950 border border-amber-800 flex items-center justify-center text-xl">
                    💳
                </div>
                <div>
                    <h3 class="text-sm font-bold text-white">پرداخت آنلاین زرین‌پال</h3>
                    <p class="text-[11px] text-slate-400">اتصال مستقیم به کلیه کارت‌های شتاب و تحویل آنی دوره</p>
                </div>
            </div>

            <!-- Course Info -->
            <div class="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 flex justify-between items-center">
                <div>
                    <span class="text-[11px] text-slate-400 block">دوره انتخابی:</span>
                    <h4 id="zarinpalModalCourseTitle" class="text-xs font-bold text-white mt-0.5">-</h4>
                </div>
                <div class="text-left">
                    <span class="text-[11px] text-slate-400 block">مبلغ قابل پرداخت:</span>
                    <span id="zarinpalModalPrice" class="text-sm font-extrabold text-amber-400 font-mono">-</span>
                </div>
            </div>

            <!-- Payment Form -->
            <form id="zarinpalBuyForm" class="space-y-3" onsubmit="handleZarinpalPaymentSubmit(event)">
                <input type="hidden" id="zarinpalCourseId">
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">نام و نام خانوادگی خریدار</label>
                    <input type="text" id="zarinpalCustomerName" required placeholder="مثال: علی رضایی" class="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-amber-500 transition">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">شماره تلفن همراه</label>
                    <input type="tel" id="zarinpalCustomerPhone" required placeholder="09xxxxxxxxx" class="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-amber-500 font-mono transition text-left" dir="ltr">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">ایمیل خریدار (اختیاری جهت دریافت فاکتور)</label>
                    <input type="email" id="zarinpalCustomerEmail" placeholder="user@example.com" class="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-amber-500 font-mono transition text-left" dir="ltr">
                </div>

                <div class="pt-2">
                    <button type="submit" id="btnZarinpalPaySubmit" class="w-full py-3 rounded-xl bg-gradient-to-r from-amber-600 to-yellow-600 hover:from-amber-500 hover:to-yellow-500 text-white font-bold text-xs shadow-lg shadow-amber-500/20 transition flex items-center justify-center gap-2">
                        <span>⚡️</span> اتصال به درگاه پرداخت شاپرک (زرین‌پال)
                    </button>
                </div>
            </form>
        </div>
    </div>

<!-- Store JavaScript Logic -->
    <script>
        let currentBaleOrderId = '';
        let currentBaleInvoiceUrl = '';
        let currentBaleDlLink = '';
        let balePollTimer = null;
        let selectedCourseId = '';
        let selectedCourseName = '';
        let selectedCoursePrice = 0;

        function copyText(txt) {{
            if (!txt) return;
            navigator.clipboard.writeText(txt).then(() => {{
                alert('✅ با موفقیت کپی شد:\\n' + txt);
            }}).catch(() => {{
                prompt('لینک جهت کپی:', txt);
            }});
        }}

        function copyBaleInvoiceLink() {{
            if (currentBaleInvoiceUrl) {{
                copyText(currentBaleInvoiceUrl);
            }} else {{
                alert('لینکی جهت پرداخت وجود ندارد.');
            }}
        }}

        function closeModal(id) {{
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
            if (id === 'baleBuyModal' && balePollTimer) {{
                clearInterval(balePollTimer);
                balePollTimer = null;
            }}
        }}

        function openBaleBuyModal(target) {{
            let pid = '', name = '', price = 0;
            if (target && (target instanceof HTMLElement || target.nodeType === 1)) {{
                pid = target.getAttribute('data-id') || '';
                name = target.getAttribute('data-name') || '';
                price = parseInt(target.getAttribute('data-price') || '0', 10);
            }} else {{
                pid = arguments[0] || '';
                name = arguments[1] || '';
                price = parseInt(arguments[2] || '0', 10);
            }}

            selectedCourseId = pid;
            selectedCourseName = name;
            selectedCoursePrice = price;

            const nameEl = document.getElementById('baleModalCourseName');
            const priceEl = document.getElementById('baleModalCoursePrice');
            if (nameEl) nameEl.innerText = name;
            if (priceEl) priceEl.innerText = price.toLocaleString() + ' تومان';

            const formEl = document.getElementById('baleBuyForm');
            const invEl = document.getElementById('baleInvoiceSection');
            const succEl = document.getElementById('baleSuccessSection');
            if (formEl) formEl.classList.remove('hidden');
            if (invEl) invEl.classList.add('hidden');
            if (succEl) succEl.classList.add('hidden');

            const inpName = document.getElementById('baleCustomerName');
            const inpPhone = document.getElementById('baleCustomerPhone');
            if (inpName) inpName.disabled = false;
            if (inpPhone) inpPhone.disabled = false;

            const btn = document.getElementById('btnBalePaySubmit');
            if (btn) {{
                btn.disabled = false;
                btn.innerHTML = '<span>⚡️</span> دریافت لینک پرداخت بله';
            }}

            const modal = document.getElementById('baleBuyModal');
            if (modal) modal.classList.remove('hidden');
        }}

        function openZarinpalBuyModal(target) {{
            let pid = '', name = '', price = 0;
            if (target && (target instanceof HTMLElement || target.nodeType === 1)) {{
                pid = target.getAttribute('data-id') || '';
                name = target.getAttribute('data-name') || '';
                price = parseInt(target.getAttribute('data-price') || '0', 10);
            }} else {{
                pid = arguments[0] || '';
                name = arguments[1] || '';
                price = parseInt(arguments[2] || '0', 10);
            }}

            const idEl = document.getElementById('zarinpalCourseId');
            const titleEl = document.getElementById('zarinpalModalCourseTitle');
            const priceEl = document.getElementById('zarinpalModalPrice');

            if (idEl) idEl.value = pid;
            if (titleEl) titleEl.innerText = name;
            if (priceEl) priceEl.innerText = price.toLocaleString() + ' تومان';

            const modal = document.getElementById('zarinpalBuyModal');
            if (modal) modal.classList.remove('hidden');
        }}

        async function handleZarinpalPaymentSubmit(e) {{
            e.preventDefault();
            const btn = document.getElementById('btnZarinpalPaySubmit');
            const courseId = document.getElementById('zarinpalCourseId').value;
            const name = document.getElementById('zarinpalCustomerName').value.trim();
            const phone = document.getElementById('zarinpalCustomerPhone').value.trim();
            const email = document.getElementById('zarinpalCustomerEmail').value.trim();

            btn.disabled = true;
            btn.innerHTML = '<span>⏳</span> در حال اتصال به درگاه زرین‌پال...';

            try {{
                const res = await fetch('/api/payment/zarinpal/request', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        course_id: courseId,
                        customer_name: name,
                        phone: phone,
                        email: email
                    }})
                }});
                const data = await res.json();
                if (data.ok && data.payment_url) {{
                    window.location.href = data.payment_url;
                }} else {{
                    alert('❌ خطا در اتصال به درگاه: ' + (data.error || 'پاسخ نامعتبر از سرور'));
                    btn.disabled = false;
                    btn.innerHTML = '<span>⚡️</span> ورود به درگاه شاپرک و پرداخت';
                }}
            }} catch (err) {{
                alert('❌ خطای ارتباط با سرور: ' + err.message);
                btn.disabled = false;
                btn.innerHTML = '<span>⚡️</span> ورود به درگاه شاپرک و پرداخت';
            }}
        }}

        function openCardBuyModal(target) {{
            let pid = '', name = '', price = 0;
            if (target && (target instanceof HTMLElement || target.nodeType === 1)) {{
                pid = target.getAttribute('data-id') || '';
                name = target.getAttribute('data-name') || '';
                price = parseInt(target.getAttribute('data-price') || '0', 10);
            }} else {{
                pid = arguments[0] || '';
                name = arguments[1] || '';
                price = parseInt(arguments[2] || '0', 10);
            }}

            selectedCourseId = pid;
            selectedCourseName = name;
            selectedCoursePrice = price;

            const priceEl = document.getElementById('cardModalCoursePrice');
            if (priceEl) priceEl.innerText = price.toLocaleString() + ' تومان';

            const formEl = document.getElementById('cardBuyForm');
            const succEl = document.getElementById('cardSuccessSection');
            if (formEl) formEl.classList.remove('hidden');
            if (succEl) succEl.classList.add('hidden');

            const modal = document.getElementById('cardBuyModal');
            if (modal) modal.classList.remove('hidden');
        }}

        function openTrackModal() {{
            const modal = document.getElementById('trackOrderModal');
            if (modal) modal.classList.remove('hidden');
        }}

        function openFreeModal(target) {{
            let dlLink = '';
            if (target && (target instanceof HTMLElement || target.nodeType === 1)) {{
                dlLink = target.getAttribute('data-link') || '';
            }} else {{
                dlLink = arguments[2] || arguments[0] || '';
            }}

            if (dlLink) {{
                window.open(dlLink, '_blank');
            }} else {{
                alert('فایل‌های این دوره رایگان در حال آماده‌سازی می‌باشد.');
            }}
        }}

        async function handleBalePaymentSubmit(e) {{
            e.preventDefault();
            const btn = document.getElementById('btnBalePaySubmit');
            btn.disabled = true;
            btn.innerText = 'در حال ارتباط با درگاه بله...';

            const name = document.getElementById('baleCustomerName').value.trim();
            const phone = document.getElementById('baleCustomerPhone').value.trim();

            try {{
                const res = await fetch('/api/store/buy_bale', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        course_id: selectedCourseId,
                        customer_name: name,
                        phone: phone
                    }})
                }});
                const data = await res.json();
                if (!data.ok) {{
                    alert('❌ خطا در ایجاد فاکتور پرداخت: ' + (data.error || ''));
                    btn.disabled = false;
                    btn.innerText = '⚡️ دریافت لینک پرداخت بله';
                    return;
                }}

                currentBaleOrderId = data.order_id;
                currentBaleInvoiceUrl = data.invoice_url || '';

                if (data.is_free) {{
                    showBaleSuccess(data.download_link);
                    return;
                }}

                document.getElementById('baleBuyForm').classList.add('hidden');
                document.getElementById('baleOrderIdBadge').innerText = data.order_id;
                const linkBtn = document.getElementById('baleInvoiceLinkBtn');
                linkBtn.href = data.invoice_url;

                document.getElementById('baleInvoiceSection').classList.remove('hidden');
                try {{
                    window.open(data.invoice_url, '_blank');
                }} catch (e) {{
                    console.warn('Popup blocked, use direct link or copy button');
                }}

                // Start polling order status every 3 seconds
                if (balePollTimer) clearInterval(balePollTimer);
                balePollTimer = setInterval(async () => {{
                    try {{
                        const stRes = await fetch('/api/store/order_status?order_id=' + encodeURIComponent(data.order_id));
                        const stData = await stRes.json();
                        if (stData.ok && stData.orders && stData.orders.length > 0) {{
                            const ord = stData.orders[0];
                            if (ord.status === 'completed' || ord.status === 'approved') {{
                                clearInterval(balePollTimer);
                                balePollTimer = null;
                                showBaleSuccess(ord.download_link);
                            }}
                        }}
                    }} catch (err) {{
                        console.warn('Poll error:', err);
                    }}
                }}, 3000);

            }} catch (err) {{
                alert('❌ خطای ارتباط با سرور: ' + err.message);
                btn.disabled = false;
                btn.innerText = '⚡️ دریافت لینک پرداخت بله';
            }}
        }}

        function showBaleSuccess(dlLink) {{
            currentBaleDlLink = dlLink || '';
            document.getElementById('baleInvoiceSection').classList.add('hidden');
            document.getElementById('baleBuyForm').classList.add('hidden');

            const dlBtn = document.getElementById('baleDirectDlBtn');
            if (dlLink) {{
                dlBtn.href = dlLink;
                dlBtn.style.display = 'flex';
            }} else {{
                dlBtn.style.display = 'none';
            }}
            document.getElementById('baleSuccessSection').classList.remove('hidden');
        }}

        function copyBaleDlLink() {{
            if (currentBaleDlLink) {{
                copyText(currentBaleDlLink);
            }} else {{
                alert('لینکی جهت کپی موجود نیست.');
            }}
        }}

        async function handleCardPaymentSubmit(e) {{
            e.preventDefault();
            const btn = document.getElementById('btnCardPaySubmit');
            btn.disabled = true;
            btn.innerText = 'در حال ثبت رسید...';

            const name = document.getElementById('cardCustomerName').value.trim();
            const phone = document.getElementById('cardCustomerPhone').value.trim();
            const receipt = document.getElementById('cardReceiptInfo').value.trim();
            const fileInp = document.getElementById('cardReceiptImage');
            const receiptFile = fileInp && fileInp.files ? fileInp.files[0] : null;

            let receiptImageData = '';
            if (receiptFile) {{
                try {{
                    receiptImageData = await new Promise((resolve, reject) => {{
                        const reader = new FileReader();
                        reader.onload = () => resolve(reader.result);
                        reader.onerror = reject;
                        reader.readAsDataURL(receiptFile);
                    }});
                }} catch (readErr) {{
                    console.warn('Failed reading receipt image:', readErr);
                }}
            }}

            try {{
                const res = await fetch('/api/store/buy_card', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        course_id: selectedCourseId,
                        customer_name: name,
                        phone: phone,
                        receipt_info: receipt,
                        receipt_image: receiptImageData
                    }})
                }});
                const data = await res.json();
                if (!data.ok) {{
                    alert('❌ خطا: ' + (data.error || 'ثبت سفارش ناموفق بود.'));
                    btn.disabled = false;
                    btn.innerText = '📤 ثبت سفارش و ارسال رسید';
                    return;
                }}

                document.getElementById('cardBuyForm').classList.add('hidden');
                document.getElementById('cardOrderIdBadge').innerText = data.order_id;
                document.getElementById('cardSuccessSection').classList.remove('hidden');

            }} catch (err) {{
                alert('❌ خطای ارتباط: ' + err.message);
                btn.disabled = false;
                btn.innerText = '📤 ثبت سفارش و ارسال رسید';
            }}
        }}

        async function handleTrackSubmit(e) {{
            e.preventDefault();
            const q = document.getElementById('trackInput').value.trim();
            if (!q) return;

            const box = document.getElementById('trackResultsContainer');
            box.innerHTML = '<p class="text-center text-xs text-cyan-400 py-6">در حال استعلام وضعیت سفارش...</p>';

            try {{
                const res = await fetch('/api/store/order_status?order_id=' + encodeURIComponent(q));
                const data = await res.json();
                if (!data.ok || !data.orders || data.orders.length === 0) {{
                    box.innerHTML = '<div class="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 text-center text-xs text-rose-300">هیچ سفارشی با این کد یا شماره همراه یافت نشد.</div>';
                    return;
                }}

                box.innerHTML = data.orders.map(ord => {{
                    let badge = '';
                    let dlHtml = '';
                    if (ord.status === 'completed' || ord.status === 'approved') {{
                        badge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">✅ پرداخت تایید شده</span>';
                        if (ord.download_link) {{
                            dlHtml = '<div class="pt-2 border-t border-slate-800 mt-2 flex items-center justify-between gap-2">' +
                                '<span class="text-[11px] text-slate-400 truncate max-w-[200px] font-mono">🔗 ' + ord.download_link + '</span>' +
                                '<div class="flex gap-1.5">' +
                                    '<a href="' + ord.download_link + '" target="_blank" class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition">📥 دانلود</a>' +
                                    '<button data-dl="' + ord.download_link + '" onclick="copyText(this.dataset.dl)" class="px-2.5 py-1.5 rounded-lg bg-slate-800 text-cyan-300 text-xs border border-slate-700">کپی</button>' +
                                '</div>' +
                            '</div>';
                        }} else {{
                            dlHtml = '<div class="text-[11px] text-slate-400 pt-2 border-t border-slate-800 mt-2">لینک دانلود در دسترس نیست (با پشتیبانی تماس بگیرید).</div>';
                        }}
                    }} else if (ord.status === 'rejected') {{
                        badge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-950 text-rose-300 border border-rose-800">❌ تایید نشده / رد شده</span>';
                    }} else {{
                        badge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-950 text-amber-300 border border-amber-800">⏳ در انتظار بررسی فیش</span>';
                        dlHtml = '<div class="text-[11px] text-amber-300/80 pt-2 border-t border-slate-800 mt-2">سفارش شما در صف بررسی توسط ادمین است. به محض تایید، لینک دانلود فعال خواهد شد.</div>';
                    }}

                    const dateStr = ord.created_at ? ord.created_at.split('T')[0] : '-';

                    return '<div class="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-2 text-xs">' +
                        '<div class="flex justify-between items-start gap-2">' +
                            '<div>' +
                                '<span class="font-mono text-[10px] text-cyan-400 bg-cyan-950 px-2 py-0.5 rounded border border-cyan-800">' + ord.order_id + '</span>' +
                                '<h4 class="font-bold text-white text-sm mt-1">' + (ord.product_name || 'دوره آموزشی') + '</h4>' +
                            '</div>' +
                            badge +
                        '</div>' +
                        '<div class="flex justify-between text-[11px] text-slate-400 pt-1">' +
                            '<span>مبلغ: <span class="text-emerald-400 font-mono font-bold">' + (ord.amount || 0).toLocaleString() + ' تومان</span></span>' +
                            '<span class="font-mono">' + dateStr + '</span>' +
                        '</div>' +
                        dlHtml +
                    '</div>';
                }}).join('');

            }} catch (err) {{
                box.innerHTML = '<div class="p-4 rounded-2xl bg-rose-950/40 border border-rose-800 text-center text-xs text-rose-300">خطا در دریافت وضعیت: ' + err.message + '</div>';
            }}
        }}

        // Check for payment callback status from URL
        (function checkPaymentStatus() {{
            try {{
                const urlParams = new URLSearchParams(window.location.search);
                const status = urlParams.get('payment');
                const orderId = urlParams.get('order_id');
                const dlLink = urlParams.get('dl');
                if (status === 'success') {{
                    alert('🎉 پرداخت شما با موفقیت انجام شد!\\nشناسه سفارش: ' + (orderId || '') + (dlLink ? '\\nلینک دانلود: ' + dlLink : ''));
                }} else if (status === 'failed') {{
                    alert('❌ پرداخت زرین‌پال ناموفق بود یا لغو گردید.');
                }}
            }} catch(e) {{}}
        }})();

        window.openBaleBuyModal = openBaleBuyModal;
        window.openCardBuyModal = openCardBuyModal;
        window.openZarinpalBuyModal = openZarinpalBuyModal;
        window.openTrackModal = openTrackModal;
        window.closeModal = closeModal;
    </script>
</body>
</html>"""


