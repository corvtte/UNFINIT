import os
import zipfile
import platform
import string

def get_drive_paths():
    if platform.system() == "Windows":
        drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        return drives
    return ["/"]

def find_google_drive():
    drives = get_drive_paths()
    for drive in drives:
        # standard G Drive path
        g_path = os.path.join(drive, "My Drive")
        if os.path.exists(g_path):
            return g_path
        
        # sometimes it's named 'Google Drive' inside a drive
        g_path2 = os.path.join(drive, "Google Drive")
        if os.path.exists(g_path2):
            return g_path2
            
        g_path3 = os.path.join(drive, "Google Drive", "My Drive")
        if os.path.exists(g_path3):
            return g_path3
            
    # Default fallback
    return os.path.join(os.path.expanduser("~"), "Google Drive")

def should_ignore(file_path):
    # Normalized for forward slashes
    norm_path = file_path.replace('\\', '/')
    
    ignore_patterns = [
        '/.git/',
        '/.venv/',
        '/__pycache__/',
        '/.env',
        '.session',
        '.db',
        '/data/unfinit.db',
        '/data/abasmanesh_session.json',
        '/data/crawler_cache.json',
        '/data/custom_categories.json',
        '.pyc',
        '.pyo'
    ]
    
    # Also ignore anything inside node_modules if present
    if '/node_modules/' in norm_path:
        return True
        
    for pat in ignore_patterns:
        if pat in norm_path or norm_path.endswith(pat.lstrip('/')):
            return True
            
    # Explicitly ignore files named exactly .env
    if os.path.basename(norm_path) == '.env':
        return True
        
    return False

def package_project():
    print("Finding Google Drive...")
    g_drive = find_google_drive()
    target_dir = os.path.join(g_drive, "UNFINIT_PROJECT_CURRENT")
    
    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create directory in Google Drive: {e}")
        print("Will attempt to save in local directory first.")
        target_dir = os.getcwd()
        
    zip_path = os.path.join(target_dir, "unfinit_v0.7.27.zip")
    local_temp_zip = "unfinit_v0.7.27.zip"
    
    print(f"Packaging project to {zip_path}...")
    
    base_path = os.getcwd()
    
    with zipfile.ZipFile(local_temp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(base_path):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d))]
            
            for f in files:
                full_path = os.path.join(root, f)
                if not should_ignore(full_path) and f != "unfinit_v0.7.27.zip":
                    arcname = os.path.relpath(full_path, base_path)
                    zf.write(full_path, arcname)
                    
    print("Project packaged successfully.")
    
    # Move to Google Drive
    if target_dir != os.getcwd():
        try:
            import shutil
            shutil.move(local_temp_zip, zip_path)
            print(f"Successfully moved to Google Drive: {zip_path}")
        except Exception as e:
            print(f"Error moving to Google Drive: {e}")
            print(f"File left at: {os.path.abspath(local_temp_zip)}")
    else:
        print(f"File saved locally at: {os.path.abspath(local_temp_zip)}")

if __name__ == "__main__":
    package_project()
