"""
Fit the substitutability program committee on val and evaluate it on test.

Measures how well the aggregated programmatic judge reproduces the LLM
substitutability judge's `substitutable` labels.

Usage:
    # 1. build splits first:  python substitutability/data_prep.py
    python substitutability/run.py \
        [--judges substitutability/baseline_programs] \
        [--val substitutability/data/val.jsonl] \
        [--test substitutability/data/test.jsonl] \
        [--band 0.0] [--output substitutability/outputs]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import pipeline as P  # local module (run from substitutability/ or with it on sys.path)

SCRIPT_DIR = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser(description="Fit + evaluate the substitutability committee.")
    ap.add_argument("--judges", default=str(SCRIPT_DIR / "baseline_programs"),
                    help="Directory of judge_*.py programs")
    ap.add_argument("--val", default=str(SCRIPT_DIR / "data" / "val.jsonl"))
    ap.add_argument("--test", default=str(SCRIPT_DIR / "data" / "test.jsonl"))
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
    test_rows = P.load_jsonl(args.test)
    y_test = P.labels_of(test_rows)
    print(f"val={len(val_rows)} rows, test={len(test_rows)} rows")

    print("Fitting pipeline on validation split ...")
    pipe = P.fit(val_rows, programs, band=args.band)
    print(f"  surviving={pipe.summary['n_surviving_programs']}  best_k={pipe.best_k}  "
          f"val_agreement={pipe.summary['val_best_agreement']}")
    print(f"  selected program ids: {pipe.selected_program_ids}")

    print("Evaluating on test split ...")
    hard, soft = P.predict(test_rows, programs, pipe)
    metrics = P.binary_metrics(y_test, hard)
    diags = P.program_diagnostics(test_rows, programs, pipe)

    # Majority-class baseline (over covered rows) for reference.
    covered = hard != -1
    base = float(max(np.mean(y_test), 1 - np.mean(y_test)))

    print("\n=== Test metrics (programmatic committee vs LLM judge labels) ===")
    for k, v in metrics.items():
        print(f"  {k:10s}: {v:.4f}")
    print(f"  {'maj_base':10s}: {base:.4f}  (predict-majority baseline)")
    print(f"  covered   : {int(covered.sum())}/{len(y_test)}")

    report = {
        "fit_summary": pipe.summary,
        "test_metrics": {k: round(v, 4) for k, v in metrics.items()},
        "majority_baseline": round(base, 4),
        "n_test": len(y_test),
        "n_test_covered": int(covered.sum()),
        "program_diagnostics": diags,
    }
    (out_dir / "evaluation_metrics.json").write_text(json.dumps(report, indent=2))

    # Row-level predictions for inspection.
    preds = []
    for i, r in enumerate(test_rows):
        preds.append({
            "ingredient": r["ingredient"],
            "usda_match": r["usda_match"],
            "label": int(r["label"]),
            "pred": (None if hard[i] == -1 else int(hard[i])),
            "prob_substitutable": (None if np.isnan(soft[i]) else round(float(soft[i]), 4)),
        })
    with open(out_dir / "test_predictions.jsonl", "w", encoding="utf-8") as f:
        for p in preds:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"\nWrote {out_dir / 'evaluation_metrics.json'} and test_predictions.jsonl")


if __name__ == "__main__":
    main()
