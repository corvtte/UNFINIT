import urllib.request
import json
import time
import sys

def poll_gha():
    url = 'https://api.github.com/repos/corvtte/UNFINIT/actions/runs'
    headers = {'User-Agent': 'Mozilla/5.0'}
    max_retries = 30 # 30 * 10 seconds = 5 minutes
    
    # Get current run id which might be queued or in_progress
    current_run_id = None
    print("Checking for new workflow run...")
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                if 'workflow_runs' in data and len(data['workflow_runs']) > 0:
                    run = data['workflow_runs'][0]
                    # We expect a run in 'queued' or 'in_progress' state right after a push
                    current_run_id = run['id']
                    print(f"Found run ID: {current_run_id}, Status: {run['status']}")
                    break
        except Exception as e:
            print('Error fetching initial status:', e)
        time.sleep(3)
        
    if not current_run_id:
        print("Could not find a workflow run.")
        return
        
    print("Polling for completion...")
    for i in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                if 'workflow_runs' in data:
                    for run in data['workflow_runs']:
                        if run['id'] == current_run_id:
                            if run['status'] == 'completed':
                                print(f"Workflow completed with conclusion: {run['conclusion']}")
                                return
                            else:
                                print(f"[{i+1}/{max_retries}] Status: {run['status']}...")
                                break
        except Exception as e:
            print('Error polling:', e)
        time.sleep(10)
        
    print("Polling timed out.")

poll_gha()
