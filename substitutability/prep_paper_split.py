"""
Paper-proportion split of data_synth_v2 for an exact PAJAMA baseline replication.

Paper (§4.1, App. B, Table 3): up to 5,000 test rows + 500 validation rows per dataset,
i.e. validation = 500 / 5,500 = 9.09% of the pool, test = 90.91%. The 10 few-shot examples
used for program synthesis are drawn at random from the validation set (App. A.3; upstream
code uses random.sample with seed 42).

The paper samples rows at random. Here rows are grouped by core food so that contrast pairs
of the same food never sit on both sides of the split; the 9.09% share is preserved.

Labels: Haiku v3 (`label`), generator label kept as `label_intended`. Built from
data_synth_v2/pajama/*.jsonl (run prep_synth_v2.py first). All 4,179 main rows are pooled.

Writes data_synth_v2/pajama_paper/{val,test,fewshot}.jsonl and split_info.json.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "data_synth_v2" / "pajama"
OUT = HERE / "data_synth_v2" / "pajama_paper"
VAL_FRACTION = 500 / 5500
SEED = 42
NUM_FEW_SHOT = 10


def read(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def write(p: Path, rows: list[dict]) -> None:
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    pool = [r for s in ("fewshot", "fit", "router", "test") for r in read(SRC / f"{s}.jsonl")]
    target_val = round(len(pool) * VAL_FRACTION)

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in pool:
        groups[r["core_food"] or r["id"]].append(r)
    keys = sorted(groups)
    random.Random(SEED).shuffle(keys)

    val, test = [], []
    for k in keys:
        (val if len(val) < target_val else test).extend(groups[k])

    # Few-shot: plain random sample from validation, as in the paper / upstream code.
    rng = random.Random(SEED)
    fewshot = rng.sample(val, NUM_FEW_SHOT)

    OUT.mkdir(exist_ok=True)
    write(OUT / "val.jsonl", val)
    write(OUT / "test.jsonl", test)
    write(OUT / "fewshot.jsonl", fewshot)

    vf = {r["core_food"] for r in val}
    tf = {r["core_food"] for r in test}
    info = {
        "pool": len(pool), "val": len(val), "test": len(test),
        "val_fraction": round(len(val) / len(pool), 4), "paper_val_fraction": round(VAL_FRACTION, 4),
        "val_yes": round(sum(r["label"] for r in val) / len(val), 4),
        "test_yes": round(sum(r["label"] for r in test) / len(test), 4),
        "fewshot_yes": sum(r["label"] for r in fewshot),
        "core_food_overlap": len(vf & tf), "seed": SEED,
        "val_tiers": {t: sum(r["tier"] == t for r in val) for t in ("easy", "medium", "hard", "edge")},
        "test_tiers": {t: sum(r["tier"] == t for r in test) for t in ("easy", "medium", "hard", "edge")},
    }
    (OUT / "split_info.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
