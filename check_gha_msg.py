import urllib.request
import json
url = 'https://api.github.com/repos/corvtte/UNFINIT/actions/runs'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        run = data['workflow_runs'][0]
        print(f"Message: {run['head_commit']['message']}")
        print(f"Status: {run['status']}, Conclusion: {run['conclusion']}")
except Exception as e:
    print('Error:', e)
