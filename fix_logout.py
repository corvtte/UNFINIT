import sys

filepath = 'app.py'
text = open(filepath, encoding='utf-8').read()

new_logout = '''        elif path == "/api/crawler/logout":
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                from services.feed_crawler import FeedAuthManager
                loop.run_until_complete(FeedAuthManager.invalidate_session())
                
                from pathlib import Path
                import json
                import core.config as config
                settings_file = getattr(config, "SETTINGS_JSON_FILE", None) or (Path(getattr(config, "DATA_DIR", "data")) / "settings.json")
                if settings_file.exists():
                    with open(settings_file, "r", encoding="utf-8") as f:
                        settings = json.load(f)
                    settings["FEED_AUTH_EMAIL"] = ""
                    settings["FEED_AUTH_PASSWORD"] = ""
                    settings["FEED_AUTH_COOKIE"] = ""
                    with open(settings_file, "w", encoding="utf-8") as f:
                        json.dump(settings, f, ensure_ascii=False, indent=4)
                        
                loop.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": "با موفقیت خارج شدید."}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}, ensure_ascii=False).encode("utf-8"))
            return
        else:'''

text = text.replace('        else:', new_logout)
open(filepath, 'w', encoding='utf-8').write(text)
print('Logout endpoint added')
