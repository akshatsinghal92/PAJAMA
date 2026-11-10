"""Independent reviewer (optional extra in the plan) — Haiku applies the production judge's criteria WITHOUT seeing the
intended label. Disagreements flag pairs the production judge may label differently.
NOTE: this is a Haiku proxy, NOT the production judge; it is a quality signal, not a replacement for step 4.
Usage: s6_review.py submit|collect pilot|main [--wait]
"""
import json
import sys

from common import WORK, collect_batch, load_results, parse_json, submit_batch

PER_CALL = 20

SYSTEM = """You are evaluating whether a USDA food database entry is an acceptable match for a recipe ingredient.

A match counts as "substitutable" if and only if BOTH conditions hold:
  1. It could be used in place of the ingredient without changing how the dish is prepared.
  2. A person eating the dish would not notice any difference in taste, texture, or appearance.

If the match would alter cooking method, change the dish's flavour, texture, or appearance, or if a diner would notice they were eating something different, it is not substitutable.

You will be given several (ingredient, USDA match) pairs. Judge EACH pair independently and strictly by the two conditions above. Reply with JSON only, no markdown:
{"results": [{"id": "<pair id>", "substitutable": true_or_false, "why": "<=12 words"}]}"""


def load_pairs(name):
    return [p for p in json.loads((WORK / f"s3_{name}_pairs.json").read_text()) if p["snapped"]]


def submit(name):
    pairs = load_pairs(name)
    items = []
    for ci in range(0, len(pairs), PER_CALL):
        chunk = pairs[ci: ci + PER_CALL]
        lines = [f'id {ci + j}: Ingredient: "{p["ingredient_q"]}" | USDA match: "{p["usda_match"]}"' for j, p in enumerate(chunk)]
        items.append({"id": f"rv-{name}-{ci // PER_CALL:04d}", "user": "Pairs:\n" + "\n".join(lines), "max_tokens": 6000})
    if "--sync" in sys.argv:
        from common import run_sync
        run_sync(f"s6_{name}", SYSTEM, items, effort="medium")
        process(name)
    else:
        submit_batch(f"s6_{name}", SYSTEM, items, effort="medium")


def process(name):
    pairs = load_pairs(name)
    lab = {}
    for r in load_results(f"s6_{name}"):
        if r["status"] != "succeeded":
            continue
        obj = parse_json(r["text"])
        for it in (obj.get("results", []) if isinstance(obj, dict) else []):
            try:
                lab[int(str(it["id"]).replace("id", "").strip())] = (1 if it["substitutable"] in (True, "true", "True") else 0, str(it.get("why", ""))[:100])
            except Exception:
                pass
    out, agree, n = [], 0, 0
    for i, p in enumerate(pairs):
        q = dict(p)
        if i in lab:
            q["review"], q["review_why"] = lab[i]
            q["disputed"] = int(q["review"] != q["intended"])
            n += 1
            agree += 1 - q["disputed"]
        else:
            q["review"], q["review_why"], q["disputed"] = None, "", None
        out.append(q)
    (WORK / f"s6_{name}_pairs.json").write_text(json.dumps(out, indent=1))
    print(f"{name}: reviewed {n}/{len(pairs)}; agreement with intended label {agree/max(1,n):.1%}")
    import collections as C
    by = C.defaultdict(lambda: [0, 0])
    for q in out:
        if q["disputed"] is not None:
            by[q["level"]][0] += 1
            by[q["level"]][1] += q["disputed"]
    print("disputed by level:", {k: f"{b}/{a} ({b/a:.0%})" for k, (a, b) in sorted(by.items())})


if __name__ == "__main__":
    cmd, name = sys.argv[1], sys.argv[2]
    if cmd == "submit":
        submit(name)
    elif cmd == "collect":
        if collect_batch(f"s6_{name}", wait="--wait" in sys.argv) is not None:
            process(name)
    elif cmd == "process":
        process(name)
