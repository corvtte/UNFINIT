import re

p_file = 'services/web_panel.py'
text = open(p_file, encoding='utf-8').read()

rescrap_dispatch = """        details = await FeedCrawler.scrape_single_item(url)
        if details:
            dl_links = json.dumps(details.get("download_links", []), ensure_ascii=False)
            await execute_query(
                "UPDATE crawler_cache SET download_links = ?, last_scraped = CURRENT_TIMESTAMP WHERE link = ?",
                (dl_links, url)
            )
            audio_url = details.get("audio_url", "")
            video_url = details.get("video_url", "")
            thumbnail = details.get("cover_url", "")
            await execute_query("UPDATE abasmanesh_feed SET audio_url = ?, video_url = ?, thumbnail_url = ? WHERE source_url = ?", (audio_url, video_url, thumbnail, url))
            
            links = details.get("download_links", [])"""

text = re.sub(r'        details = await FeedCrawler\.scrape_single_item\(url\).*?links = details\.get\("download_links", \[\]\)', rescrap_dispatch, text, flags=re.DOTALL)

open(p_file, 'w', encoding='utf-8').write(text)
