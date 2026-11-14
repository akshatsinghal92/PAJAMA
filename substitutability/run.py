"""
Fit the substitutability program committee on val and evaluate it on one or more test sets.

Measures how well the aggregated programmatic judge reproduces the LLM
substitutability judge's `substitutable` labels.

Usage:
    # 1. build splits first:  python substitutability/data_prep.py   (real data)
    #                    or:  python substitutability/prep_synth_v2.py (synthetic v2)
    python substitutability/run.py \
        [--judges substitutability/baseline_programs] \
        [--val substitutability/data/val.jsonl] \
        [--test substitutability/data/test.jsonl] \
        [--extra-test name=path ...] \
        [--band 0.0] [--output substitutability/outputs]

Metrics per test set:
  * covered metrics: accuracy/precision/recall/F1 over rows where the committee votes,
    plus coverage (share of rows with at least one vote).
  * accuracy_full: the paper's convention (PAJAMA §4.1) - rows where every selected
    program abstains get a random label (seeded), so coverage is 100%.
  * majority_baseline: always predicting that set's majority class.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import pipeline as P  # local module (run from substitutability/ or with it on sys.path)

SCRIPT_DIR = Path(__file__).resolve().parent
RANDOM_FILL_SEED = 0


def evaluate(name: str, rows: list[dict], programs, pipe, out_dir: Path) -> dict:
    y = P.labels_of(rows)
    hard, soft = P.predict(rows, programs, pipe)
    metrics = P.binary_metrics(y, hard)

    filled = hard.copy()
    abstained = filled == -1
    rng = np.random.default_rng(RANDOM_FILL_SEED)
    filled[abstained] = rng.integers(0, 2, abstained.sum())
    acc_full = float((filled == y).mean())

    base = float(max(np.mean(y), 1 - np.mean(y)))
    print(f"\n=== {name}: n={len(y)}  yes={100 * np.mean(y):.1f}% ===")
    for k, v in metrics.items():
        print(f"  {k:14s}: {v:.4f}")
    print(f"  {'accuracy_full':14s}: {acc_full:.4f}  (abstentions filled at random)")
    print(f"  {'maj_baseline':14s}: {base:.4f}")

    with open(out_dir / f"predictions_{name}.jsonl", "w", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            rec = {k: r[k] for k in ("id", "tier", "relation_code") if k in r}
            rec.update({
                "ingredient": r["ingredient"],
                "usda_match": r["usda_match"],
                "label": int(r["label"]),
                "pred": (None if hard[i] == -1 else int(hard[i])),
                "prob_substitutable": (None if np.isnan(soft[i]) else round(float(soft[i]), 4)),
            })
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return {
        "n": len(y),
        "positive_rate": round(float(np.mean(y)), 4),
        "metrics_covered": {k: round(v, 4) for k, v in metrics.items()},
        "accuracy_full": round(acc_full, 4),
        "n_abstained": int(abstained.sum()),
        "majority_baseline": round(base, 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Fit + evaluate the substitutability committee.")
    ap.add_argument("--judges", default=str(SCRIPT_DIR / "baseline_programs"),
                    help="Directory of judge_*.py programs")
    ap.add_argument("--val", default=str(SCRIPT_DIR / "data" / "val.jsonl"))
    ap.add_argument("--test", default=str(SCRIPT_DIR / "data" / "test.jsonl"))
    ap.add_argument("--extra-test", nargs="*", default=[], metavar="NAME=PATH",
                    help="Additional test sets, e.g. real=data_synth_v2/pajama/real_external.jsonl")
    ap.add_argument("--band", type=float, default=0.0, help="Abstention margin around theta")
    ap.add_argument("--output", default=str(SCRIPT_DIR / "outputs"))
    args = ap.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    programs = P.load_programs_from_dir(args.judges)
    ok = [p for p in programs if p.fn is not None]
    print(f"Loaded {len(programs)} programs ({len(ok)} compiled) from {args.judges}")
    for p in programs:
        if p.fn is None:
            print(f"  ! {p.display_name}: {p.status}")

    val_rows = P.load_jsonl(args.val)
    tests = {"test": P.load_jsonl(args.test)}
    for spec in args.extra_test:
        name, _, path = spec.partition("=")
        if not path:
            raise SystemExit(f"--extra-test expects NAME=PATH, got {spec!r}")
        tests[name] = P.load_jsonl(path)
    print(f"val={len(val_rows)} rows; " + ", ".join(f"{k}={len(v)}" for k, v in tests.items()))

    print("Fitting pipeline on validation split ...")
    pipe = P.fit(val_rows, programs, band=args.band)
    print(f"  surviving={pipe.summary['n_surviving_programs']}  best_k={pipe.best_k}  "
          f"val_agreement={pipe.summary['val_best_agreement']}")
    print(f"  selected program ids: {pipe.selected_program_ids}")

    results = {name: evaluate(name, rows, programs, pipe, out_dir) for name, rows in tests.items()}

    t = results["test"]
    report = {
        "judges_dir": str(args.judges),
        "val_path": str(args.val),
        "fit_summary": pipe.summary,
        # Kept for backward compatibility with earlier runs:
        "test_metrics": t["metrics_covered"],
        "majority_baseline": t["majority_baseline"],
        "n_test": t["n"],
        "n_test_covered": t["n"] - t["n_abstained"],
        "results": results,
        "program_diagnostics": P.program_diagnostics(tests["test"], programs, pipe),
    }
    (out_dir / "evaluation_metrics.json").write_text(json.dumps(report, indent=2))
    # Backward-compatible filename for the main test set.
    (out_dir / "test_predictions.jsonl").write_text(
        (out_dir / "predictions_test.jsonl").read_text(encoding="utf-8"), encoding="utf-8")

    print(f"\nWrote {out_dir / 'evaluation_metrics.json'} and predictions_*.jsonl")


if __name__ == "__main__":
    main()
