---
"anki_template_version": 1
deck: ObsiAnki-Test
model: Basic
cards:
- id: test-card-1
  Front: What is the primary benefit of the **Apy** backend?
  Back: It accesses the Anki database directly, providing significantly faster synchronization than AnkiConnect.
  nid: '1767551647248'
  cid: '1767551647248'
- id: test-card-2
  Front: How do **Parallel Workers** improve sync performance?
  Back: They allow multiple cards to be processed and synced concurrently, reducing the total time taken for large batches.
  nid: '1767551647215'
  cid: '1767551647215'
- id: test-card-3
  model: Cloze
  Text: |-
    ObsiAnki uses a {{c1::Producer-Consumer}} model with {{c2::asyncio.Queue}} to handle parallel synchronization.
- id: test-card-4
  Front: Why is **asyncio** used for parallelism in ObsiAnki?
  Back: To efficiently handle I/O-bound tasks (like HTTP requests to AnkiConnect) without blocking the main execution thread.
  nid: '1767552228179'
  cid: '1767552228179'
- id: test-card-5
  Front: What happens if **Anki is closed** when using the `apy` backend?
  Back: The sync still works! `apy` reads and writes to the database files directly.
  nid: '1767552228418'
  cid: '1767552228418'
- id: test-card-6
  Front: Where can I find the **Parallel Workers** setting in Obsidian?
  Back: In the ObsiAnki settings tab, next to the Backend selection dropdown.
  nid: '1767552228448'
  cid: '1767552228448'
- id: test-card-7
  Front: Does increasing workers always make it faster?
  Back: Up to a point. High concurrency can speed up network-bound tasks, but setting it too high (e.g., >8) may cause overhead or rate-limiting in AnkiConnect.
  nid: '1767552228482'
  cid: '1767552228482'
- id: test-card-8
  model: Cloze
  Text: |-
    The default number of parallel workers in ObsiAnki is {{c1::4}}.
  nid: '1767552228514'
  cid: '1767552228514'
---
# ObsiAnki Performance Test Note 🚀

This note contains a set of test cards to help you verify the new performance features.

## Testing Instructions:
1.  **Open the Mock Vault** in Obsidian.
2.  Enable the **ObsiAnki** plugin.
3.  Go to **Settings -> ObsiAnki**.
4.  Set **Anki Backend** to `Apy` or `AnkiConnect`.
5.  Set **Parallel Workers** to `8` (to see the speed!).
6.  Click the **Sync Icon** in the sidebar.

Watch the progress bar! With 8 cards and parallel workers, it should be near-instant.
