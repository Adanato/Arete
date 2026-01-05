import subprocess
import sys
from pathlib import Path

import pytest
import requests

ANKI_URL = "http://localhost:8765"


@pytest.fixture(scope="session")
def anki_url():
    """Returns the URL of the Dockerized Anki instance."""
    return ANKI_URL


@pytest.fixture(scope="session")
def anki_media_dir():
    """Returns the path to the Docker bind-mount media dir on the host."""
    # This is relative to the repo root where docker-compose is.
    # Assuming tests run from repo root.
    p = Path("docker/anki_data/.local/share/Anki2/User 1/collection.media").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture(scope="session")
def check_anki_available(anki_url):
    """
    Skips all integration tests if Anki is not reachable.
    """
    try:
        requests.post(anki_url, json={"action": "version", "version": 6}, timeout=2)
    except requests.ConnectionError:
        pytest.skip(f"Anki not available at {anki_url}. Is the Docker container running?")


@pytest.fixture
def test_deck():
    return "IntegrationTest"


@pytest.fixture
def setup_anki(check_anki_available, anki_url, test_deck):
    """
    Ensures a clean state for the test deck.
    """
    # Create Custom Model for Pruning (with nid field)
    requests.post(
        anki_url,
        json={
            "action": "createModel",
            "version": 6,
            "params": {
                "modelName": "O2A_Basic",
                "inOrderFields": ["Front", "Back", "nid"],
                "cardTemplates": [
                    {
                        "Name": "Card 1",
                        "Front": "{{Front}}",
                        "Back": (
                            "{{Front}}<hr id=answer>{{Back}}<div style='display:none'>{{nid}}</div>"
                        ),
                    }
                ],
            },
        },
    )

    # Create Deck if not exists
    requests.post(
        anki_url, json={"action": "createDeck", "version": 6, "params": {"deck": test_deck}}
    )

    # Empty it (delete all cards in it)
    # 1. Find cards
    resp = requests.post(
        anki_url,
        json={"action": "findNotes", "version": 6, "params": {"query": f"deck:{test_deck}"}},
    )
    notes = resp.json().get("result", [])

    if notes:
        # 2. Delete them
        requests.post(
            anki_url, json={"action": "deleteNotes", "version": 6, "params": {"notes": notes}}
        )

    yield

    # Cleanup (Optional: leave it for inspection? currently leaving it)


@pytest.fixture
def run_o2a():
    """
    Fixture that returns a function to run the o2a CLI.
    """

    def _run(tmp_path, anki_url, args=None, capture_output=True):
        cmd = [
            sys.executable,
            "-m",
            "o2a.main",
            "-v",
            "sync",
            str(tmp_path),
            "--anki-connect-url",
            anki_url,
        ]
        if args:
            cmd.extend(args)

        print(f"DEBUG running: {cmd}")
        res = subprocess.run(cmd, capture_output=capture_output, text=True)
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
        return res

    return _run
