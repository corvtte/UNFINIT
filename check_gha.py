import urllib.request
import json

def check_gha():
    url = 'https://api.github.com/repos/corvtte/UNFINIT/actions/runs'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if 'workflow_runs' in data and len(data['workflow_runs']) > 0:
                run = data['workflow_runs'][0]
                print(f"Status: {run['status']}, Conclusion: {run['conclusion']}, Name: {run['name']}")
    except Exception as e:
        print('Error:', e)

check_gha()
