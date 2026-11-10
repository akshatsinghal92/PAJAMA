"""Step 9 — one LLM audit pass over every candidate row (feedback points 2 and 4):
  (a) realism : would a home-recipe ingredient line plausibly read like this?   (drops scientific/USDA-style/odd lines)
  (b) type    : which pair type is it REALLY, judged blind to the claimed type and label  (re-tags the ~9% misfits)
Usage: s9_audit.py submit | collect [--wait] | process
"""
import collections as C
import json
import sys

from common import WORK, collect_batch, load_results, parse_json, submit_batch
from s2_pairs import TYPE_DESC

TYPE_DESC = dict(TYPE_DESC)
TYPE_DESC["G8"] = "KEEP-MODIFIER: ingredient and USDA entry both carry the same modifier (smoked / toasted / ground / powder / paste / flakes), acceptable swap."
TYPE_DESC["G9"] = "COMPOSITE MATCH: a combined ingredient matched to the same combined USDA food (peas and carrots -> Peas and carrots, canned)."
PER_CALL = 20

SYSTEM = """You audit rows of a dataset that pairs a recipe ingredient line with a USDA FoodData Central entry name.
For EACH row answer two independent questions.

1. realistic: could this ingredient line plausibly appear in an ordinary home-cooking recipe ingredient list (quantity removed)?
   Answer false for: scientific/Latin names; wording copied from the USDA database (e.g. 'greens, dandelion, raw', 'separable lean');
   obscure, archaic or invented names a cook would not use; rare wild game or things that are not purchasable foods; unnatural phrasing.
   Answer true for ordinary, even if uncommon, ingredients written the way a recipe writes them.
   If false give a very short reason.

2. type: which ONE pair type below best describes the relationship between the ingredient line and the USDA entry, judged purely from
   the two strings (you are not told any label). Choose the single best code.

PAIR TYPES
""" + "\n".join(f"{t}: {d}" for t, d in TYPE_DESC.items()) + """

Reply with JSON only, no markdown:
{"results": [{"id": "<row id>", "realistic": true or false, "reason": "<only if false, <=8 words>", "type": "<code>"}]}"""


def build_pool():
    pool = json.loads((WORK / "pool_clean.json").read_text()) + json.loads((WORK / "topup_rows.json").read_text())
    for i, r in enumerate(pool):
        r["rid"] = f"r{i:05d}"
    (WORK / "pool_all.json").write_text(json.dumps(pool, indent=1))
    return pool


def submit():
    pool = build_pool()
    items = []
    for ci in range(0, len(pool), PER_CALL):
        chunk = pool[ci:ci + PER_CALL]
        lines = [f'{r["rid"]}: ingredient "{r["ingredient"]}" | USDA entry "{r["usda_match"]}"' for r in chunk]
        items.append({"id": f"au-{ci // PER_CALL:04d}", "user": "Rows:\n" + "\n".join(lines), "max_tokens": 7000})
    print(f"{len(pool)} rows -> {len(items)} calls")
    submit_batch("s9_audit", SYSTEM, items, effort="medium")


def process():
    pool = json.loads((WORK / "pool_all.json").read_text())
    res = {}
    for r in load_results("s9_audit"):
        if r["status"] != "succeeded":
            continue
        obj = parse_json(r["text"])
        for it in (obj.get("results", []) if isinstance(obj, dict) else []):
            res[str(it.get("id"))] = it
    st = C.Counter()
    for r in pool:
        a = res.get(r["rid"])
        if not a:
            r["audit_realistic"], r["audit_type"] = None, None
            st["unaudited"] += 1
            continue
        r["audit_realistic"] = a.get("realistic") is not False
        r["audit_reason"] = a.get("reason", "")
        r["audit_type"] = a.get("type") if a.get("type") in TYPE_DESC else None
        st["audited"] += 1
        st["unrealistic"] += (not r["audit_realistic"])
    (WORK / "pool_audited.json").write_text(json.dumps(pool, indent=1))
    print(dict(st))
    ex = [r for r in pool if r.get("audit_realistic") is False]
    import random
    random.Random(1).shuffle(ex)
    print("sample of rows judged unrealistic:")
    for r in ex[:14]:
        print(f"   {r['ingredient']!r} -> {r['usda_match']!r}   [{r.get('audit_reason')}]")
    agree = sum(1 for r in pool if r.get("audit_type") == r["type_used"])
    n = sum(1 for r in pool if r.get("audit_type"))
    print(f"blind type agrees with claimed type: {agree}/{n} = {agree/max(1,n):.1%}")
    cm = C.Counter((r["type_used"], r["audit_type"]) for r in pool if r.get("audit_type") and r["audit_type"] != r["type_used"])
    print("most common re-tags (claimed -> blind):", cm.most_common(14))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "submit":
        submit()
    elif cmd == "collect":
        if collect_batch("s9_audit", wait="--wait" in sys.argv) is not None:
            process()
    elif cmd == "process":
        process()
