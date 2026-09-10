import json
import os
import uuid
import re
import html
from pathlib import Path
from datetime import datetime, timezone, timedelta

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def get_tehran_now_str() -> str:
    return datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")
from typing import List, Optional, Dict, Any, Tuple
from core.database import execute_query, fetch_one, fetch_all, get_system_setting
from core.config import config
from core.logger import get_logger

logger = get_logger("store")

class ProductItem:
    def __init__(self, d: dict):
        self.id = d.get("id")
        self.product_id = d.get("product_id", "")
        self.name = d.get("name", "")
        self.price = int(d.get("price", 0) or 0)
        self.description = d.get("description", "")
        self.photo_file_id = d.get("photo_file_id")
        self.bale_photo_file_id = str(d.get("bale_photo_file_id") or "")
        self.photo_url = str(d.get("photo_url") or "")
        self.digital_file_id = d.get("digital_file_id")
        self.download_link = str(d.get("download_link") or "")
        self.digital_file_type = d.get("digital_file_type", "audio")
        self.active = bool(d.get("active", 1))
        self.allow_card = bool(d.get("allow_card", 1))
        self.allow_bale = bool(d.get("allow_bale", 1))
        self.payment_type = d.get("payment_type", "paid")

class OrderItem:
    def __init__(self, d: dict):
        self.id = d.get("id")
        self.order_id = d.get("order_id", "")
        self.user_id = str(d.get("user_id", ""))
        self.username = d.get("username", "")
        self.customer_name = d.get("customer_name", "")
        self.phone = d.get("phone", "")
        self.product_id = d.get("product_id", "")
        self.product_name = d.get("product_name", "")
        self.amount = int(d.get("amount") or d.get("total", 0) or 0)
        self.total = self.amount
        self.wallet_used = int(d.get("wallet_used", 0) or 0)
        self.receipt_file_id = d.get("receipt_file_id")
        self.receipt_text = d.get("receipt_text", "")
        self.payment_method = d.get("payment_method", "telegram")
        self.status = d.get("status", "pending")
        self.platform = d.get("platform", "telegram")
        self.created_at = d.get("created_at", "")
        self.download_link = d.get("download_link", "")

class CustomerItem:
    def __init__(self, d: dict):
        self.id = d.get("id")
        self.user_id = str(d.get("user_id", ""))
        self.customer_name = d.get("customer_name", "")
        self.phone = d.get("phone", "")
        self.terms_accepted = bool(d.get("terms_accepted", 0))
        self.wallet_balance = int(d.get("wallet_balance", 0) or 0)
        self.platform = d.get("platform", "telegram")

class TicketItem:
    def __init__(self, d: dict):
        self.id = d.get("id")
        self.ticket_id = d.get("ticket_id", "")
        self.user_id = str(d.get("user_id", ""))
        self.username = d.get("username", "")
        self.message_text = d.get("message_text", "")
        self.status = d.get("status", "open")
        self.platform = d.get("platform", "telegram")

