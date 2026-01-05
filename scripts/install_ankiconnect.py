import io
import os
import zipfile
from pathlib import Path

import requests

# AnkiConnect ID and GitHub URL
ADDON_ID = "2055492159"
DOWNLOAD_URL = "https://github.com/FooSoft/anki-connect/releases/latest/download/AnkiConnect.zip"
# Fallback if specific release needed, usually "AnkiConnect.zip" is in assets.
# Actually, FooSoft/anki-connect releases often just have source code. 
# Let's check a known stable download or standard AnkiWeb link (harder to script).
# Better to use the source code from master if no built artifact, 
# BUT AnkiConnect source IS the addon.
# Let's try downloading the repo zip.
REPO_ZIP_URL = "https://github.com/FooSoft/anki-connect/archive/refs/heads/master.zip"

def install_ankiconnect():
    # Install to the GLOBAL Anki addons directory (not per-profile)
    # The correct path is /config/.local/share/Anki2/addons21/ (NOT User 1/addons21)
    paths = [
        Path(__file__).parent.parent / "docker/anki_data/.local/share/Anki2/addons21" / ADDON_ID,
    ]

    for target_dir in paths:
        print(f"Checking {target_dir}...")
        if target_dir.exists():
            print(f"AnkiConnect already exists at {target_dir}.")
            continue
            
        target_dir.mkdir(parents=True, exist_ok=True)

    # Download once
    print(f"Downloading from {REPO_ZIP_URL}...")
    response = requests.get(REPO_ZIP_URL)
    response.raise_for_status()
    zip_content = response.content

    for target_dir in paths:
        # Check if empty (we just created it or it existed)
        if any(target_dir.iterdir()):
             continue # Already populated

        print(f"Extracting to {target_dir}...")
        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            for member in z.namelist():
                if "plugin/" in member and not member.endswith("/"):
                    relative_path = member.split("plugin/", 1)[1]
                    if not relative_path: continue
                    dest_path = target_dir / relative_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(member) as source, open(dest_path, "wb") as target:
                        target.write(source.read())

        # Config
        config_file = target_dir / "config.json"
        with open(config_file, "w") as f:
            # webBindAddress MUST be 0.0.0.0 for Docker container to receive external traffic
            # webCorsOriginList: Allow all origins to prevent CORS issues
            f.write('{"apiKey": null, "apiLogPath": null, "webBindAddress": "0.0.0.0", "webBindPort": 8765, "webCorsOriginList": ["*"]}')
        print(f"Configured AnkiConnect at {target_dir}")

    # Seed 'prefs21.db' to skip First Run Wizard
    # The container runs as user 1000 (abc), mapping $HOME to /config (which is docker/anki_data)
    # Location: docker/anki_data/.local/share/Anki2/prefs21.db
    fixture_path = Path(__file__).parent.parent / "tests/fixtures/anki/prefs21.db"
    if fixture_path.exists():
        print("Seeding Anki preferences (bypassing wizard)...")
        anki_base = Path(__file__).parent.parent / "docker/anki_data"
        prefs_dir = anki_base / ".local/share/Anki2"
        prefs_dir.mkdir(parents=True, exist_ok=True)
        
        import shutil
        shutil.copy(fixture_path, prefs_dir / "prefs21.db")
        print(f"Copied {fixture_path.name} to {prefs_dir}")
    else:
        print(f"⚠️ Warning: Fixture {fixture_path} not found. Anki may show setup wizard.")

    # Create collection.media directory for media files
    media_dir = Path(__file__).parent.parent / "docker/anki_data/.local/share/Anki2/User 1/collection.media"
    media_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created media directory: {media_dir}")
        
    # Ensure permissive permissions for Docker user (uid 1000)
    print("Fixing permissions...")
    start_dir = Path(__file__).parent.parent / "docker/anki_data"
    for root, dirs, files in os.walk(start_dir):
        for d in dirs:
            try:
                os.chmod(os.path.join(root, d), 0o777)
            except OSError:
                pass
        for f in files:
            try:
                os.chmod(os.path.join(root, f), 0o666)
            except OSError:
                pass
    print("Permissions set to 777/666 for anki_data.")

if __name__ == "__main__":
    install_ankiconnect()
