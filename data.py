# analyze_rounds.py
import json
from typing import List, Dict, Tuple

DATA_FILE = "data.json"
TOP_KEYS = {"cowboy_win", "draw", "bull_win"}
RIGHT_KEYS = {"high_onepair", "two_pair", "trips", "full_house", "four_kind"}
FOUR_KIND_KEY = "four_kind"

def load_data(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def analyze(data: List[Dict]):
    total = len(data)

    # top stats
    top_at_least_one = 0
    top_exactly_one = 0
    top_more_than_one = 0
    top_none = 0

    # right stats
    right_at_least_one = 0
    right_exactly_one = 0
    right_more_than_one = 0
    right_none = 0

    # combined categories
    both_none = 0  # neither top nor right

    # lists of rounds: (line_number, round_id)
    missing_top: List[Tuple[int, str]] = []
    missing_right: List[Tuple[int, str]] = []
    missing_both: List[Tuple[int, str]] = []
    multi_top: List[Tuple[int, str]] = []   # rounds with >1 top
    multi_right: List[Tuple[int, str]] = [] # rounds with >1 right
    has_four_kind: List[Tuple[int, str]] = []  # rounds containing four_kind

    for idx, r in enumerate(data, start=1):
        sbs = r.get("selected_boxes") or []
        sbs_set = set(sbs)  # remove duplicates if any

        round_id = r.get("round_id", f"line-{idx}")

        top_selected = [k for k in sbs_set if k in TOP_KEYS]
        right_selected = [k for k in sbs_set if k in RIGHT_KEYS]

        # top counts
        n_top = len(top_selected)
        if n_top == 0:
            top_none += 1
            missing_top.append((idx, round_id))
        elif n_top == 1:
            top_exactly_one += 1
            top_at_least_one += 1
        else:
            top_more_than_one += 1
            top_at_least_one += 1
            multi_top.append((idx, round_id))

        # right counts
        n_right = len(right_selected)
        if n_right == 0:
            right_none += 1
            missing_right.append((idx, round_id))
        elif n_right == 1:
            right_exactly_one += 1
            right_at_least_one += 1
        else:
            right_more_than_one += 1
            right_at_least_one += 1
            multi_right.append((idx, round_id))

        # four_kind presence
        if FOUR_KIND_KEY in sbs_set:
            has_four_kind.append((idx, round_id))

        # both none
        if n_top == 0 and n_right == 0:
            both_none += 1
            missing_both.append((idx, round_id))

    return {
        "total_rounds": total,
        "top": {
            "at_least_one": top_at_least_one,
            "exactly_one": top_exactly_one,
            "more_than_one": top_more_than_one,
            "none": top_none,
            "missing_list": missing_top,
            "multi_list": multi_top,
        },
        "right": {
            "at_least_one": right_at_least_one,
            "exactly_one": right_exactly_one,
            "more_than_one": right_more_than_one,
            "none": right_none,
            "missing_list": missing_right,
            "multi_list": multi_right,
        },
        "four_kind": {
            "count": len(has_four_kind),
            "list": has_four_kind
        },
        "both_none": {
            "count": both_none,
            "missing_list": missing_both
        }
    }

def print_report(stats):
    total = stats["total_rounds"]
    print(f"Total rounds: {total}\n")

    top = stats["top"]
    right = stats["right"]
    fk = stats["four_kind"]
    both = stats["both_none"]

    print("TOP group (cowboy_win, draw, bull_win):")
    print(f"  rounds with at least one top: {top['at_least_one']}")
    print(f"  rounds with exactly one top: {top['exactly_one']}")
    print(f"  rounds with more than one top: {top['more_than_one']}")
    print(f"  rounds with NO top: {top['none']}")
    print()
    if top["multi_list"]:
        print("Rounds WITH MORE THAN ONE TOP (line, round_id):")
        for line, rid in top["multi_list"]:
            print(f"   {line:4d}  {rid}")
        print()
    else:
        print("No rounds with more than one top.\n")

    print("-> list of rounds WITHOUT top (line, round_id):")
    for line, rid in top["missing_list"]:
        print(f"   {line:4d}  {rid}")
    print()

    print("RIGHT group (high_onepair, two_pair, trips, full_house, four_kind):")
    print(f"  rounds with at least one right: {right['at_least_one']}")
    print(f"  rounds with exactly one right: {right['exactly_one']}")
    print(f"  rounds with more than one right: {right['more_than_one']}")
    print(f"  rounds with NO right: {right['none']}")
    print()
    if right["multi_list"]:
        print("Rounds WITH MORE THAN ONE RIGHT (line, round_id):")
        for line, rid in right["multi_list"]:
            print(f"   {line:4d}  {rid}")
        print()
    else:
        print("No rounds with more than one right.\n")

    print("-> list of rounds WITHOUT right (line, round_id):")
    for line, rid in right["missing_list"]:
        print(f"   {line:4d}  {rid}")
    print()

    print("Rounds containing FOUR_KIND:")
    print(f"  count: {fk['count']}")
    if fk["list"]:
        print("  -> list (line, round_id):")
        for line, rid in fk["list"]:
            print(f"   {line:4d}  {rid}")
    else:
        print("  No rounds with four_kind found.")
    print()

    print("Rounds with NEITHER top nor right:")
    print(f"  count: {both['count']}")
    if both["missing_list"]:
        print("  -> list (line, round_id):")
        for line, rid in both["missing_list"]:
            print(f"   {line:4d}  {rid}")
    print()

if __name__ == "__main__":
    data = load_data(DATA_FILE)
    stats = analyze(data)
    print_report(stats)