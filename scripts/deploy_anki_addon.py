import os
import platform
import shutil
import sys


def get_anki_addon_dir():
    system = platform.system()
    if system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support/Anki2/addons21")
    elif system == "Windows":
        base = os.path.join(os.getenv("APPDATA"), "Anki2", "addons21")
    elif system == "Linux":
        base = os.path.expanduser("~/.local/share/Anki2/addons21")
    else:
        print(f"Unsupported system: {system}")
        sys.exit(1)

    if not os.path.exists(base):
        print(f"Anki add-on directory not found at: {base}")
        # Try finding it? Or just error.
        sys.exit(1)

    return base


def deploy():
    addon_dir = get_anki_addon_dir()
    # The folder name in addons21. Let's call it "arete_sync" or match current folder name
    target_name = "arete_ankiconnect"
    target_path = os.path.join(addon_dir, target_name)

    source_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "arete_ankiconnect")
    )

    if not os.path.exists(source_path):
        print(f"Source plugin not found at: {source_path}")
        sys.exit(1)

    print("Deploying Anki add-on...")
    print(f"Source: {source_path}")
    print(f"Target: {target_path}")

    if os.path.exists(target_path):
        shutil.rmtree(target_path)

    shutil.copytree(source_path, target_path)
    print("Deployment successful!")
    print("Please RESTART Anki for changes to take effect.")


if __name__ == "__main__":
    deploy()
