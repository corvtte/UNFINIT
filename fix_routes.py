import sys
import re

sys.stdout.reconfigure(encoding='utf-8')
app_file = 'app.py'
lines = open(app_file, encoding='utf-8').readlines()

# ====================================================
# 1. Remove save-auth and test-auth blocks from do_GET
#    They sit at lines 819-852 (0-indexed)
# ====================================================
new_lines = lines[:819] + lines[853:]

# ====================================================
# 2. Add them to do_POST, just before the final 'else' block
#    Find the "else:" fallback at the end of do_POST
# ====================================================
text = ''.join(new_lines)

new_endpoints = """        elif path == "/api/crawler/save-auth":
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                from services.web_panel import handle_crawler_save_auth_async
                res = loop.run_until_complete(handle_crawler_save_auth_async(payload))
                loop.close()
                self.send_response(200 if res.get("success") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e) or repr(e), "error": str(e) or repr(e)}, ensure_ascii=False).encode("utf-8"))
            return
        elif path == "/api/crawler/test-auth":
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                from services.web_panel import handle_crawler_test_auth_async
                res = loop.run_until_complete(handle_crawler_test_auth_async(payload))
                loop.close()
                self.send_response(200 if res.get("success") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e) or repr(e), "authenticated": False}, ensure_ascii=False).encode("utf-8"))
            return
"""

# Insert before the final fallback 'else' at end of do_POST
# That fallback is:  "        else:\n            self.send_response(200)\n"
old_fallback = '        else:\n            self.send_response(200)\n            self.send_header("Content-Type", "application/json; charset=utf-8")\n            self.end_headers()\n            self.wfile.write(b\'{"status":"OK"}\')\n'

if old_fallback in text:
    text = text.replace(old_fallback, new_endpoints + old_fallback, 1)
    print("Inserted new endpoints before fallback")
else:
    print("Fallback not found! Trying alternate...")
    # Try another approach - find log_message as anchor
    anchor = '    def log_message(self, format, *args):\n        return\n'
    if anchor in text:
        text = text.replace(anchor, new_endpoints + anchor, 1)
        print("Inserted using log_message anchor")
    else:
        print("Could not find insertion point")

open(app_file, 'w', encoding='utf-8').write(text)
print("Done")
