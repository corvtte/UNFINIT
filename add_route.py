import re

p_file = 'app.py'
text = open(p_file, encoding='utf-8').read()

# Add import
text = text.replace('    handle_crawler_test_auth,', '    handle_crawler_test_auth,\n    handle_crawler_save_auth,')

# Add route
route = """        elif path == "/api/crawler/save-auth":
            try:
                res = handle_crawler_save_auth(payload)
                self.send_response(200 if res.get("success") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}, ensure_ascii=False).encode("utf-8"))
            return
        elif path == "/api/crawler/test-auth":"""

text = text.replace('        elif path == "/api/crawler/test-auth":', route)

open(p_file, 'w', encoding='utf-8').write(text)
