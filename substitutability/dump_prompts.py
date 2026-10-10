"""
Dump the exact synthesis prompts (one per program slot) WITHOUT calling any LLM.

This realizes the "build the input via code, generate programs out-of-band, then
continue the pipeline" workflow: run this to materialize `prompts/prompt_<id>.txt`,
have an LLM (or a human) write each `programs/judge_<id>.py` in response, then run
`run.py --judges programs`.

Reuses the real prompt builder from generate_programs.py so prompts are identical
to what the API path would send (minus the dynamic "avoid these approaches" block,
which is populated from already-accepted code during a live run).

Usage:
    python substitutability/dump_prompts.py [--per-heuristic 8] [--num-few-shot 10]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from generate_programs import (
    HEURISTICS,
    build_prompt,
    format_few_shot,
    load_few_shot,
    DEFAULT_VAL,
    NUM_FEW_SHOT_EXAMPLES,
    PROGRAMS_PER_HEURISTIC,
    SEED,
)

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = SCRIPT_DIR / "prompts"


def main() -> None:
    ap = argparse.ArgumentParser(description="Dump synthesis prompts (no LLM call).")
    ap.add_argument("--val", default=str(DEFAULT_VAL))
    ap.add_argument("--per-heuristic", type=int, default=PROGRAMS_PER_HEURISTIC)
    ap.add_argument("--num-few-shot", type=int, default=NUM_FEW_SHOT_EXAMPLES)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    examples = load_few_shot(Path(args.val), args.num_few_shot, args.seed)
    few_shot_text = format_few_shot(examples)

    plan = [{"heuristic_id": h, "variant": v}
            for h in HEURISTICS for v in range(1, args.per_heuristic + 1)]

    index = []
    for i, item in enumerate(plan):
        pid = i + 1
        h = HEURISTICS[item["heuristic_id"]]
        prompt = build_prompt(h, few_shot_text, item["variant"], existing_approaches=None)
        (OUT_DIR / f"prompt_{pid}.txt").write_text(prompt, encoding="utf-8")
        index.append({"program_id": pid, "heuristic_id": item["heuristic_id"],
                      "heuristic_name": h["name"], "variant": item["variant"]})

    (OUT_DIR / "index.json").write_text(json.dumps(index, indent=2))
    print(f"Wrote {len(plan)} prompts to {OUT_DIR}/ (index.json has the slot map)")


if __name__ == "__main__":
    main()
