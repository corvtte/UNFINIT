import re

p_file = 'services/web_panel.py'
text = open(p_file, encoding='utf-8').read()

rescrap = """async def handle_crawler_rescrap_item_async(payload: dict) -> dict:
    url = (payload.get("url") or "").strip()
    if not url:
        return {"ok": False, "error": "URL not provided"}
    try:
        from services.feed_crawler import FeedCrawler, FeedAuthManager
        session = await FeedAuthManager.get_session()
        details = await FeedCrawler.fetch_article_details(session, url)
        
        from core.database import execute_query
        audio_url = details.get("audio_url", "")
        video_url = details.get("video_url", "")
        thumbnail = details.get("cover_url", "")
        if audio_url or video_url or thumbnail:
            await execute_query("UPDATE abasmanesh_feed SET audio_url = ?, video_url = ?, thumbnail_url = ? WHERE source_url = ?", (audio_url, video_url, thumbnail, url))
        
        return {"ok": True, "audio_url": audio_url, "video_url": video_url, "url": audio_url or video_url, "thumbnail_url": thumbnail}
    except Exception as e:
        return {"ok": False, "error": str(e)}"""

text = re.sub(r'async def handle_crawler_rescrap_item_async\(payload: dict\) -> dict:.*?(?=\ndef handle_crawler_rescrap_item)', rescrap, text, flags=re.DOTALL)

open(p_file, 'w', encoding='utf-8').write(text)
