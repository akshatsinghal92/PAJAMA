"""Step 8 — entry-first top-up for the coverage gaps found by the audit (feedback points 3 and 5).
Pick a REAL FoodData Central entry, then have Haiku write the recipe ingredient line for it. Real USDA string and pair type are
therefore guaranteed by construction.
  MOD   -> G8 : good pair that KEEPS a smoked/toasted/ground/powder/paste/flakes modifier on both sides (breaks the cue)
  COMP  -> G9 : good composite ('peas and carrots' -> 'Peas and carrots, canned')   (breaks the ' and ' => negative cue)
  BRAND -> G7 : good pair, plain product vs branded entry
  VARIANT -> B8 : plain generic ingredient vs a specific non-default variant (bad)
  SYN   -> G6 : good pair, common recipe name with LOW word overlap vs formal/alt-named entry
Usage: s8_topup.py run | process
"""
import collections as C
import json
import random
import re
import sys

from blocklist import core_of
from common import WORK, canon_key, fdc, norm, parse_json, run_sync, strip_qty

SEED = 17
N = {"MOD": 260, "COMP": 90, "BRAND": 100, "VARIANT": 260, "SYN": 240}
TYPE = {"MOD": "G8", "COMP": "G9", "BRAND": "G7", "VARIANT": "B8", "SYN": "G6"}
LABEL = {"MOD": 1, "COMP": 1, "BRAND": 1, "VARIANT": 0, "SYN": 1}
PER_CALL = 25

BAD = re.compile(r"restaurant|sandwich|burger|pizza|salad|soup|casserole|babyfood|baby food|infant|toddler|formula|candy|candies|"
                 r"cookie|cake\b|pie\b|pudding|dessert|snack|fast food|\bmix\b|beverage|energy|alcoholic|entree|dinner|stew|"
                 r"gravy|mcdonald|burger king|taco bell|wendy|domino|subway|alaska native|navajo|hopi|apache|0% moisture|"
                 r"diet|whiskey|cocktail|latte|coffee|smart soup|bar\b|school lunch|kfc|cracker barrel", re.I)
STAPLE = re.compile(r"^(milk|cheese|yogurt|cream|sour cream|mayonnaise|salad dressing|dressing|margarine|butter|juice|soymilk|"
                    r"soy milk|almond milk|peanut butter|jelly|jam|syrup|sausage|bacon|ham|turkey|chicken|beef|pork|beans|"
                    r"tofu|sweeteners|oil|flour|pasta|noodles|rice|bread|tortilla|cereal|oat|granola|hummus|salsa|vinegar|"
                    r"mustard|ketchup|honey|crackers|nuts|seeds|fish|tuna|salmon|shrimp|egg|tomato|potato|pickle|olive|"
                    r"spices|seasoning|broth|bouillon|stock|sauce)", re.I)
MODRE = re.compile(r"\b(smoked|toasted|ground|powder|paste|flakes)\b", re.I)
VARRE = re.compile(r"\b(unsweetened|sweetened|light|lite|lowfat|low fat|reduced fat|fat free|nonfat|low sodium|reduced sodium|"
                   r"sugar free)\b", re.I)


def plain(d):
    return len(d.split()) <= 9 and not BAD.search(d)


def candidates():
    rows = [r for r in fdc() if r["source"] in ("SR_Legacy", "FNDDS", "Foundation")]
    out = {}
    out["MOD"] = [r for r in rows if MODRE.search(r["description"]) and plain(r["description"]) and STAPLE.match(r["description"])]
    out["COMP"] = [r for r in rows if re.search(r"^[A-Za-z ]+ and [A-Za-z ]+(,|$)", r["description"]) and plain(r["description"])
                   and not re.search(r"\bwith\b|meat|fruit and", r["description"], re.I)]
    out["BRAND"] = [r for r in rows if re.search(r"\b[A-Z]{4,}\b", r["description"]) and not BAD.search(r["description"])
                    and len(r["description"].split()) <= 14 and STAPLE.match(re.sub(r"^[A-Z0-9 &'.-]+,\s*", "", r["description"]))]
    out["VARIANT"] = [r for r in rows if VARRE.search(r["description"]) and plain(r["description"]) and STAPLE.match(r["description"])
                      and not re.search(r"salt", r["description"], re.I)]
    out["SYN"] = [r for r in rows if plain(r["description"]) and STAPLE.match(r["description"]) is None or plain(r["description"])]
    out["SYN"] = [r for r in out["SYN"] if (re.search(r"\([^)]*\)", r["description"]) and not re.search(r"includes|NFS|year round|Food Distribution|\d", r["description"]))
                  or re.search(r"^[A-Za-z]+, [a-z ]+ or [a-z ]+", r["description"])]
    return out


