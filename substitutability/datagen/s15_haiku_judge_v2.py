"""Compare Haiku with the verbatim prompt (v1) vs verbatim prompt + guidelines (v2).
Batches: v2 on the 344 dev rows + 120 held-out rows; v1 on the 120 held-out rows.
Usage: s15_haiku_judge_v2.py submit | collect [--wait]"""
import json, sys
from pathlib import Path
from common import collect_batch, load_results, parse_json, submit_batch
from judge_groq import prompt
from judge_guidelines import GUIDELINES
EV = Path("/private/tmp/claude-501/-Users-akshat-Documents/e4ab1802-4b4a-4900-9162-c9d20b9dce66/scratchpad/eval344")
SYS = "You are a careful food-data annotator."
NAME = "s15_haiku_v2"

def items():
    dev = json.load(open(EV / "rows.json")); ho = json.load(open(EV / "heldout.json"))
    out = []
    for i, r in enumerate(dev):
        out.append({"id": f"v2-dev-{i}", "user": prompt(r["ingredient"], r["usda_match"]) + GUIDELINES, "max_tokens": 3000})
    for i, r in enumerate(ho):
        out.append({"id": f"v2-ho-{i}", "user": prompt(r["ingredient"], r["usda_match"]) + GUIDELINES, "max_tokens": 3000})
        out.append({"id": f"v1-ho-{i}", "user": prompt(r["ingredient"], r["usda_match"]), "max_tokens": 3000})
    return out

def labels():
    res = {}
    for r in load_results(NAME):
        if r["status"] != "succeeded": continue
        o = parse_json(r["text"]); v = o.get("substitutable") if isinstance(o, dict) else None
        if isinstance(v, str): v = v.lower() == "true"
        if v is not None: res[r["id"]] = int(bool(v))
    json.dump(res, open(EV / "s15_labels.json", "w"))
    print(len(res), "labels parsed")

if __name__ == "__main__":
    if sys.argv[1] == "submit": submit_batch(NAME, SYS, items(), effort="medium")
    elif sys.argv[1] == "collect":
        if collect_batch(NAME, wait="--wait" in sys.argv) is not None: labels()
