import urllib.request
import json
import os
import sys

def get_hf_logs(token, space_id, log_type="run", lines=50):
    url = f"https://huggingface.co/api/spaces/{space_id}/logs/{log_type}"
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            count = 0
            for line in response:
                decoded = line.decode('utf-8').strip()
                if not decoded or not decoded.startswith('data: '): continue
                try:
                    data = json.loads(decoded[6:])
                    print(f"[{data.get('timestamp')}] {data.get('data', '').strip()}", flush=True)
                except:
                    pass
                count += 1
                if count >= lines: break
    except Exception as e:
        print(f"Error fetching logs: {e}", flush=True)

if __name__ == "__main__":
    token = os.environ.get("HF_TOKEN", "")
    space = "Foadian/UNFINIT"
    l_type = "run"
    if len(sys.argv) > 1: l_type = sys.argv[1]
    get_hf_logs(token, space, l_type)