INSTR = {
    "MOD": ("Write the recipe ingredient line a cook would use for exactly this USDA entry, KEEPING the key modifier word "
            "(smoked / toasted / ground / powder / paste / flakes) in the ingredient line. The entry must be an acceptable "
            "swap for your line."),
    "COMP": ("The entry is a combined food. Write the combined ingredient line (naming both components, e.g. 'canned peas and carrots') "
             "that this entry exactly matches."),
    "BRAND": ("The entry is a branded product. Write the plain, brand-less ingredient line a recipe would use for this product "
              "(never include the brand name)."),
    "VARIANT": ("The entry is a specific non-default variant (e.g. unsweetened, light, lowfat, reduced sodium). Write the plain, "
                "UNQUALIFIED ingredient line a recipe would use for the ordinary version of this food. Do NOT mention the "
                "qualifier. (A strict diner could notice the difference.)"),
    "SYN": ("The entry has a formal or alternative name. Write the COMMON recipe ingredient line for exactly the same food, "
            "choosing a name that shares as few words with the entry as possible."),
}
SYSTEM = """You write recipe ingredient lines that correspond to real USDA FoodData Central entries, for building a test set.
Rules for every line: no quantity, no brand names (unless told), natural lowercase wording as a home recipe would write it
(e.g. "fresh diced onion", "canned black beans, drained", "smoked paprika"). It must be a food a home cook could actually buy.
Do not copy USDA database wording (no 'NFS', no commas listing database attributes, no 'raw, separable lean').
If the entry cannot produce a natural recipe line, skip it.
Reply with JSON only: {"items": [{"id": "<entry id>", "ingredient": "<line>"} or {"id": "<entry id>", "skip": true}]}"""


