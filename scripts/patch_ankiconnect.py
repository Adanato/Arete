import os


def force_patch_ankiconnect():
    base = os.path.expanduser("~/Library/Application Support/Anki2/addons21/2055492159/__init__.py")
    if not os.path.exists(base):
        print(f"AnkiConnect not found at {base}")
        return

    with open(base, encoding="utf-8") as f:
        content = f.read()

    # Define the verbose method clearly
    verbose_method = """
    @util.api()
    def getFSRSStats(self, cards=None):
        if cards is None:
            cards = []
        result = []
        # Debug: Access collection
        try:
            col = self.collection()
            if not col:
                return [{"error": "Collection is None", "cardId": -1}]
        except Exception as e:
            return [{"error": f"Collection access failed: {e}", "cardId": -1}]

        for cid in cards:
            item = {"cardId": cid, "difficulty": None, "debug": []}
            try:
                # Force int conversion
                try:
                    cid = int(cid)
                except:
                    item["debug"].append(f"Invalid CID type: {type(cid)}")
                card = None
                try:
                    card = col.getCard(cid)
                except AttributeError:
                    try:
                        card = col.get_card(cid)
                    except AttributeError:
                         item["debug"].append("No get_card or getCard method")
                except Exception as e:
                     item["debug"].append(f"get_card exception: {e}")
                if not card:
                    item["debug"].append("Card not found")
                    result.append(item)
                    continue
                # Check attributes
                found_data = False
                if hasattr(card, 'memory_state'):
                    item["debug"].append("Has memory_state")
                    if card.memory_state:
                         item["difficulty"] = card.memory_state.difficulty
                         item["source"] = "memory_state"
                         found_data = True
                    else:
                         item["debug"].append("memory_state is None/Falsey")
                else:
                    item["debug"].append("No memory_state attr")

                if not found_data:
                    if hasattr(card, 'data'):
                         item["debug"].append("Has data")
                         if card.data:
                            try:
                                import json
                                data = json.loads(card.data)
                                if 'd' in data:
                                    item["difficulty"] = data['d']
                                    item["source"] = "data_json"
                                else:
                                    item["debug"].append(f"No 'd' in keys: {list(data.keys())}")
                            except Exception as e:
                                item["debug"].append(f"JSON parse error: {e}")
                         else:
                             item["debug"].append("Data empty")
                    else:
                        item["debug"].append("No data attr")

                result.append(item)
            except Exception as e:
                result.append({"cardId": cid, "error": f"Outer loop error: {e}"})
        return result
"""

    # STRATEGY:
    # 1. Remove ANY existing implementation of getFSRSStats by splitting.
    # 2. Append the new one before the entry point.

    # 1. Remove old implementation if present
    # We look for the decorator or the def.
    # The file structure is: Class ... methods ... [Our Method] ... Entry Point.

    # Let's find the Entry Point
    entry_marker = "\n#\n# Entry\n#"
    if entry_marker not in content:
        # fallback
        entry_marker = '\nif __name__ != "plugin":'

    if entry_marker not in content:
        print("CRITICAL: Could not find entry marker in file. Aborting to avoid corrupting.")
        return

    # Split into Top and Bottom (Top contains Class, Bottom contains Entry)
    parts = content.split(entry_marker)
    top = parts[0]
    # Reassemble bottom if split multiple times (unlikely)
    bottom = entry_marker + "".join(parts[1:])

    # Now clean up `top`. If it has `def getFSRSStats`, truncate it BEFORE that.
    if "def getFSRSStats" in top:
        # Find where it starts.
        # It usually starts with @util.api()
        clean_top = top.split("def getFSRSStats")[0]
        # Remove the @util.api() line preceding it if we can find it.
        # This is simple string manipulation.
        clean_top = clean_top.rsplit("@util.api()", 1)[0]
        print("Removed existing getFSRSStats from top part.")
        top = clean_top

    # Reassemble: Top + New Method + Bottom
    new_content = top.rstrip() + "\n\n" + verbose_method + "\n" + bottom

    with open(base, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("Force patched AnkiConnect successfully.")


if __name__ == "__main__":
    force_patch_ankiconnect()
