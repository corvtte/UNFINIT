import os
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from core.database import execute_query, fetch_one, fetch_all
from core.normalizer import normalize_persian_text
from core.logger import get_logger

logger = get_logger("keyword_service")

class KeywordRuleItem:
    def __init__(self, d: dict):
        self.id = int(d.get("id", 0))
        self.platform = str(d.get("platform", "INSTAGRAM")).upper()
        self.keyword = str(d.get("keyword", "")).strip()
        self.matching_mode = str(d.get("matching_mode", "EXACT")).upper()
        self.response_type = str(d.get("response_type", "TEXT")).upper()
        self.response_text = str(d.get("response_text", ""))
        self.media_id = d.get("media_id")
        self.enabled = bool(d.get("enabled", 1))
        self.priority = int(d.get("priority", 0) or 0)
        self.created_at = str(d.get("created_at", ""))
        self.updated_at = str(d.get("updated_at", ""))

class KeywordService:
    @staticmethod
    async def create_rule(
        keyword: str,
        response_text: str,
        matching_mode: str = "EXACT",
        response_type: str = "TEXT",
        media_id: Optional[str] = None,
        platform: str = "INSTAGRAM",
        priority: int = 0,
        enabled: bool = True
    ) -> KeywordRuleItem:
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        sql = """
        INSERT INTO keyword_rules (
            platform, keyword, matching_mode, response_type,
            response_text, media_id, enabled, priority, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            platform.upper(),
            keyword.strip(),
            matching_mode.upper(),
            response_type.upper(),
            response_text.strip(),
            media_id,
            1 if enabled else 0,
            priority,
            now_str,
            now_str
        )
        row_id = await execute_query(sql, params)
        row = await fetch_one("SELECT * FROM keyword_rules WHERE id = ?", (row_id,))
        return KeywordRuleItem(row)

    @staticmethod
    async def update_rule(
        rule_id: int,
        **updates
    ) -> Optional[KeywordRuleItem]:
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        updates["updated_at"] = now_str
        
        set_clauses = []
        params = []
        for k, v in updates.items():
            set_clauses.append(f"{k} = ?")
            if isinstance(v, bool):
                params.append(1 if v else 0)
            elif isinstance(v, str):
                params.append(v.upper() if k in ("platform", "matching_mode", "response_type") else v)
            else:
                params.append(v)
                
        params.append(rule_id)
        sql = f"UPDATE keyword_rules SET {', '.join(set_clauses)} WHERE id = ?"
        await execute_query(sql, tuple(params))
        row = await fetch_one("SELECT * FROM keyword_rules WHERE id = ?", (rule_id,))
        return KeywordRuleItem(row) if row else None

    @staticmethod
    async def delete_rule(rule_id: int) -> bool:
        await execute_query("DELETE FROM keyword_rules WHERE id = ?", (rule_id,))
        return True

    @staticmethod
    async def get_rule(rule_id: int) -> Optional[KeywordRuleItem]:
        row = await fetch_one("SELECT * FROM keyword_rules WHERE id = ?", (rule_id,))
        return KeywordRuleItem(row) if row else None

    @staticmethod
    async def get_rules(platform: Optional[str] = None, enabled_only: bool = False) -> List[KeywordRuleItem]:
        conditions = []
        params = []
        if platform:
            conditions.append("(platform = ? OR platform = 'ALL')")
            params.append(platform.upper())
        if enabled_only:
            conditions.append("enabled = 1")
            
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM keyword_rules {where} ORDER BY priority DESC, id ASC"
        rows = await fetch_all(sql, tuple(params))
        return [KeywordRuleItem(r) for r in rows]

    @staticmethod
    async def match_keyword(
        incoming_text: str,
        platform: str = "INSTAGRAM"
    ) -> Optional[KeywordRuleItem]:
        """
        Matches an incoming message against active keyword rules for the specified platform.
        Uses Persian normalization and respects priority ordering (highest priority first).
        """
        if not incoming_text:
            return None

        normalized_input = normalize_persian_text(incoming_text)
        rules = await KeywordService.get_rules(platform=platform, enabled_only=True)

        for rule in rules:
            normalized_kw = normalize_persian_text(rule.keyword)
            if not normalized_kw:
                continue

            mode = rule.matching_mode
            is_matched = False

            if mode == "EXACT":
                is_matched = (normalized_input == normalized_kw)
            elif mode == "STARTS_WITH":
                is_matched = normalized_input.startswith(normalized_kw)
            elif mode == "CONTAINS":
                is_matched = (normalized_kw in normalized_input)

            if is_matched:
                logger.info(
                    f"[KeywordMatch] Text '{incoming_text}' matched rule ID={rule.id} "
                    f"(kw='{rule.keyword}', mode={mode}, priority={rule.priority})"
                )
                return rule

        return None