class StoreService:
    @staticmethod
    async def get_products(is_free_only: bool = False) -> List[ProductItem]:
        if is_free_only:
            sql = "SELECT * FROM products WHERE active = 1 AND price = 0 ORDER BY id ASC"
        else:
            sql = "SELECT * FROM products WHERE active = 1 AND price > 0 ORDER BY id ASC"
        rows = await fetch_all(sql)
        return [ProductItem(r) for r in rows]

    @staticmethod
    async def get_all_products(active_only: bool = False, only_active: Optional[bool] = None) -> List[ProductItem]:
        if only_active is not None:
            active_only = only_active
        if active_only:
            sql = "SELECT * FROM products WHERE active = 1 ORDER BY id ASC"
        else:
            sql = "SELECT * FROM products ORDER BY id ASC"
        rows = await fetch_all(sql)
        return [ProductItem(r) for r in rows]

    @staticmethod
    async def get_product(product_id: str) -> Optional[ProductItem]:
        sql = "SELECT * FROM products WHERE product_id = ?"
        row = await fetch_one(sql, (product_id,))
        return ProductItem(row) if row else None

    @staticmethod
    async def backup_products_to_disk() -> None:
        if os.getenv("TESTING") == "true" or os.getenv("PYTEST_CURRENT_TEST"):
            return
        try:
            sql = "SELECT * FROM products WHERE active = 1 ORDER BY id ASC"
            rows = await fetch_all(sql)
            data = []
            for r in rows:
                data.append({
                    "product_id": r.get("product_id", ""),
                    "name": r.get("name", ""),
                    "price": int(r.get("price", 0) or 0),
                    "description": r.get("description", ""),
                    "photo_file_id": r.get("photo_file_id"),
                    "photo_url": r.get("photo_url", ""),
                    "digital_file_id": r.get("digital_file_id"),
                    "download_link": r.get("download_link", ""),
                    "digital_file_type": r.get("digital_file_type", "audio"),
                    "active": int(r.get("active", 1)),
                    "allow_card": int(r.get("allow_card", 1)),
                    "allow_bale": int(r.get("allow_bale", 1)),
                    "payment_type": r.get("payment_type", "paid"),
                    "created_at": r.get("created_at", "")
                })
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            for target_file in (config.COURSES_JSON_FILE, config.DATA_DIR / "courses_backup.json"):
                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[store_backup] Successfully persisted {len(data)} active courses to disk JSON")
        except Exception as e:
            logger.error(f"[store_backup] Failed to backup courses: {e}")

    @staticmethod
    async def update_product_field(product_id: str, field: str, value: Any) -> bool:
        allowed = {
            "name", "price", "description", "photo_file_id", "bale_photo_file_id", "digital_file_id",
            "active", "download_link", "photo_url", "allow_card", "allow_bale"
        }
        if field not in allowed:
            return False
        sql = f"UPDATE products SET {field} = ? WHERE product_id = ?"
        await execute_query(sql, (value, product_id))
        await StoreService.backup_products_to_disk()
        return True

    @staticmethod
    async def add_product(
        name: str,
        price: int,
        description: str = "",
        download_link: str = "",
        photo_url: str = "",
        allow_card: bool = True,
        allow_bale: bool = True
    ) -> ProductItem:
        pid = "prod_" + uuid.uuid4().hex[:6]
        now_str = get_tehran_now_str()
        ptype = "free" if price == 0 else "paid"
        await execute_query(
            """INSERT INTO products (
                product_id, name, price, description, download_link, photo_url,
                allow_card, allow_bale, payment_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pid, name, price, description or "", download_link or "", photo_url or "",
                1 if allow_card else 0, 1 if allow_bale else 0, ptype, now_str
            )
        )
        await StoreService.backup_products_to_disk()
        row = await fetch_one("SELECT * FROM products WHERE product_id = ?", (pid,))
        return ProductItem(row)

    @staticmethod
    async def delete_product(product_id: str) -> bool:
        await execute_query("DELETE FROM products WHERE product_id = ?", (product_id,))
        await StoreService.backup_products_to_disk()
        return True

    @staticmethod
    async def get_or_create_customer(user_id: str | int, platform: str = "telegram") -> CustomerItem:
        uid = str(user_id)
        row = await fetch_one("SELECT * FROM customers WHERE user_id = ?", (uid,))
        if not row:
            now_str = get_tehran_now_str()
            await execute_query(
                "INSERT INTO customers (user_id, platform, wallet_balance, terms_accepted, created_at) VALUES (?, ?, 0, 0, ?)",
                (uid, platform, now_str)
            )
            row = await fetch_one("SELECT * FROM customers WHERE user_id = ?", (uid,))
        return CustomerItem(row)

    @staticmethod
    async def get_wallet_balance(user_id: str | int) -> int:
        cust = await StoreService.get_or_create_customer(user_id)
        return cust.wallet_balance

    @staticmethod
    async def create_order(
        user_id: str | int,
        username: str,
        customer_name: str,
        phone: str,
        product: ProductItem,
        platform: str = "telegram",
        wallet_used: int = 0,
        payment_method: Optional[str] = None
    ) -> OrderItem:
        order_id = "ORD_" + uuid.uuid4().hex[:8].upper()
        uid = str(user_id)
        now_str = get_tehran_now_str()
        status = "completed" if product.price == 0 else "pending"
        if not payment_method:
            payment_method = "bale_online" if platform == "bale" else "card_to_card"

        if wallet_used > 0:
            await execute_query("UPDATE customers SET wallet_balance = MAX(0, wallet_balance - ?) WHERE user_id = ?", (wallet_used, uid))

        try:
            await execute_query(
                "INSERT INTO orders (order_id, invoice_id, user_id, username, customer_name, phone, product_id, product_name, total, wallet_used, payment_method, status, platform, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, f"ord_{order_id}", uid, username or "", customer_name or "", phone or "", product.product_id, product.name, product.price, wallet_used, payment_method, status, platform, now_str)
            )
        except Exception:
            await execute_query(
                "INSERT INTO orders (order_id, user_id, username, customer_name, phone, product_id, product_name, total, wallet_used, payment_method, status, platform, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, uid, username or "", customer_name or "", phone or "", product.product_id, product.name, product.price, wallet_used, payment_method, status, platform, now_str)
            )
        row = await fetch_one("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        return OrderItem(row)

    @staticmethod
    async def submit_receipt(order_id: str, receipt_file_id: str) -> bool:
        await execute_query("UPDATE orders SET receipt_file_id = ?, status = 'pending_review' WHERE order_id = ?", (receipt_file_id, order_id))
        return True

    @staticmethod
    async def submit_card_receipt(order_id: str, receipt_file_id: str = "", receipt_text: str = "") -> bool:
        await execute_query(
            "UPDATE orders SET receipt_file_id = COALESCE(NULLIF(?, ''), receipt_file_id), receipt_text = COALESCE(NULLIF(?, ''), receipt_text), status = 'pending_review' WHERE order_id = ?",
            (receipt_file_id, receipt_text, order_id)
        )
        return True

    @staticmethod
    async def delete_order(order_id: str) -> bool:
        await execute_query("DELETE FROM orders WHERE order_id = ?", (order_id,))
        return True

    @staticmethod
    async def cleanup_rejected_orders() -> int:
        rows = await fetch_all("SELECT order_id FROM orders WHERE status = 'rejected'")
        count = len(rows)
        if count > 0:
            await execute_query("DELETE FROM orders WHERE status = 'rejected'")
        return count

    @staticmethod
    async def get_order(order_id: str) -> Optional[OrderItem]:
        if not order_id:
            return None
        raw = str(order_id).strip()
        clean = raw
        for pfx in ("invoice_id=", "invoice_", "ord_ORD_", "ord_ord_", "order_", "ord_", "ORD_"):
            if clean.startswith(pfx):
                clean = clean[len(pfx):]
        clean = clean.split("&")[0].split("?")[0].strip()

        candidates = list(dict.fromkeys([
            raw,
            clean,
            f"ORD_{clean}",
            f"ord_{clean}",
            f"ord_ORD_{clean}",
            f"invoice_{clean}",
            f"ORD_{clean.upper()}",
            f"ord_{clean.lower()}"
        ]))

        placeholders = ", ".join(["?"] * len(candidates))
        sql = f"""
            SELECT * FROM orders
            WHERE order_id IN ({placeholders}) OR invoice_id IN ({placeholders})
            ORDER BY id DESC LIMIT 1
        """
        try:
            order = await fetch_one(sql, tuple(candidates) + tuple(candidates))
        except Exception:
            sql_fallback = f"SELECT * FROM orders WHERE order_id IN ({placeholders}) ORDER BY id DESC LIMIT 1"
            order = await fetch_one(sql_fallback, tuple(candidates))
        return OrderItem(order) if order else None

    @staticmethod
    async def approve_order(order_id: str) -> Optional[Dict[str, Any]]:
        order = await fetch_one("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        if not order:
            return None

        await execute_query("UPDATE orders SET status = 'approved' WHERE order_id = ?", (order_id,))
        
        cashback = int((int(order["total"]) * config.CASHBACK_PERCENT) / 100)
        if cashback > 0:
            uid = str(order["user_id"])
            await StoreService.get_or_create_customer(uid)
            await execute_query("UPDATE customers SET wallet_balance = wallet_balance + ? WHERE user_id = ?", (cashback, uid))

        prod = await StoreService.get_product(order["product_id"])
        updated_order = await fetch_one("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        return {
            "status": "approved",
            "order": OrderItem(updated_order),
            "product": prod,
            "product_name": prod.name if prod else "دوره آموزشی",
            "download_link": prod.download_link if prod else "",
            "cashback_amount": cashback,
            "cashback_awarded": cashback
        }

    @staticmethod
    async def reject_order(order_id: str, reason: str = "") -> Optional[OrderItem]:
        order = await fetch_one("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        if not order:
            return None

        await execute_query("UPDATE orders SET status = 'rejected' WHERE order_id = ?", (order_id,))
        wallet_used = int(order["wallet_used"] or 0)
        if wallet_used > 0:
            await execute_query("UPDATE customers SET wallet_balance = wallet_balance + ? WHERE user_id = ?", (wallet_used, str(order["user_id"])))

        updated = await fetch_one("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        return OrderItem(updated)

    @staticmethod
    async def get_customer_orders(user_id: str | int) -> List[OrderItem]:
        uid = str(user_id)
        rows = await fetch_all("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 10", (uid,))
        return [OrderItem(r) for r in rows]

    @staticmethod
    async def get_all_orders(limit: int = 100) -> List[OrderItem]:
        sql = """
            SELECT o.*, p.download_link
            FROM orders o
            LEFT JOIN products p ON o.product_id = p.product_id
            ORDER BY o.id DESC LIMIT ?
        """
        rows = await fetch_all(sql, (limit,))
        return [OrderItem(r) for r in rows]

    @staticmethod
    async def create_web_order(
        course_id: str,
        customer_name: str,
        phone: str,
        payment_method: str = "bale",
        receipt_info: str = ""
    ) -> Optional[OrderItem]:
        prod = await StoreService.get_product(course_id)
        if not prod:
            return None

        order_id = "ORD_" + uuid.uuid4().hex[:8].upper()
        now_str = get_tehran_now_str()
        status = "completed" if prod.price == 0 else ("pending_review" if "card" in payment_method else "pending")
        uid = f"web_{phone.strip() or uuid.uuid4().hex[:6]}"

        try:
            await execute_query(
                """INSERT INTO orders (
                    order_id, invoice_id, user_id, username, customer_name, phone,
                    product_id, product_name, total, wallet_used,
                    receipt_text, payment_method, status, platform, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_id, f"ord_{order_id}", uid, "", customer_name or "خریدار آنلاین",
                    phone or "", prod.product_id, prod.name, prod.price, 0,
                    receipt_info or "", payment_method, status, "web", now_str
                )
            )
        except Exception:
            await execute_query(
                """INSERT INTO orders (
                    order_id, user_id, username, customer_name, phone,
                    product_id, product_name, total, wallet_used,
                    receipt_text, payment_method, status, platform, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_id, uid, "", customer_name or "خریدار آنلاین",
                    phone or "", prod.product_id, prod.name, prod.price, 0,
                    receipt_info or "", payment_method, status, "web", now_str
                )
            )
        row = await fetch_one("""
            SELECT o.*, p.download_link
            FROM orders o
            LEFT JOIN products p ON o.product_id = p.product_id
            WHERE o.order_id = ?
        """, (order_id,))
        return OrderItem(row) if row else None

    @staticmethod
    async def notify_admin_card_order(order: OrderItem, receipt_image_path: Optional[str] = None) -> None:
        """
        Sends an instant notification for a new card-to-card order to TELEGRAM_OWNER_ID and BALE_OWNER_ID,
        attaching the receipt photo if provided.
        """
        from core.jalali import format_to_jalali
        now_str = format_to_jalali(get_tehran_now_str())
        prod_name = order.product_name or "دوره آموزشی"
        amount = order.total or order.amount or 0
        receipt_txt = order.receipt_text or "ثبت نشده"
        cust_name = order.customer_name or "خریدار آنلاین"
        phone = order.phone or "ثبت نشده"
        ord_id = order.order_id

        admin_txt = (
            f"🔔 <b>اعلان سفارش جدید کارت‌به‌کارت (استورفرانت)</b>\n\n"
            f"🎓 <b>نام دوره:</b> {prod_name}\n"
            f"💰 <b>مبلغ:</b> <code>{amount:,} تومان</code>\n"
            f"👤 <b>خریدار:</b> {cust_name}\n"
            f"📞 <b>شماره تماس:</b> <code>{phone}</code>\n"
            f"🧾 <b>اطلاعات فیش / پیگیری:</b>\n<code>{receipt_txt}</code>\n"
            f"🔖 <b>کد سفارش (ORD):</b> <code>{ord_id}</code>\n"
            f"⏰ <b>زمان ثبت:</b> <code>{now_str}</code>\n\n"
            f"⚠️ لطفاً فیش واریزی را بررسی و در صورت صحت، سفارش را در پنل وب تایید فرمایید."
        )

        has_image = bool(receipt_image_path and os.path.exists(receipt_image_path))

        # 1. Telegram notification (Forum Topic + Direct Admin PV from SQLite)
        try:
            from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            tg_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ تایید سفارش و ارسال دوره", callback_data=f"adm_app:{ord_id}"),
                    InlineKeyboardButton("❌ رد سفارش", callback_data=f"adm_rej:{ord_id}")
                ]
            ])
            from services import web_panel
            tg_adapter = getattr(web_panel, "ACTIVE_TG_ADAPTER", None)
            
            # Direct SQLite fallback for TELEGRAM_OWNER_ID
            db_tg_owner = (await get_system_setting("TELEGRAM_OWNER_ID", "")) or (await get_system_setting("tg_owner_id", ""))
            owner_tg_id = config.TELEGRAM_OWNER_ID or db_tg_owner or (tg_adapter.get_admin_id() if tg_adapter else "")

            if tg_adapter and tg_adapter.app and tg_adapter.app.is_connected:
                # If forum group configured, send to receipts topic
                forum_id = getattr(config, "TELEGRAM_FORUM_GROUP_ID", "")
                thread_id = None
                if forum_id:
                    try:
                        topics = await tg_adapter.ensure_forum_topics()
                        thread_id = topics.get("tg_topic_receipts")
                        if has_image:
                            await tg_adapter.send_photo(forum_id, receipt_image_path, caption=admin_txt, reply_markup=tg_kb, message_thread_id=thread_id)
                        else:
                            await tg_adapter.send_message(forum_id, admin_txt, reply_markup=tg_kb, message_thread_id=thread_id)
                    except Exception as err_topic:
                        logger.warning(f"[store_service] Telegram forum topic dispatch failed: {err_topic}")

                # Send directly to Admin PV
                if owner_tg_id and str(owner_tg_id).strip() not in ("0", ""):
                    try:
                        if has_image:
                            await tg_adapter.send_photo(owner_tg_id, receipt_image_path, caption=admin_txt, reply_markup=tg_kb)
                        else:
                            await tg_adapter.send_message(owner_tg_id, admin_txt, reply_markup=tg_kb)
                    except Exception as err_pv:
                        logger.warning(f"[store_service] Telegram owner PV dispatch failed: {err_pv}")
        except Exception as ex_tg:
            logger.warning(f"[store_service] Failed to notify Telegram admin: {ex_tg}")

        # 2. Bale notification (Direct Admin PV from SQLite)
        try:
            bale_kb = {
                "inline_keyboard": [
                    [
                        {"text": "✅ تایید سفارش و ارسال دوره", "callback_data": f"adm_app:{ord_id}"},
                        {"text": "❌ رد سفارش", "callback_data": f"adm_rej:{ord_id}"}
                    ]
                ]
            }
            from services import web_panel
            bale_adapter = getattr(web_panel, "ACTIVE_BALE_ADAPTER", None)
            if not bale_adapter:
                from platforms.bale_adapter import BaleAdapter
                bale_adapter = BaleAdapter()

            # Direct SQLite fallback for BALE_OWNER_ID and BALE_BOT_TOKEN
            db_bale_owner = (await get_system_setting("BALE_OWNER_ID", "")) or (await get_system_setting("bale_owner_id", ""))
            target_bale_id = config.BALE_OWNER_ID or db_bale_owner or (bale_adapter.get_admin_chat_id() if bale_adapter else "402479514")
            db_bale_token = (await get_system_setting("BALE_BOT_TOKEN", "")) or (await get_system_setting("bale_bot_token", ""))
            has_bale_token = bool(config.BALE_BOT_TOKEN or db_bale_token)

            if target_bale_id and has_bale_token:
                if has_image:
                    await bale_adapter.send_photo(target_bale_id, receipt_image_path, caption=admin_txt, reply_markup=bale_kb)
                else:
                    await bale_adapter.send_message(target_bale_id, admin_txt, reply_markup=bale_kb)
        except Exception as ex_bale:
            logger.warning(f"[store_service] Failed to notify Bale admin: {ex_bale}")

    @staticmethod
    async def get_order_status_for_customer(order_id: str) -> Optional[dict]:
        sql = """
            SELECT o.*, p.download_link, p.description, p.photo_url
            FROM orders o
            LEFT JOIN products p ON o.product_id = p.product_id
            WHERE o.order_id = ?
        """
        row = await fetch_one(sql, (order_id.strip(),))
        if not row:
            return None
        return {
            "order_id": row["order_id"],
            "status": row["status"],
            "product_name": row["product_name"],
            "total": row["total"],
            "payment_method": row.get("payment_method", "bale"),
            "customer_name": row["customer_name"],
            "phone": row["phone"],
            "created_at": row["created_at"],
            "download_link": row["download_link"] if row["status"] in ("approved", "completed") else "",
            "is_paid": row["status"] in ("approved", "completed")
        }

    @staticmethod
    async def create_support_ticket(user_id: str | int, username: str, text: str, platform: str = "telegram") -> TicketItem:
        ticket_id = "TCK_" + uuid.uuid4().hex[:6].upper()
        now_str = get_tehran_now_str()
        await execute_query(
            "INSERT INTO support_tickets (ticket_id, user_id, username, message_text, status, platform, created_at) VALUES (?, ?, ?, ?, 'open', ?, ?)",
            (ticket_id, str(user_id), username or "", text, platform, now_str)
        )
        row = await fetch_one("SELECT * FROM support_tickets WHERE ticket_id = ?", (ticket_id,))
        return TicketItem(row)

    @staticmethod
    async def get_customer_purchased_courses(user_id: str | int, phone: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns all unique courses successfully purchased by the customer across all platforms.
        """
        uid = str(user_id).strip()
        ph = str(phone or "").strip()
        sql = """
            SELECT o.*, p.name as course_name, p.download_link, p.photo_url, p.description
            FROM orders o
            JOIN products p ON o.product_id = p.product_id
            WHERE (o.user_id = ? OR (o.phone IS NOT NULL AND o.phone != '' AND o.phone = ?))
              AND o.status IN ('approved', 'completed', 'paid')
            ORDER BY o.id DESC
        """
        rows = await fetch_all(sql, (uid, ph))
        results = []
        seen = set()
        for r in rows:
            pid = r["product_id"]
            if pid not in seen:
                seen.add(pid)
                results.append({
                    "product_id": pid,
                    "name": r["course_name"] or r["product_name"] or "دوره آموزشی",
                    "download_link": r["download_link"] or "",
                    "photo_url": r["photo_url"] or "",
                    "order_id": r["order_id"],
                    "created_at": r["created_at"]
                })
        return results

    @staticmethod
    async def request_zarinpal_payment(
        course_id: str,
        customer_name: str,
        phone: str,
        email: str = "",
        callback_url: str = ""
    ) -> Dict[str, Any]:
        """
        Initiates a Zarinpal v4 payment request and records a pending order.
        """
        merchant_id = getattr(config, "ZARINPAL_MERCHANT_ID", "").strip()
        if not merchant_id:
            return {"ok": False, "error": "درگاه پرداخت زرین‌پال در تنظیمات سیستم فعال یا پیکربندی نشده است."}

        prod = await StoreService.get_product(course_id)
        if not prod:
            return {"ok": False, "error": "دوره مورد نظر یافت نشد."}

        order_id = "ORD_" + uuid.uuid4().hex[:8].upper()
        now_str = get_tehran_now_str()
        amount_rials = int(prod.price * 10)

        # Save pending order in SQLite
        uid = f"web_{phone.strip() or uuid.uuid4().hex[:6]}"
        try:
            await execute_query(
                """INSERT INTO orders (
                    order_id, invoice_id, user_id, username, customer_name, phone,
                    product_id, product_name, total, wallet_used,
                    receipt_text, payment_method, status, platform, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_id, f"zpal_{order_id}", uid, "", customer_name or "خریدار آنلاین زرین‌پال",
                    phone or "", prod.product_id, prod.name, prod.price, 0,
                    "", "zarinpal", "pending", "web", now_str
                )
            )
        except Exception:
            await execute_query(
                """INSERT INTO orders (
                    order_id, user_id, username, customer_name, phone,
                    product_id, product_name, total, wallet_used,
                    receipt_text, payment_method, status, platform, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_id, uid, "", customer_name or "خریدار آنلاین زرین‌پال",
                    phone or "", prod.product_id, prod.name, prod.price, 0,
                    "", "zarinpal", "pending", "web", now_str
                )
            )

        is_sandbox = getattr(config, "ZARINPAL_SANDBOX", False)
        api_url = "https://sandbox.zarinpal.com/pg/v4/payment/request.json" if is_sandbox else "https://api.zarinpal.com/pg/v4/payment/request.json"
        start_pay_url = "https://sandbox.zarinpal.com/pg/StartPay/" if is_sandbox else "https://www.zarinpal.com/pg/StartPay/"

        full_callback = f"{callback_url}?order_id={order_id}" if callback_url else f"/api/payment/zarinpal/callback?order_id={order_id}"

        payload = {
            "merchant_id": merchant_id,
            "amount": amount_rials,
            "currency": "IRR",
            "description": f"خرید آنلاین دوره {prod.name}",
            "callback_url": full_callback,
            "metadata": {
                "mobile": phone or "",
                "email": email or ""
            }
        }

        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.post(api_url, json=payload) as resp:
                    res_data = await resp.json()
                    data = res_data.get("data") or {}
                    errors = res_data.get("errors")
                    code = data.get("code")
                    if code == 100:
                        authority = data.get("authority")
                        pay_url = f"{start_pay_url}{authority}"
                        return {
                            "ok": True,
                            "order_id": order_id,
                            "authority": authority,
                            "payment_url": pay_url
                        }
                    else:
                        err_msg = str(errors) if errors else f"خطای درگاه زرین‌پال کد {code}"
                        return {"ok": False, "error": err_msg}
        except Exception as e:
            logger.error(f"[zarinpal] Request error: {e}")
            return {"ok": False, "error": f"خطا در ارتباط با سرور زرین‌پال: {str(e)}"}

    @staticmethod
    async def verify_zarinpal_payment(order_id: str, authority: str) -> Dict[str, Any]:
        """
        Verifies a completed payment with Zarinpal and fulfills the order.
        """
        order = await fetch_one("SELECT * FROM orders WHERE order_id = ?", (order_id.strip(),))
        if not order:
            return {"ok": False, "error": "سفارش یافت نشد."}

        prod = await StoreService.get_product(order["product_id"])
        dl_link = prod.download_link if prod else ""

        if order["status"] in ("completed", "approved", "paid"):
            return {"ok": True, "order": OrderItem(order), "download_link": dl_link}

        merchant_id = getattr(config, "ZARINPAL_MERCHANT_ID", "").strip()
        amount_rials = int(order["total"] * 10)
        is_sandbox = getattr(config, "ZARINPAL_SANDBOX", False)
        verify_url = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json" if is_sandbox else "https://api.zarinpal.com/pg/v4/payment/verify.json"

        payload = {
            "merchant_id": merchant_id,
            "amount": amount_rials,
            "authority": authority
        }

        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.post(verify_url, json=payload) as resp:
                    res_data = await resp.json()
                    data = res_data.get("data") or {}
                    code = data.get("code")
                    if code in (100, 101):
                        ref_id = str(data.get("ref_id") or "")
                        await execute_query(
                            "UPDATE orders SET status = 'completed', receipt_text = ? WHERE order_id = ?",
                            (f"Zarinpal RefID: {ref_id}", order_id)
                        )
                        # Award cashback if enabled
                        cashback = int((int(order["total"]) * config.CASHBACK_PERCENT) / 100)
                        if cashback > 0:
                            await execute_query(
                                "UPDATE customers SET wallet_balance = wallet_balance + ? WHERE user_id = ?",
                                (cashback, str(order["user_id"]))
                            )

                        updated_order = await fetch_one("SELECT * FROM orders WHERE order_id = ?", (order_id,))
                        return {
                            "ok": True,
                            "order": OrderItem(updated_order),
                            "ref_id": ref_id,
                            "download_link": dl_link
                        }
                    else:
                        errors = res_data.get("errors")
                        err_msg = str(errors) if errors else f"خطای تایید تراکنش زرین‌پال کد {code}"
                        return {"ok": False, "error": err_msg}
        except Exception as e:
            logger.error(f"[zarinpal] Verify error: {e}")
            return {"ok": False, "error": f"خطا در ارتباط با زرین‌پال: {str(e)}"}

    @staticmethod
    def parse_delivery_links(raw_text_or_url: str) -> Dict[str, Any]:
        return parse_course_delivery_links(raw_text_or_url)

    @staticmethod
    def format_delivery_message(product_name: str, order_id: str, dl_content: str, cashback_awarded: int = 0) -> str:
        return format_customer_delivery_message(product_name, order_id, dl_content, cashback_awarded)

    @staticmethod
    def format_customer_course_card(product_name: str, download_link: Optional[str], index: Optional[int] = None, total: Optional[int] = None) -> Tuple[str, List[Dict[str, str]]]:
        return format_customer_course_card(product_name, download_link, index, total)


def clean_delivery_instruction(instruction: str, product_name: str = "") -> str:
    """
    Strips boilerplate labels, markdown formatting, redundant quotes, and echoes of the course name
    from delivery instructions, leaving only genuine instructional text.
    """
    if not instruction:
        return ""
    # 1. Strip markdown formatting (*, _, ~, `, #)
    cleaned = re.sub(r"[\*_~`#]", "", instruction).strip()

    # 2. Strip common boilerplate labels and platform indicators
    cleaned = re.sub(
        r"(?i)(لینک\s*(?:ورود\s*به\s*)?دوره(?:\s*«[^»]+»)?|در\s*(?:بله|تلگرام|روبیکا)\s*:?|تقدیم\s*شما|با\s*احترام|سلام|روز\s*بخیر|🌹|🌸|✨|راهنما\s*:?)",
        "",
        cleaned
    ).strip()

    # 3. Strip quotes, brackets, and extra punctuation
    cleaned_no_quotes = re.sub(r"[«»\"\'\(\)\[\]]", "", cleaned).strip()

    # 4. If what remains is just the product name or words from it, discard it as redundant filler
    if product_name:
        prod_clean = re.sub(r"[«»\"\'\(\)\[\]\*\_\~]", "", product_name).strip().lower()
        c_low = cleaned_no_quotes.lower()
        if c_low == prod_clean or (prod_clean and c_low in prod_clean) or (c_low and prod_clean in c_low):
            return ""
        prod_words = set(re.findall(r"[\w\u0600-\u06FF]+", prod_clean))
        inst_words = [w for w in re.findall(r"[\w\u0600-\u06FF]+", c_low) if w not in ("دوره", "آموزشی", "جامع", "راهنما", "پکیج")]
        if inst_words and all(w in prod_words for w in inst_words):
            return ""

    cleaned = re.sub(r"^[\s\:\-\–\—\.\،\,]+", "", cleaned)
    cleaned = re.sub(r"[\s\:\-\–\—\.\،\,]+$", "", cleaned).strip()

    if len(cleaned_no_quotes) < 4:
        return ""
    return cleaned


def parse_course_delivery_links(raw_text_or_url: str) -> Dict[str, Any]:
    """
    Intelligently parses multi-platform course delivery text.
    Extracts URLs for Telegram, Bale, Rubika, and direct downloads.
    Separates instructional notes and attaches warm closing message.
    """
    default_closing = getattr(config, "COURSE_DELIVERY_NOTE", None) or "امیدوارم این دوره، براتون سرشار از آگاهی، رشد و نتایج ارزشمند باشه. ✨"
    if not raw_text_or_url:
        return {
            "has_links": False,
            "links": [],
            "instructions": "",
            "warm_closing": default_closing
        }

    raw = str(raw_text_or_url).strip()

    # Regex matching URLs (http/https, www, or platform shortlinks like ble.ir, t.me, rubika.ir)
    pattern = r'(https?://[^\s<>"]+|(?:\b(?:t\.me|telegram\.me|ble\.ir|bale\.ai|rubika\.ir)/[^\s<>"]+)|(?:www\.[^\s<>"]+))'
    matches = re.findall(pattern, raw, flags=re.IGNORECASE)

    extracted_links = []
    seen_urls = set()

    for m in matches:
        clean_url = m.strip(".,;:()[]{}<>\"'")
        normalized_url = clean_url
        if not normalized_url.startswith("http://") and not normalized_url.startswith("https://"):
            normalized_url = f"https://{normalized_url}"

        if normalized_url.lower() in seen_urls:
            continue
        seen_urls.add(normalized_url.lower())

        lower_u = normalized_url.lower()
        if "t.me" in lower_u or "telegram.me" in lower_u:
            link_type = "telegram"
            title = "✈️ دسترسی به محتوای دوره از طریق تلگرام"
        elif "ble.ir" in lower_u or "bale.ai" in lower_u:
            link_type = "bale"
            title = "🟢 دسترسی به محتوای دوره از طریق بله"
        elif "rubika.ir" in lower_u:
            link_type = "rubika"
            title = "🟣 دسترسی به محتوای دوره از طریق روبیکا"
        else:
            link_type = "download"
            title = "📥 دانلود و دسترسی مستقیم به دوره"

        extracted_links.append({
            "url": normalized_url,
            "raw": clean_url,
            "type": link_type,
            "title": title
        })

    # Clean the raw text by removing raw URL tokens to leave only instructions
    cleaned_text = raw
    for m in matches:
        cleaned_text = cleaned_text.replace(m, "")
    lines = [ln.strip() for ln in cleaned_text.splitlines() if ln.strip()]
    instructions = "\n".join(lines).strip()

    return {
        "has_links": len(extracted_links) > 0,
        "links": extracted_links,
        "instructions": instructions,
        "warm_closing": default_closing
    }


def format_customer_delivery_message(product_name: str, order_id: str, dl_content: str, cashback_awarded: int = 0) -> str:
    parsed = parse_course_delivery_links(dl_content)
    lines = [
        f"🎉 <b>سفارش شما برای دوره «{html.escape(product_name)}» با موفقیت تایید شد!</b>",
        "",
        f"🔖 کد سفارش: <code>{order_id}</code>",
        ""
    ]
    cleaned_inst = clean_delivery_instruction(parsed.get("instructions", ""), product_name)

    if cleaned_inst:
        lines.extend([
            "📦 <b>راهنمای دسترسی به دوره:</b>",
            f"<blockquote>{html.escape(cleaned_inst)}</blockquote>",
            ""
        ])
    elif not parsed["has_links"]:
        lines.extend([
            "📦 <b>محتوا و راه‌های دسترسی به دوره:</b>",
            f"<blockquote>{html.escape(dl_content or 'جهت دریافت راهنمایی دسترسی با پشتیبانی در ارتباط باشید.')}</blockquote>",
            ""
        ])

    if cashback_awarded > 0:
        lines.extend([
            f"🎁 مبلغ <b>{cashback_awarded:,} تومان</b> پاداش خرید (کش‌بک) به کیف پول شما منظور شد.",
            ""
        ])

    lines.append(parsed["warm_closing"])
    return "\n".join(lines)


def clean_course_access_input(text: str, product_name: str = "") -> str:
    """
    Intelligently cleans admin input for course access links.
    Extracts all platform links (Bale, Telegram, Rubika, Web),
    removes connective filler text (e.g. 'در بله:', 'در تلگرام:', 'تقدیم شما 🌹', redundant course titles),
    and preserves only genuine instructions.
    """
    if not text or not str(text).strip():
        return ""
    raw = str(text).strip()
    parsed = parse_course_delivery_links(raw)
    if not parsed.get("has_links") or not parsed.get("links"):
        return raw

    urls = [lk["url"] for lk in parsed["links"]]
    raw_instructions = parsed.get("instructions", "")
    cleaned_notes = clean_delivery_instruction(raw_instructions, product_name)

    if cleaned_notes:
        return "\n".join(urls) + f"\nراهنما: {cleaned_notes}"
    return "\n".join(urls)


def format_customer_course_card(
    product_name: str,
    download_link: Optional[str],
    index: Optional[int] = None,
    total: Optional[int] = None
) -> Tuple[str, List[Dict[str, str]]]:
    """
    Builds a clean, professional course access card and inline buttons for customer view.
    Does NOT dump raw URLs into text.
    Extracts multi-platform buttons for Telegram, Bale, Rubika, and direct download.
    """
    parsed = parse_course_delivery_links(download_link or "")

    header = f"🎓 <b>دوره ({index} از {total}): {html.escape(product_name)}</b>" if (index and total) else f"🎓 <b>دوره: {html.escape(product_name)}</b>"

    lines = [header, ""]

    inst = clean_delivery_instruction(parsed.get("instructions", ""), product_name)

    if parsed.get("has_links") and parsed.get("links"):
        lines.append("✨ <b>راه‌های دسترسی به محتوای دوره:</b>")
        lines.append("جهت ورود به محتوا و عضویت در کانال‌های اختصاصی دوره، از دکمه‌های شیشه‌ای زیر استفاده فرمایید:")
        if inst:
            lines.extend([
                "",
                "📦 <b>راهنمای دسترسی:</b>",
                f"<blockquote>{html.escape(inst)}</blockquote>"
            ])
    else:
        lines.append("📦 <b>محتوا و راه‌های دسترسی به دوره:</b>")
        if inst:
            lines.append(f"<blockquote>{html.escape(inst)}</blockquote>")
        else:
            lines.append("<blockquote>جهت دریافت راهنمایی و فعال‌سازی دسترسی با پشتیبانی در ارتباط باشید.</blockquote>")

    lines.append("")
    lines.append("امیدواریم این دوره برای شما سرشار از رشد و آگاهی باشد. ✨")

    buttons = []
    for lk in parsed.get("links", []):
        buttons.append({
            "text": lk["title"],
            "url": lk["url"],
            "type": lk.get("type", "download")
        })

    return "\n".join(lines), buttons


def format_course_links_for_card(download_link: Optional[str]) -> str:
    """
    Formats course access links into clean, organized status badges for admin cards.
    Shows checkmarks for configured platforms instead of dumping long raw URLs.
    """
    if not download_link or not str(download_link).strip():
        return "<code>تنظیم نشده ❌</code>"
    parsed = parse_course_delivery_links(str(download_link))
    if not parsed.get("has_links") or not parsed.get("links"):
        return f"<code>{html.escape(str(download_link).strip())}</code>"

    has_bale = any(lk.get("type") == "bale" for lk in parsed["links"])
    has_tg = any(lk.get("type") == "telegram" for lk in parsed["links"])
    has_rub = any(lk.get("type") == "rubika" for lk in parsed["links"])
    has_dl = any(lk.get("type") == "download" for lk in parsed["links"])

    badges = []
    if has_bale:
        badges.append("🟢 بله: ثبت شده ✅")
    else:
        badges.append("🟢 بله: تنظیم نشده ❌")

    if has_tg:
        badges.append("✈️ تلگرام: ثبت شده ✅")
    else:
        badges.append("✈️ تلگرام: تنظیم نشده ❌")

    if has_rub:
        badges.append("🟣 روبیکا: ثبت شده ✅")

    if has_dl:
        badges.append("🌐 دانلود مستقیم: ثبت شده ✅")

    lines = [f"▫️ {b}" for b in badges]

    if parsed.get("instructions"):
        cleaned_inst = clean_delivery_instruction(parsed["instructions"])
        if cleaned_inst:
            lines.append(f"▫️ ℹ️ <b>راهنما:</b> {html.escape(cleaned_inst)}")
    return "\n".join(lines)


def format_course_photo_for_card(photo_url: Optional[str]) -> str:
    """
    Formats course banner/photo cleanly for admin cards to prevent Bidi RTL/LTR flipping.
    """
    if not photo_url or not str(photo_url).strip():
        return "فاقد تصویر"
    clean = str(photo_url).strip()
    fn = Path(clean.split("?")[0]).name
    return f"تنظیم شده ✅ (<code>{html.escape(fn)}</code>)"



