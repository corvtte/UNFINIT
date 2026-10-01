import re

p = 'services/web_panel.py'
text = open(p, encoding='utf-8').read()

new_render = r"""def render_dashboard_html() -> str:
    from pathlib import Path
    import json
    
    settings = {}
    try:
        settings_file = getattr(config, "SETTINGS_JSON_FILE", None) or (Path(getattr(config, "DATA_DIR", "data")) / "settings.json")
        if settings_file.exists():
            with open(settings_file, "r", encoding="utf-8") as sf:
                settings = json.load(sf)
    except:
        pass

    health = get_system_health(settings)
    p_info = health["platforms"]
    s = health["stats"]
    connected_platforms_count = sum(1 for p_val in p_info.values() if p_val.get("status") == "ONLINE")

    products = []
    saved_theme = settings.get("THEME", "default-dark")
    all_themes = get_all_themes()
    if not saved_theme or saved_theme not in all_themes:
        saved_theme = "default-dark"

    try:
        from core.database import execute_query
        from services.store_service import ProductItem
        rows = execute_query("SELECT * FROM products ORDER BY id ASC")
        products = [ProductItem.from_db_row(r) for r in rows]
    except Exception as e:
        logger.warning(f"Failed to load products sync in dashboard: {e}")

    bale_cap, bale_buf, bale_effective = get_bale_cap_config(settings)

    from services.feed_scraper import get_all_categories
    all_cats = get_all_categories()
    cfg = settings
    premium_categories_html = ""
    for cat in all_cats:"""

text = re.sub(r'def render_dashboard_html\(\) -> str:.*?premium_categories_html = ""\n    for cat in all_cats:', new_render, text, flags=re.DOTALL)

open(p, 'w', encoding='utf-8').write(text)
