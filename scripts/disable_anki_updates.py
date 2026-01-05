#!/usr/bin/env python3
"""Update prefs21.db to disable Anki update checks."""
import pickle
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / "tests/fixtures/anki/prefs21.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get the _global profile data
cursor.execute("SELECT data FROM profiles WHERE name = '_global'")
row = cursor.fetchone()
data_blob = row[0]

# Decode the pickle
prefs = pickle.loads(data_blob)
print(f"Current prefs: {prefs}")

# Disable updates
prefs['updates'] = False
prefs['suppressUpdate'] = True

# Re-encode
new_blob = pickle.dumps(prefs, protocol=2)

# Update the database
cursor.execute("UPDATE profiles SET data = ? WHERE name = '_global'", (new_blob,))
conn.commit()
conn.close()

print(f"Updated prefs: {prefs}")
print("✓ Disabled update checks in prefs21.db")
