import json
import random

import requests


def invoke(action, **params):
    return requests.post(
        "http://localhost:8765", json={"action": action, "version": 6, "params": params}
    ).json()


# 1. Get ALL card IDs
print("Fetching all card IDs...")
decks = invoke("deckNames")["result"]
cards = []
for d in decks:
    res = invoke("findCards", query=f'"deck:{d}"')
    if res["result"]:
        cards.extend(res["result"])

print(f"Total cards found: {len(cards)}")

# 2. Sample 100 cards
sample_size = min(100, len(cards))
sample = random.sample(cards, sample_size)
print(f"Scanning sample of {sample_size} cards...")

# 3. Check for FSRS stats
stats = invoke("getFSRSStats", cards=sample)
results = stats.get("result", [])

found_count = 0
for r in results:
    if r.get("difficulty") is not None:
        found_count += 1
        print(f"FOUND DATA for Card {r['cardId']}: Difficulty={r['difficulty']}")

if found_count == 0:
    print("\nRESULT: No FSRS difficulty found in any of the 100 sampled cards.")
    print("Possibilities:")
    print("1. Cards are all 'New' (unreviewed).")
    print("2. FSRS is not enabled or scheduled.")
    print("3. Data is stored in a location  isn't checking.")

    # Print debug info for one failed card to see inspection
    if results:
        print("\nDebug info for first card:")
        print(json.dumps(results[0], indent=2))
else:
    print(f"\nRESULT: Found FSRS data for {found_count}/{sample_size} cards.")
