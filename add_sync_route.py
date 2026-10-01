import re

p_file = 'app.py'
text = open(p_file, encoding='utf-8').read()

route = """        elif path == "/api/feed/sync-thumbnails":
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                from services.feed_crawler import FeedCrawler
                loop.run_until_complete(FeedCrawler.sync_page_1_cache())
                loop.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8"))
            return
        elif path == "/api/vip/settings":"""

text = text.replace('        elif path == "/api/vip/settings":', route)

open(p_file, 'w', encoding='utf-8').write(text)
