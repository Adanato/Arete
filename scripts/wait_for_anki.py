import os
import sys
import time

import requests

ANKI_URL = os.getenv("ANKI_CONNECT_URL", "http://127.0.0.1:8766")
MAX_RETRIES = 30  # 30 retries * 1 second = 30 seconds max wait
DELAY = 1


def check_anki():
    # Try 127.0.0.1 first, then 0.0.0.0 as fallback for some Mac/OrbStack setups
    urls = [ANKI_URL]
    if "127.0.0.1" in ANKI_URL:
        urls.append(ANKI_URL.replace("127.0.0.1", "0.0.0.0"))

    for url in urls:
        try:
            response = requests.post(url, json={"action": "version", "version": 6}, timeout=1)
            if response.status_code == 200:
                print(f"Anki is ready at {url}! Version: {response.json()}")
                return True
        except requests.exceptions.RequestException:
            continue
    return False


def main():
    print(f"Waiting for Anki (trying {ANKI_URL} and/or 0.0.0.0)...")
    sys.stdout.flush()
    for i in range(MAX_RETRIES):
        if check_anki():
            sys.exit(0)
        time.sleep(DELAY)
        if (i + 1) % 5 == 0:
            print(f"Still waiting... {i + 1}/{MAX_RETRIES} attempts")
            sys.stdout.flush()

    print("Timed out waiting for Anki.")
    sys.exit(1)


if __name__ == "__main__":
    main()
