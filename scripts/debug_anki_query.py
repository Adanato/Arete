import json

import requests


def invoke(action, **params):
    return requests.post(
        "http://localhost:8765", json={"action": action, "version": 6, "params": params}
    ).json()


# 1. Find a valid note ID
print("Finding a note...")
notes = invoke("findNotes", query="dict:en*")  # Try to find some notes, fallback to all
if not notes["result"]:
    notes = invoke("findNotes", query="*:*")

if not notes["result"]:
    print("No notes found in Anki.")
    exit(1)

nid = notes["result"][0]
print(f"Testing with Note ID: {nid}")

# 2. Find cards for this note
print("Finding cards...")
res = invoke("findCards", query=f"nid:{nid}")
card_ids = res["result"]
print(f"Card IDs: {card_ids}")

if not card_ids:
    print("No cards found for this note.")
    exit(1)

# 3. Get cards info
print("Fetching cardsInfo...")
info = invoke("cardsInfo", cards=card_ids)
result = info["result"][0]

print("Keys in cardsInfo result:")
print(json.dumps(list(result.keys()), indent=2))

print(f"Value of 'note': {result.get('note')}")
print(f"Value of 'noteId': {result.get('noteId')}")
