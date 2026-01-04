import sys
import time

import requests

ANKI_URL = "http://localhost:8765"
MAX_RETRIES = 30
DELAY = 1


def check_anki():
    try:
        response = requests.post(ANKI_URL, json={"action": "version", "version": 6}, timeout=1)
        if response.status_code == 200:
            print(f"Anki is ready! Version: {response.json()}")
            return True
    except requests.exceptions.RequestException:
        pass
    return False


def main():
    print(f"Waiting for Anki at {ANKI_URL}...")
    for i in range(MAX_RETRIES):
        if check_anki():
            sys.exit(0)
        time.sleep(DELAY)
        print(f"Retry {i + 1}/{MAX_RETRIES}...")

    print("Timed out waiting for Anki.")
    sys.exit(1)


if __name__ == "__main__":
    main()
