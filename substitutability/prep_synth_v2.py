"""
Build PAJAMA-ready splits from data_synth_v2 with the Haiku v3 judge labels as ground truth.

Writes data_synth_v2/pajama/:
    fewshot.jsonl   58 rows    -> few-shot examples for program synthesis
    fit.jsonl       1,456 rows -> "validation" set: threshold tuning, filtering, top-k, Snorkel
    router.jsonl    1,041 rows -> held out for the routing / fallback stage (not used by the baseline)
    test.jsonl      1,624 rows -> synthetic test set
    robustness.jsonl  163 rows -> perturbation variants (optional robustness check)
    real_external.jsonl 943 rows -> real labeled data (data/val + data/test), external test set

Every row keeps `ingredient`, `usda_match`, `label` (= Haiku v3), plus `label_intended`
(the generator's planned label) and metadata useful for slicing results.

Usage:
    python prep_synth_v2.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "data_synth_v2"
OUT = SRC / "pajama"
REAL = [HERE / "data" / "val.jsonl", HERE / "data" / "test.jsonl"]

KEEP = ["id", "ingredient", "usda_match", "tier", "relation_code", "family", "cuisine",
        "fdc_source", "split", "gold_for_human_label", "core_food", "group_id"]


def read(path: Path) -> list[dict]:
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def write(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    # Haiku v3 labels. "<id>_rerun" keys are repeat calls used only to measure judge
    # stability; the original call is the label of record.
    haiku = {j["key"]: int(j["haiku_v3"]) for j in read(SRC / "judge_haiku_v3.jsonl")
             if not j["key"].endswith("_rerun")}

    rows = read(SRC / "all.jsonl")
    missing = [r["id"] for r in rows if r["id"] not in haiku]
    if missing:
        raise SystemExit(f"{len(missing)} rows have no Haiku v3 label, e.g. {missing[:3]}")

    OUT.mkdir(exist_ok=True)
    out_rows = []
    for r in rows:
        o = {k: r.get(k) for k in KEEP}
        o["label"] = haiku[r["id"]]
        o["label_intended"] = int(r["label"])
        out_rows.append(o)

    print(f"{'split':10s} {'rows':>6s} {'yes%':>6s}  {'changed vs intended':>20s}")
    for split in ("fewshot", "fit", "router", "test"):
        part = [o for o in out_rows if o["split"] == split]
        write(OUT / f"{split}.jsonl", part)
        yes = sum(o["label"] for o in part) / len(part)
        changed = sum(o["label"] != o["label_intended"] for o in part)
        print(f"{split:10s} {len(part):6d} {100 * yes:6.1f}  {changed:20d}")

    variants = []
    for r in read(SRC / "robustness.jsonl"):
        if r["id"] not in haiku:
            continue
        variants.append({"id": r["id"], "ingredient": r["ingredient"], "usda_match": r["usda_match"],
                         "label": haiku[r["id"]], "variant_of": r.get("variant_of"),
                         "perturbation": r.get("perturbation"), "split": r.get("split")})
    write(OUT / "robustness.jsonl", variants)
    print(f"robustness {len(variants):6d}")

    real = []
    for p in REAL:
        for r in read(p):
            real.append({"ingredient": r["ingredient"], "usda_match": r["usda_match"],
                         "label": int(r["label"]), "source_file": p.name})
    write(OUT / "real_external.jsonl", real)
    pairs = Counter((r["ingredient"], r["usda_match"]) for r in real)
    print(f"real       {len(real):6d} rows, {len(pairs)} distinct pairs, "
          f"{100 * sum(r['label'] for r in real) / len(real):.1f}% yes")

    # Leakage guard: no synthetic pair may appear in the real external set.
    synth_pairs = {(o["ingredient"], o["usda_match"]) for o in out_rows}
    overlap = synth_pairs & set(pairs)
    print(f"synthetic/real exact-pair overlap: {len(overlap)}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
