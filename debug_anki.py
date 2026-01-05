import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure src is in python path so we can import arete
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root / "src"))

import platform  # noqa: E402
import shutil  # noqa: E402

# Setup Logging to Console
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("debug_anki")


async def async_main():
    print("=" * 60)
    print("  AnkiConnect Diagnostic Tool")
    print("=" * 60)

    # 1. Environment Diagnostics
    print("\n[Environment]")
    print(f"  OS: {platform.system()} {platform.release()}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  CWD: {os.getcwd()}")

    # Check WSL
    is_wsl = "microsoft" in platform.uname().release.lower()
    print(f"  WSL Detected: {is_wsl}")

    # Check curl.exe
    curl_path = shutil.which("curl.exe")
    print(f"  curl.exe found: {curl_path if curl_path else 'NO'}")

    # Check Env Var
    env_host = os.environ.get("ANKI_CONNECT_HOST")
    print(f"  ANKI_CONNECT_HOST: {env_host if env_host else 'Not Set'}")

    try:
        from arete.services.anki_connect import AnkiConnectAdapter
    except ImportError as e:
        print(f"\n[Error] Could not import arete: {e}")
        print("Make sure you are running this from the repo root.")
        return

    # 2. Initialize Adapter
    print("\n[Initialization]")
    try:
        # We assume default URL, let the adapter do its magic
        adapter = AnkiConnectAdapter()
        print(f"  Adapter URL: {adapter.url}")
        print(f"  Using Curl Bridge: {getattr(adapter, 'use_windows_curl', False)}")
    except Exception as e:
        print(f"  [Fatal] Failed to init adapter: {e}")
        return

    # 3. Test Connectivity
    print("\n[Connectivity Test]")

    # Test 1: Version (Lightweight)
    print("  > Check Version...")
    try:
        v = await adapter._invoke("version")
        print(f"    [SUCCESS] AnkiConnect Version: {v}")
    except Exception as e:
        print(f"    [FAILURE] Could not get version: {e}")
        print("\nTroubleshooting Tips:")
        if is_wsl:
            print("  - Ensure Anki is open on Windows.")
            if not curl_path and not env_host:
                print(
                    "  - If you don't have curl.exe, ensure AnkiConfig has "
                    "'webBindAddress': '0.0.0.0'"
                )
            if curl_path:
                print("  - curl.exe failed. Is Anki blocking connections?")
        else:
            print("  - Ensure Anki is open and AnkiConnect is installed.")
        return

    # Test 2: Deck Names
    print("  > List Decks...")
    try:
        decks = await adapter.get_deck_names()
        print(f"    [SUCCESS] Found {len(decks)} decks: {decks}")
    except Exception as e:
        print(f"    [FAILURE] Could not list decks: {e}")

    # Test 3: Model Names
    print("  > List Models...")
    try:
        models = await adapter.get_model_names()
        print(f"    [SUCCESS] Found {len(models)} models: {models[:5]}...")
    except Exception as e:
        print(f"    [FAILURE] Could not list models: {e}")

    print("\n[Done]")


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass
