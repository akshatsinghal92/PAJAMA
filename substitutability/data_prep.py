"""
Build val/test splits for the substitutability judge from the labeled CSV.

Input: the fully-labeled subjudge CSV produced by the usda-judge backend
(``backend/rerank_log_varied_subjudge_final_complete.csv``), which has at least:
    ingredient, usda_match, substitutable   (True/False)

Output: unified JSONL rows under ``substitutability/data/``:
    {"ingredient": str, "usda_match": str, "label": int}   # label 1=substitutable, 0=not

The split is stratified by label and deterministic (seed). The validation split
is used for per-program threshold tuning, program filtering, and fitting the
Snorkel aggregator; the test split measures how well the program committee
reproduces the LLM judge's ``substitutable`` column.

Usage:
    python substitutability/data_prep.py \
        [--csv ../backend/rerank_log_varied_subjudge_final_complete.csv] \
        [--val-frac 0.2] [--seed 42]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = (SCRIPT_DIR / ".." / ".." / "backend"
               / "rerank_log_varied_subjudge_final_complete.csv").resolve()
DATA_DIR = SCRIPT_DIR / "data"

TRUE_STRINGS = {"true", "1", "yes", "y", "t"}
FALSE_STRINGS = {"false", "0", "no", "n", "f"}


def _parse_label(raw: str) -> int | None:
    v = (raw or "").strip().lower()
    if v in TRUE_STRINGS:
        return 1
    if v in FALSE_STRINGS:
        return 0
    return None


def load_rows(csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    skipped = 0
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ingredient = (r.get("ingredient") or "").strip()
            usda_match = (r.get("usda_match") or "").strip()
            label = _parse_label(r.get("substitutable", ""))
            if not ingredient or not usda_match or label is None:
                skipped += 1
                continue
            rows.append({"ingredient": ingredient, "usda_match": usda_match, "label": label})
    if skipped:
        print(f"  skipped {skipped} rows with missing ingredient/usda_match/substitutable")
    return rows


def _group_key(row: dict) -> tuple[str, str]:
    """Leak-safe grouping key = what a judge program actually sees.

    Strips the leading gram weight so near-duplicates like '150g onion' and
    '200g onion' (identical program input) share a group and never straddle splits.
    """
    ing = row["ingredient"].strip().lower()
    ing = re.sub(r"^\s*\d+(\.\d+)?\s*g\b", "", ing).strip()
    return (ing, row["usda_match"].strip().lower())


def stratified_split(rows: list[dict], val_frac: float, seed: int) -> tuple[list[dict], list[dict]]:
    """Grouped, label-stratified split: all rows sharing a group key go to one side."""
    rng = random.Random(seed)

    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        groups.setdefault(_group_key(r), []).append(r)

    # Each group's label (duplicates share a label; majority-vote on the rare chance they don't).
    by_label: dict[int, list[list[dict]]] = {0: [], 1: []}
    for grp in groups.values():
        lbl = round(sum(x["label"] for x in grp) / len(grp))
        by_label[lbl].append(grp)

    val: list[dict] = []
    test: list[dict] = []
    for label, grps in by_label.items():
        rng.shuffle(grps)
        n_val_groups = max(1, round(len(grps) * val_frac)) if grps else 0
        for g in grps[:n_val_groups]:
            val.extend(g)
        for g in grps[n_val_groups:]:
            test.extend(g)
    rng.shuffle(val)
    rng.shuffle(test)
    return val, test


def write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _balance(rows: list[dict]) -> str:
    pos = sum(r["label"] for r in rows)
    neg = len(rows) - pos
    return f"{len(rows)} rows ({pos} substitutable / {neg} not)"


def main() -> None:
    ap = argparse.ArgumentParser(description="Build substitutability val/test splits.")
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="Path to the labeled subjudge CSV")
    ap.add_argument("--val-frac", type=float, default=0.2, help="Validation fraction (stratified)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default=str(DATA_DIR))
    args = ap.parse_args()

    csv_path = Path(args.csv).resolve()
    out_dir = Path(args.out_dir)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    print(f"Reading {csv_path}")
    rows = load_rows(csv_path)
    print(f"  usable: {_balance(rows)}")

    val, test = stratified_split(rows, args.val_frac, args.seed)
    write_jsonl(val, out_dir / "val.jsonl")
    write_jsonl(test, out_dir / "test.jsonl")

    print(f"  val : {_balance(val)}  -> {out_dir / 'val.jsonl'}")
    print(f"  test: {_balance(test)}  -> {out_dir / 'test.jsonl'}")


if __name__ == "__main__":
    main()
