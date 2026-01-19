#!/usr/bin/env python3
"""
Automate pushing Arete Anki Add-on to AnkiWeb.
Requires: anki-addon-uploader (pip install anki-addon-uploader)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def publish_to_ankiweb(addon_id: str, zip_path: Path):
    """
    Push the zip file to AnkiWeb using anki-addon-uploader.
    """
    user = os.getenv("ANKIWEB_USER")
    password = os.getenv("ANKIWEB_PASS")

    if not user or not password:
        print("Error: ANKIWEB_USER and ANKIWEB_PASS environment variables must be set.")
        sys.exit(1)

    if not zip_path.exists():
        print(f"Error: Zip file not found at {zip_path}")
        sys.exit(1)

    print(f"🚀 Uploading {zip_path.name} to AnkiWeb (ID: {addon_id})...")

    cmd = ["anki-addon-uploader", addon_id, str(zip_path)]

    try:
        # Pass credentials via env to the tool
        env = os.environ.copy()
        result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        print("✅ Successfully uploaded to AnkiWeb!")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("❌ Failed to upload to AnkiWeb:")
        print(e.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Publish Anki Add-on to AnkiWeb")
    # Default ID from env or hardcoded fallback (Arete ID)
    default_id = os.getenv("ANKI_ADDON_ID", "2055492159")
    parser.add_argument("--id", default=default_id, help="AnkiWeb Add-on ID")
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("release_artifacts/arete_ankiconnect.zip"),
        help="Path to .zip or .ankiaddon file",
    )

    args = parser.parse_args()

    print(f"Configured Add-on ID: {args.id}")
    publish_to_ankiweb(args.id, args.file)


if __name__ == "__main__":
    main()
