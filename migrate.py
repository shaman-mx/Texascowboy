# migrate.py
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime

DATA_FILE = "data.json"
HOUR_FILE = "hour.json"

def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []

def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def migrate_group_contiguous_by_first_card():
    raw = load_json(DATA_FILE)
    if not raw:
        print("No data to migrate.")
        return

    new_rounds = []
    i = 0
    n = len(raw)

    while i < n:
        r = raw[i]
        # If already new schema (selected_boxes list) -> copy as-is
        if isinstance(r.get("selected_boxes"), list):
            new_rounds.append({
                "round_id": r.get("round_id") or str(uuid.uuid4()),
                "first_card": r.get("first_card"),
                "selected_boxes": r.get("selected_boxes"),
                "timestamp": r.get("timestamp")
            })
            i += 1
            continue

        # If record has round_id -> group by round_id
        if r.get("round_id"):
            rid = r["round_id"]
            boxes = set()
            first_card = r.get("first_card")
            ts = r.get("timestamp")
            j = i
            while j < n and raw[j].get("round_id") == rid:
                sb = raw[j].get("selected_box")
                if sb:
                    boxes.add(sb)
                if not ts and raw[j].get("timestamp"):
                    ts = raw[j].get("timestamp")
                j += 1
            new_rounds.append({
                "round_id": rid,
                "first_card": first_card,
                "selected_boxes": list(boxes),
                "timestamp": ts
            })
            i = j
            continue

        # Fallback: group consecutive records with same first_card
        first_card = r.get("first_card")
        boxes = set()
        ts = r.get("timestamp")
        j = i
        while j < n and raw[j].get("first_card") == first_card:
            sb = raw[j].get("selected_box")
            if sb:
                boxes.add(sb)
            if not ts and raw[j].get("timestamp"):
                ts = raw[j].get("timestamp")
            j += 1
        new_rounds.append({
            "round_id": str(uuid.uuid4()),
            "first_card": first_card,
            "selected_boxes": list(boxes),
            "timestamp": ts
        })
        i = j

    # backup original and write new data.json
    backup_path = DATA_FILE + ".bak"
    os.rename(DATA_FILE, backup_path)
    save_json(DATA_FILE, new_rounds)
    print(f"Migrated {n} records -> {len(new_rounds)} rounds. Backup saved to {backup_path}")

    # rebuild hour.json from new rounds
    rebuild_hour_from_rounds(new_rounds)

def rebuild_hour_from_rounds(rounds):
    hour = {"aa": {}, "four_kind": {}}
    for r in rounds:
        slot = r.get("timestamp") or datetime.now().strftime("%H:%M")
        slot_key = slot if isinstance(slot, str) and len(slot) >= 4 else datetime.now().strftime("%H:%M")
        boxes = set(r.get("selected_boxes") or [])
        card = r.get("first_card")
        if not card:
            continue
        if "aa" in boxes:
            hour.setdefault("aa", {}).setdefault(slot_key, []).append(card)
        if "four_kind" in boxes:
            hour.setdefault("four_kind", {}).setdefault(slot_key, []).append(card)
    if os.path.exists(HOUR_FILE):
        os.rename(HOUR_FILE, HOUR_FILE + ".bak")
    save_json(HOUR_FILE, hour)
    print(f"Rebuilt {HOUR_FILE} from rounds. Backup saved to {HOUR_FILE + '.bak'}")

if __name__ == "__main__":
    print("** RUNNING MIGRATION ** — make sure you backed up files before proceeding.")
    migrate_group_contiguous_by_first_card()