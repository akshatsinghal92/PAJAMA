"""Step 12 — robustness variants (evaluation only). Usage: s12_variants.py run"""
import collections as C, json, random, sys
from common import DATA, WORK, HERE, MODEL, parse_json, run_sync
V = HERE.parent / "data_synth_v2"
SYSTEM = """You create robustness test variants of (ingredient line, USDA entry) pairs. The USDA entry never changes.
For each given pair produce:
 "preserve": a variant of the ingredient line that should keep the SAME substitutability label: one of
    typo (one realistic misspelling), abbreviation (EVOO, AP flour, tbsp...), case/punctuation, filler (organic, good-quality, about),
    reorder (onion, finely diced), unit (replace the leading gram weight with a realistic other unit such as 2 tbsp, 1 cup, 1 large).
    Keep the quantity-then-food structure. Do not change any attribute that affects the match (form, state, variety, cut, flavour).
 "flip": a MINIMAL edit of the ingredient line (add or remove exactly one decisive attribute word, e.g. smoked, unsweetened, cooked,
    frozen, jarred, 'and pepper') so that the match with the SAME USDA entry flips: a good match becomes bad or a bad match becomes good.
    If no natural single-edit flip exists, set flip to null.
Reply with JSON only: {"items": [{"id": "<id>", "preserve": {"ingredient": "...", "kind": "..."}, "flip": {"ingredient": "...", "change": "<what changed>"} or null}]}"""
def main():
    rng = random.Random(5)
    test = [json.loads(l) for l in open(V / "test.jsonl")]
    by = C.defaultdict(list)
    for r in test: by[r["tier"]].append(r)
    parents = []
    for t, k in (("easy", 20), ("medium", 30), ("hard", 35), ("edge", 15)):
        rng.shuffle(by[t]); parents += by[t][:k]
    items = []
    for i in range(0, len(parents), 10):
        ch = parents[i:i+10]
        lines = [f'{r["id"]}: ingredient "{r["ingredient"]}" | USDA entry "{r["usda_match"]}" | current label {"substitutable" if r["label"] else "NOT substitutable"}' for r in ch]
        items.append({"id": f"var-{i//10:03d}", "user": "Pairs:\n" + "\n".join(lines), "max_tokens": 8000})
    run_sync("s12_variants", SYSTEM, items, effort="medium")
    pm = {r["id"]: r for r in parents}
    out, k = [], 0
    for res in (json.loads(l) for l in (WORK / "s12_variants_results.jsonl").read_text().splitlines() if l.strip()):
        if res["status"] != "succeeded": continue
        obj = parse_json(res["text"])
        for it in (obj.get("items", []) if isinstance(obj, dict) else []):
            p = pm.get(it.get("id"))
            if not p: continue
            for key, flip in (("preserve", False), ("flip", True)):
                v = it.get(key)
                if not isinstance(v, dict) or not v.get("ingredient") or v["ingredient"].strip().lower() == p["ingredient"].lower(): continue
                k += 1
                out.append({**{f: p[f] for f in ("usda_match", "tier", "core_food", "group_id", "family", "cuisine", "fdc_id", "fdc_source")},
                            "id": f"sub2-var-{k:04d}", "ingredient": v["ingredient"].strip(), "label": 1 - p["label"] if flip else p["label"],
                            "label_status": "intended_unjudged", "judge_label": None, "variant_of": p["id"],
                            "perturbation": "flip:" + str(v.get("change", ""))[:60] if flip else "preserve:" + str(v.get("kind", ""))[:30],
                            "split": "robustness", "relation_code": p["relation_code"], "generator_model": MODEL})
    with open(V / "robustness.jsonl", "w", encoding="utf-8") as f:
        for x in out: f.write(json.dumps(x, ensure_ascii=False) + "\n")
    pc = C.Counter(x["perturbation"].split(":")[0] for x in out)
    print("variants written:", len(out), dict(pc))
    for x in random.Random(1).sample(out, min(10, len(out))):
        par = next(p for p in parents if p["id"] == x["variant_of"])
        print(f"   [{x['perturbation'][:28]:28s}] {par['ingredient']!r} => {x['ingredient']!r}  -> {x['usda_match']!r}  label {par['label']}->{x['label']}")
if __name__ == "__main__": main()
