import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from core.config import config
from core.logger import get_logger

logger = get_logger("frequency_service")

DEFAULT_FREQUENCIES: List[Dict[str, Any]] = [
    {"id": "freq_m_01", "category": "MORNING", "title": "مغناطیس ثروت", "text": "من آهنربای جذب ثروت و فراوانی هستم.", "order": 1},
    {"id": "freq_m_02", "category": "MORNING", "title": "روز برکت", "text": "امروز روز بی‌نظیری برای دریافت برکت و رحمت الهی است.", "order": 2},
    {"id": "freq_m_03", "category": "MORNING", "title": "ایده‌های طلایی", "text": "ذهن من سرشار از ایده‌های ثروت‌ساز و خلاقانه است.", "order": 3},
    {"id": "freq_m_04", "category": "MORNING", "title": "جریان بی‌پایان", "text": "هر روز دریچه‌های جدیدی از ثروت بی‌پایان به روی من گشوده می‌شود.", "order": 4},
    {"id": "freq_m_05", "category": "MORNING", "title": "احساس ارزشمندی", "text": "من لایق بهترین‌ها، ثروتمندترین‌ها و زیباترین‌های جهان هستم.", "order": 5},
    {"id": "freq_m_06", "category": "MORNING", "title": "جهان همسو", "text": "جهان هستی همواره در جهت توانگری و سعادت من حرکت می‌کند.", "order": 6},
    {"id": "freq_m_07", "category": "MORNING", "title": "جذب آسان", "text": "پول و ثروت به راحتی و از راه‌های حلال و عالی به زندگی من جریان دارد.", "order": 7},
    {"id": "freq_m_08", "category": "MORNING", "title": "تنظیم فرکانس", "text": "فرکانس من امروز روی بالاترین فرکانس جذب ثروت تنظیم شده است.", "order": 8},
    {"id": "freq_m_09", "category": "MORNING", "title": "نفس فراوانی", "text": "با هر نفس، عشق، آرامش و فراوانی بیشتری جذب می‌کنم.", "order": 9},
    {"id": "freq_m_10", "category": "MORNING", "title": "سرچشمه الهی", "text": "خدای من سرچشمه تمام دارایی‌ها و توانگری‌های من است.", "order": 10},
    {"id": "freq_n_01", "category": "NIGHT", "title": "خواب آرام", "text": "من با آرامش می‌خوابم و ایمان دارم فردا با فراوانی بیشتری بیدار می‌شوم.", "order": 1},
    {"id": "freq_n_02", "category": "NIGHT", "title": "فرکانس سلولی", "text": "تمام سلول‌های بدن من در حال جذب فرکانس ثروت و سلامتی هستند.", "order": 2},
    {"id": "freq_n_03", "category": "NIGHT", "title": "سپاسگزاری شبانه", "text": "خدایا سپاسگزارم که امشب را با آرامش و احساس توانگری به پایان می‌رسانم.", "order": 3},
    {"id": "freq_n_04", "category": "NIGHT", "title": "خلق در خواب", "text": "در خواب من، ذهن ناخودآگاهم ایده‌های طلایی ثروت را خلق می‌کند.", "order": 4},
    {"id": "freq_n_05", "category": "NIGHT", "title": "تسلیم الهی", "text": "من خود را به جریان بیکران ثروت و آرامش الهی می‌سپارم.", "order": 5},
    {"id": "freq_n_06", "category": "NIGHT", "title": "بخشش و برکت", "text": "با عشق و بخشش امشب را سپری می‌کنم تا ظرف وجودم از برکت پر شود.", "order": 6},
    {"id": "freq_n_07", "category": "NIGHT", "title": "آمادگی نعمت", "text": "هر آنچه که برای خوشبختی و ثروت من نیاز است در حال آماده شدن است.", "order": 7},
    {"id": "freq_n_08", "category": "NIGHT", "title": "آرامش نعمت‌ساز", "text": "آرامش من در خواب، فرکانس جذب نعمت‌های فرداست.", "order": 8},
    {"id": "freq_n_09", "category": "NIGHT", "title": "امنیت پایدار", "text": "خدایا شکرت که امنیت و ثروت پایدار را به زندگی من هدیه دادی.", "order": 9},
    {"id": "freq_n_10", "category": "NIGHT", "title": "در پناه حق", "text": "من ثروتمندم، من توانمندم، من در پناه خدای فراوانی‌ها هستم.", "order": 10}
]