def run():
    rng = random.Random(SEED)
    cand = candidates()
    pool = json.loads((WORK / "pool_clean.json").read_text())
    used = C.Counter(norm(r["usda_match"]) for r in pool)
    reqs, meta = [], {}
    for mode, n in N.items():
        c = [r for r in cand[mode] if used[norm(r["description"])] < 3]
        rng.shuffle(c)
        if mode == "MOD":     # stratify across modifier words
            by = C.defaultdict(list)
            for r in c:
                by[MODRE.search(r["description"]).group(1).lower()].append(r)
            c = [x for grp in zip(*[by[k] for k in by if len(by[k]) >= n // len(by)]) for x in grp] if by else c
        c = c[:n]
        print(f"{mode}: {len(cand[mode])} candidates -> using {len(c)}")
        for i in range(0, len(c), PER_CALL):
            chunk = c[i:i + PER_CALL]
            cid = f"top-{mode}-{i // PER_CALL:03d}"
            lines = []
            for j, r in enumerate(chunk):
                eid = f"e{j}"
                lines.append(f'{eid}: "{r["description"]}"')
                meta[(cid, eid)] = {"mode": mode, "usda_match": r["description"], "fdc_id": r["fdc_id"], "fdc_source": r["source"]}
            user = f"MODE: {mode}\n{INSTR[mode]}\n\nUSDA entries:\n" + "\n".join(lines)
            reqs.append({"id": cid, "user": user, "max_tokens": 9000})
    (WORK / "topup_meta.json").write_text(json.dumps({f"{k[0]}|{k[1]}": v for k, v in meta.items()}))
    run_sync("s8_topup", SYSTEM, reqs, effort="medium")
    process()


def process():
    from s7_clean import has_absurd, usda_styled
    meta = json.loads((WORK / "topup_meta.json").read_text())
    pool = json.loads((WORK / "pool_clean.json").read_text())
    block = set(json.loads((WORK / "blocklist.json").read_text()))
    seen = {canon_key(r["ingredient"], r["usda_match"]) for r in pool}
    out, st = [], C.Counter()
    for res in (json.loads(l) for l in (WORK / "s8_topup_results.jsonl").read_text().splitlines() if l.strip()):
        if res["status"] != "succeeded":
            st["call_failed"] += 1
            continue
        obj = parse_json(res["text"])
        for it in (obj.get("items", []) if isinstance(obj, dict) else []):
            m = meta.get(f"{res['id']}|{it.get('id')}")
            if not m:
                continue
            if it.get("skip") or not it.get("ingredient"):
                st["skipped_by_model"] += 1
                continue
            ing = strip_qty(str(it["ingredient"]).strip())
            ing = re.sub(r"^raw\s+", "", ing, flags=re.I)
            row = {"ingredient": ing, "usda_match": m["usda_match"], "food": norm(core_of(ing)) or norm(ing),
                   "group": "topup_" + m["mode"].lower(), "cuisine": "unknown", "intended": LABEL[m["mode"]],
                   "level": {"G8": "medium", "G9": "medium", "G7": "hard", "B8": "hard", "G6": "hard"}[TYPE[m["mode"]]],
                   "type_requested": TYPE[m["mode"]], "type_used": TYPE[m["mode"]], "fdc_id": m["fdc_id"],
                   "fdc_source": m["fdc_source"], "snapped": True, "snap_exact": True, "snap_score": 1.0,
                   "usda_llm": m["usda_match"], "decisive": m["mode"].lower(), "review": None, "disputed": None,
                   "batch": "topup"}
            if core_of(ing) in block or norm(ing) in block:
                st["blocked_core"] += 1
                continue
            if has_absurd(row) or usda_styled(ing):
                st["absurd_or_usda_style"] += 1
                continue
            if m["mode"] == "VARIANT" and VARRE.search(ing):
                st["variant_word_leaked_into_ingredient"] += 1
                continue
            if m["mode"] == "MOD" and not MODRE.search(ing):
                st["modifier_missing"] += 1
                continue
            k = canon_key(ing, m["usda_match"])
            if k in seen:
                st["duplicate"] += 1
                continue
            seen.add(k)
            out.append(row)
            st[row["type_used"]] += 1
    (WORK / "topup_rows.json").write_text(json.dumps(out, indent=1))
    print("top-up rows kept:", len(out), dict(st))
    rng = random.Random(2)
    for t in ("G8", "G9", "G7", "B8", "G6"):
        ex = [r for r in out if r["type_used"] == t]
        print(f"  {t} examples:")
        for r in rng.sample(ex, min(4, len(ex))):
            print(f"     {r['ingredient']!r} -> {r['usda_match']!r}")


def run2():
    """Second MOD pass with relaxed candidate filters, to rebalance the smoked/powder/toasted/ground cue words."""
    rng = random.Random(SEED + 1)
    loose = re.compile(r"restaurant|babyfood|baby food|infant|toddler|formula|candy|candies|cookie|cake\b|pie\b|pudding|dessert|"
                       r"snack|fast food|mcdonald|burger king|taco bell|wendy|domino|subway|alaska native|navajo|hopi|apache|"
                       r"0% moisture|smart soup|kfc|cracker barrel|school lunch|sandwich|pizza|salad|soup|casserole|entree|dinner|"
                       r"stew|gravy|beverage|energy|latte|coffee|cocktail|alcoholic", re.I)
    pool = json.loads((WORK / "pool_clean.json").read_text())
    done_entries = {m["usda_match"] for m in json.loads((WORK / "topup_meta.json").read_text()).values()}
    used = C.Counter(norm(r["usda_match"]) for r in pool)
    rows = [r for r in fdc() if r["source"] in ("SR_Legacy", "FNDDS", "Foundation") and len(r["description"].split()) <= 12
            and not loose.search(r["description"]) and used[norm(r["description"])] < 3 and r["description"] not in done_entries]
    take = {"smoked": 45, "powder": 80, "toasted": 25, "ground": 25}
    reqs, meta = [], {}
    for w, n in take.items():
        c = [r for r in rows if re.search(rf"\b{w}\b", r["description"], re.I)]
        rng.shuffle(c)
        c = c[:n]
        print(f"MOD2 {w}: {len(c)} entries")
        for i in range(0, len(c), PER_CALL):
            chunk = c[i:i + PER_CALL]
            cid = f"top2-{w}-{i // PER_CALL:03d}"
            lines = []
            for j, r in enumerate(chunk):
                lines.append(f'e{j}: "{r["description"]}"')
                meta[f"{cid}|e{j}"] = {"mode": "MOD", "usda_match": r["description"], "fdc_id": r["fdc_id"], "fdc_source": r["source"]}
            reqs.append({"id": cid, "user": f"MODE: MOD\n{INSTR['MOD']}\n\nUSDA entries:\n" + "\n".join(lines), "max_tokens": 9000})
    (WORK / "topup_meta2.json").write_text(json.dumps(meta))
    run_sync("s8_topup2", SYSTEM, reqs, effort="medium")
    process2()


def process2():
    """Same filters as process(), plus the REAL-pair leak check; appends to topup_rows.json."""
    from s7_clean import has_absurd, usda_styled
    from s7_clean import real_keys
    meta = json.loads((WORK / "topup_meta2.json").read_text())
    block = set(json.loads((WORK / "blocklist.json").read_text()))
    rk = real_keys()
    existing = json.loads((WORK / "topup_rows.json").read_text())
    pool = json.loads((WORK / "pool_clean.json").read_text())
    seen = {canon_key(r["ingredient"], r["usda_match"]) for r in pool + existing}
    new, st = [], C.Counter()
    for res in (json.loads(l) for l in (WORK / "s8_topup2_results.jsonl").read_text().splitlines() if l.strip()):
        if res["status"] != "succeeded":
            st["call_failed"] += 1
            continue
        obj = parse_json(res["text"])
        for it in (obj.get("items", []) if isinstance(obj, dict) else []):
            m = meta.get(f"{res['id']}|{it.get('id')}")
            if not m:
                continue
            if it.get("skip") or not it.get("ingredient"):
                st["skipped_by_model"] += 1
                continue
            ing = re.sub(r"^raw\s+", "", strip_qty(str(it["ingredient"]).strip()), flags=re.I)
            row = {"ingredient": ing, "usda_match": m["usda_match"], "food": norm(core_of(ing)) or norm(ing),
                   "group": "topup_mod2", "cuisine": "unknown", "intended": 1, "level": "medium", "type_requested": "G8",
                   "type_used": "G8", "fdc_id": m["fdc_id"], "fdc_source": m["fdc_source"], "snapped": True, "snap_exact": True,
                   "snap_score": 1.0, "usda_llm": m["usda_match"], "decisive": "mod", "review": None, "disputed": None, "batch": "topup"}
            k = canon_key(ing, m["usda_match"])
            if k in rk:
                st["real_pair_copy"] += 1
            elif core_of(ing) in block or norm(ing) in block:
                st["blocked_core"] += 1
            elif has_absurd(row) or usda_styled(ing):
                st["absurd_or_usda_style"] += 1
            elif not MODRE.search(ing):
                st["modifier_missing"] += 1
            elif k in seen:
                st["duplicate"] += 1
            else:
                seen.add(k)
                new.append(row)
    (WORK / "topup_rows2.json").write_text(json.dumps(new, indent=1))
    (WORK / "topup_rows.json").write_text(json.dumps(existing + new, indent=1))
    mods = C.Counter(MODRE.search(r["ingredient"]).group(1).lower() for r in new)
    print("MOD2 rows added:", len(new), dict(st), "| by modifier:", dict(mods))
    for r in rng_sample(new, 8):
        print(f"     {r['ingredient']!r} -> {r['usda_match']!r}")


def rng_sample(lst, k):
    return random.Random(3).sample(lst, min(k, len(lst)))


if __name__ == "__main__":
    {"run": run, "process": process, "run2": run2, "process2": process2}[sys.argv[1]]()