class FrequencyService:
    """
    Independent service for managing Frequency of Abundance (فرکانس فراوانی) cards.
    Completely isolated from commercial courses and orders.
    Persisted in data/frequencies.json.
    """
    _file_path: Path = config.DATA_DIR / "frequencies.json"

    @classmethod
    def _ensure_data_file(cls) -> Path:
        cls._file_path.parent.mkdir(parents=True, exist_ok=True)
        if not cls._file_path.exists() or cls._file_path.stat().st_size == 0:
            try:
                with open(cls._file_path, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_FREQUENCIES, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"[frequency_service] Failed to write default frequencies: {e}")
        return cls._file_path

    @classmethod
    def get_all(cls) -> List[Dict[str, Any]]:
        cls._ensure_data_file()
        try:
            with open(cls._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.error(f"[frequency_service] Error reading frequencies: {e}")
        return list(DEFAULT_FREQUENCIES)

    @classmethod
    def save_all(cls, items: List[Dict[str, Any]]) -> bool:
        cls._file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(cls._file_path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"[frequency_service] Error saving frequencies: {e}")
            return False

    @classmethod
    def get_by_category(cls, category: str) -> List[Dict[str, Any]]:
        cat_norm = (category or "").strip().upper()
        all_items = cls.get_all()
        filtered = [item for item in all_items if item.get("category", "").upper() == cat_norm]
        filtered.sort(key=lambda x: x.get("order", 999))
        return filtered

    @classmethod
    def get_by_id(cls, item_id: str) -> Optional[Dict[str, Any]]:
        all_items = cls.get_all()
        for it in all_items:
            if it.get("id") == item_id:
                return it
        return None

    @classmethod
    def get_item(cls, category: str, index: int) -> Tuple[Optional[Dict[str, Any]], int, int]:
        """
        Returns (item, current_1_based_index, total_count).
        Wraps around or clamps cleanly.
        """
        items = cls.get_by_category(category)
        total = len(items)
        if total == 0:
            return None, 0, 0
        norm_idx = index % total
        return items[norm_idx], norm_idx + 1, total

    @classmethod
    def add_item(cls, title: str, text: str, category: str) -> Dict[str, Any]:
        cat_norm = "NIGHT" if "NIGHT" in category.upper() or "شب" in category else "MORNING"
        all_items = cls.get_all()
        cat_items = [i for i in all_items if i.get("category", "").upper() == cat_norm]
        next_order = len(cat_items) + 1
        new_id = f"freq_{cat_norm.lower()[:1]}_{uuid.uuid4().hex[:4]}"
        new_item = {
            "id": new_id,
            "category": cat_norm,
            "title": title.strip(),
            "text": text.strip(),
            "order": next_order
        }
        all_items.append(new_item)
        cls.save_all(all_items)
        logger.info(f"[frequency_service] Added new frequency item {new_id} in {cat_norm}")
        return new_item

    @classmethod
    def delete_item(cls, item_id: str) -> bool:
        all_items = cls.get_all()
        initial_len = len(all_items)
        all_items = [i for i in all_items if str(i.get("id")) != str(item_id)]
        if len(all_items) < initial_len:
            cls.save_all(all_items)
            logger.info(f"[frequency_service] Deleted frequency item {item_id}")
            return True
        return False

    @classmethod
    def import_items(cls, incoming_items: List[Dict[str, Any]], mode: str = "replace") -> Tuple[bool, int, str]:
        """
        Imports frequency items. If mode == 'replace', completely rewrites the list.
        If mode == 'merge', appends new ones without duplicate texts.
        """
        if not isinstance(incoming_items, list):
            return False, 0, "داده ارسالی باید به صورت لیست JSON باشد."

        valid_list = []
        for idx, it in enumerate(incoming_items):
            if not isinstance(it, dict):
                continue
            title = str(it.get("title", "")).strip()
            text = str(it.get("text", "")).strip()
            if not title or not text:
                continue
            cat_raw = str(it.get("category", "")).upper()
            cat = "NIGHT" if "NIGHT" in cat_raw or "شب" in cat_raw else "MORNING"
            item_id = str(it.get("id") or f"freq_{cat.lower()[:1]}_{uuid.uuid4().hex[:4]}")
            order = int(it.get("order") or (idx + 1))
            valid_list.append({
                "id": item_id,
                "category": cat,
                "title": title,
                "text": text,
                "order": order
            })

        if not valid_list:
            return False, 0, "هیچ باور معتبری در فایل یافت نشد."

        if mode == "replace":
            cls.save_all(valid_list)
            logger.info(f"[frequency_service] Replaced frequencies with {len(valid_list)} items")
            return True, len(valid_list), f"{len(valid_list)} باور با موفقیت جایگزین گردید."
        else:
            current = cls.get_all()
            curr_texts = {c.get("text", "").strip() for c in current}
            added = 0
            for v in valid_list:
                if v["text"] not in curr_texts:
                    current.append(v)
                    curr_texts.add(v["text"])
                    added += 1
            cls.save_all(current)
            logger.info(f"[frequency_service] Merged {added} new frequencies (Total: {len(current)})")
            return True, added, f"{added} باور جدید به سامانه اضافه گردید."

    @classmethod
    def format_card(cls, item: Dict[str, Any], index: int, total: int) -> str:
        cat = item.get("category", "").upper()
        if cat == "MORNING":
            header = "☀️ *باور صبحگاهی*"
        else:
            header = "🌙 *باور شبانگاهی*"

        title = item.get("title", "").strip()
        text = item.get("text", "").strip()

        return (
            f"💎 *فرکانس فراوانی* | {header}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✨ *{title}*\n\n"
            f"«{text}»\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📄 *کارت {index} از {total}*"
        )
