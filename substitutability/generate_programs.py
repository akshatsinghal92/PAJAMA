"""
Synthesize substitutability judge programs (pointwise-binary analog of
``synthesized_programmatic_judges/generate_programs.py``).

Each synthesized program is:
    def judging_function(ingredient, usda_match):   # higher = more substitutable
        ...

Few-shot examples are drawn from the LOCAL validation split
(``substitutability/data/val.jsonl``), not Hugging Face. Programs are written to
``substitutability/programs/judge_<id>.py`` with a resume manifest.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python substitutability/data_prep.py           # build val/test first
    python substitutability/generate_programs.py    # 10 heuristics x N variants
    python substitutability/run.py --judges substitutability/programs
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import random
import re
from pathlib import Path

import anthropic

from heuristics import SUBSTITUTABILITY_HEURISTICS as HEURISTICS

MODEL = "claude-opus-4-6"   # verify id/params against the current Anthropic API before running
PROGRAMS_PER_HEURISTIC = 8
NUM_FEW_SHOT_EXAMPLES = 10
SEED = 42
MAX_RETRIES_PER_SLOT = 5
MAX_GLOBAL_ATTEMPTS = 300
SIMILARITY_THRESHOLD = 0.60

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_VAL = SCRIPT_DIR / "data" / "val.jsonl"
OUTPUT_DIR = SCRIPT_DIR / "programs"
MANIFEST_PATH = SCRIPT_DIR / "manifest.json"


# ── Few-shot (from local val split) ───────────────────────────────────────

def load_few_shot(val_path: Path, n: int, seed: int) -> list[dict]:
    rows = [json.loads(l) for l in open(val_path, encoding="utf-8") if l.strip()]
    rng = random.Random(seed)
    # Balance positives/negatives so the LLM sees both outcomes.
    pos = [r for r in rows if int(r["label"]) == 1]
    neg = [r for r in rows if int(r["label"]) == 0]
    rng.shuffle(pos); rng.shuffle(neg)
    half = n // 2
    picked = pos[:half] + neg[: n - half]
    rng.shuffle(picked)
    return picked


def format_few_shot(examples: list[dict]) -> str:
    parts = []
    for i, ex in enumerate(examples, 1):
        verdict = "substitutable" if int(ex["label"]) == 1 else "NOT substitutable"
        parts.append(
            f"--- Example {i} ---\n"
            f"Ingredient: {ex['ingredient']}\n"
            f"USDA match:  {ex['usda_match']}\n"
            f"Ground-truth: {verdict}\n"
        )
    return "\n".join(parts)


# ── Prompt ─────────────────────────────────────────────────────────────────

def build_prompt(heuristic: dict, few_shot_text: str, variant_index: int, existing_approaches=None) -> str:
    avoid_block = ""
    if existing_approaches:
        descs = "\n".join(f"  - Variant {i+1}: {d}" for i, d in enumerate(existing_approaches))
        avoid_block = (
            f"\nThe following approaches are ALREADY implemented for this heuristic. "
            f"Use a substantially DIFFERENT algorithm:\n{descs}\n"
        )
    requirements = [
        "Output ONLY valid, executable Python code inside ```python ... ``` blocks. No explanation.",
        "The function signature must be exactly: def judging_function(ingredient, usda_match):",
        "Return a single numeric score (int or float). HIGHER = MORE substitutable.",
        "Use standard Python string/math operations for speed.",
        "You may use common libraries (re, math, collections, string, statistics) but NO heavy ML/NLP libraries.",
        f"This is variant {variant_index}/{PROGRAMS_PER_HEURISTIC} — use a MEANINGFULLY DIFFERENT algorithm than other variants.",
        "Include comprehensive error handling (try/except) so the function never crashes.",
        "Handle edge cases (empty strings, missing qualifiers, gram-weight prefixes like '30g', parentheticals).",
        "Return scores in a reasonable numeric range (e.g., 0-10 or 0-100).",
        "Make the function DISCRIMINATIVE: clearly different scores for good vs bad matches.",
    ]
    requirements_text = "\n".join(f"- {x}" for x in requirements)

    return f"""You are an expert Python developer and food-informatics evaluation researcher.

Your task: Write a Python function that judges whether a USDA food-database entry is a
SUBSTITUTABLE match for a recipe ingredient. Return a numeric score where HIGHER means
the USDA entry is a BETTER (more substitutable) stand-in for the ingredient.

DEFINITION OF SUBSTITUTABLE:
The USDA entry is substitutable if BOTH hold: (1) it could be used in place of the
ingredient without changing how the dish is prepared, and (2) a person eating the dish
would not notice any difference in taste, texture, or appearance.

INPUT SHAPE:
- `ingredient` is recipe text, e.g. "200g frozen chicken breast, thawed", "30g olive oil",
  "10g garlic paste (from tube)". It may carry a leading gram weight, prep words, a
  post-comma state, and parentheticals.
- `usda_match` is a USDA description, e.g. "Olive oil", "Chicken patty, frozen, uncooked",
  "Spices, ginger, ground" (primary food first, comma-separated descriptors after).

EVALUATION STRATEGY — focus STRICTLY on this dimension:
{heuristic['name']}: {heuristic['description']}
{avoid_block}
DIVERSITY REQUIREMENT:
This is variant {variant_index}/{PROGRAMS_PER_HEURISTIC}. Use a meaningfully different
algorithm, feature set, and scoring formula than other variants for this heuristic.

FAILURE AVOIDANCE:
Avoid constant outputs, fragile code, heavy dependencies, and trivial length-only scoring.

Here are real labeled examples so you understand what substitutable vs not looks like:

{few_shot_text}

IMPORTANT REQUIREMENTS:
{requirements_text}

```python
def judging_function(ingredient, usda_match):
    # Your implementation here
```"""


# ── Extraction / validation / similarity ──────────────────────────────────

def extract_code(text: str) -> str:
    matches = re.findall(r"```python\n(.*?)\n```", text, re.DOTALL)
    if matches:
        for m in matches:
            if "def judging_function" in m:
                return m
        return matches[-1]
    return text.replace("```python", "").replace("```", "").strip()


# Food-domain validation cases: (ingredient, usda_match, expect_high)
VALIDATION_CASES = [
    ("30g olive oil", "Olive oil", True),
    ("30g olive oil", "Guava paste", False),
    ("5g ground ginger", "Spices, ginger, ground", True),
    ("10g garlic paste (from tube)", "Garlic sauce", False),
    ("250g fresh red bell pepper", "Peppers, bell, red, raw", True),
    ("", "", None),
]


def validate_code(code: str) -> tuple[bool, str]:
    try:
        ns: dict = {}
        exec(compile(code, "<generated>", "exec"), ns)
        if "judging_function" not in ns:
            return False, "Missing 'judging_function'"
        fn = ns["judging_function"]
        scores = []
        for ing, usda, _ in VALIDATION_CASES:
            s = fn(ing, usda)
            if s is None:
                return False, "Returned None"
            scores.append(float(s))
        if len(set(scores)) <= 1:
            return False, f"Constant output ({scores[0]})"
        if max(scores) - min(scores) < 0.05:
            return False, "Near-constant range"
        # Weak sanity: a clear match should not score below a clear non-match.
        if scores[0] < scores[1] or scores[2] < scores[3]:
            return False, "Fails directional sanity (good match scored below bad match)"
        return True, "Valid"
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    except Exception as e:  # noqa: BLE001
        return False, f"Runtime error: {e}"


def clean_for_similarity(code: str) -> str:
    lines = [ln.split("#")[0].rstrip() for ln in code.split("\n")]
    return " ".join(ln for ln in lines if ln.strip())


def too_similar(new_code: str, existing: list[str], threshold: float) -> bool:
    a = clean_for_similarity(new_code)
    return any(difflib.SequenceMatcher(None, a, clean_for_similarity(e)).ratio() > threshold
               for e in existing)


def summarize_approach(code: str) -> str:
    code_lower = code.lower()
    markers = [
        ("jaccard", "Jaccard"), ("overlap", "token overlap"), ("ngram", "n-gram"),
        ("trigram", "char trigrams"), ("cosine", "cosine"), ("token", "tokenization"),
        ("comma", "comma-region parsing"), ("split", "field splitting"),
        ("set(", "set operations"), ("regex", "regex"), ("difflib", "sequence match"),
        ("stem", "stemming"), ("plural", "plural normalization"),
    ]
    tags = [label for marker, label in markers if marker in code_lower]
    return ", ".join(tags[:4]) if tags else "general heuristic"


# ── State ──────────────────────────────────────────────────────────────────

def load_state() -> tuple[list[dict], dict[int, str]]:
    manifest, codes = [], {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
        for e in manifest:
            if e["status"] == "success":
                fp = OUTPUT_DIR / e["filename"]
                if fp.exists():
                    codes[e["program_id"]] = fp.read_text()
    return manifest, codes


def save_state(manifest: list[dict]) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Synthesize substitutability judge programs.")
    ap.add_argument("--val", default=str(DEFAULT_VAL))
    ap.add_argument("--per-heuristic", type=int, default=PROGRAMS_PER_HEURISTIC)
    ap.add_argument("--num-few-shot", type=int, default=NUM_FEW_SHOT_EXAMPLES)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set. export ANTHROPIC_API_KEY='sk-ant-...'")
    client = anthropic.Anthropic(api_key=api_key)

    val_path = Path(args.val)
    if not val_path.exists():
        raise FileNotFoundError(f"{val_path} not found — run data_prep.py first.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    examples = load_few_shot(val_path, args.num_few_shot, args.seed)
    few_shot_text = format_few_shot(examples)
    total = len(HEURISTICS) * args.per_heuristic
    print(f"Synthesizing {total} programs ({len(HEURISTICS)} heuristics x {args.per_heuristic}) "
          f"with {len(examples)} few-shot examples")

    manifest, existing_codes = load_state()
    completed = {e["program_id"] for e in manifest if e["status"] == "success"}
    all_codes = list(existing_codes.values())
    heuristic_approaches: dict[int, list[str]] = {h: [] for h in HEURISTICS}
    for e in manifest:
        if e["status"] == "success" and e["program_id"] in existing_codes:
            heuristic_approaches[e["heuristic_id"]].append(summarize_approach(existing_codes[e["program_id"]]))

    plan = [{"heuristic_id": h, "variant": v}
            for h in HEURISTICS for v in range(1, args.per_heuristic + 1)]

    global_attempts, success = 0, len(completed)
    for i, item in enumerate(plan):
        pid = i + 1
        if pid in completed:
            continue
        h_id = item["heuristic_id"]
        heuristic = HEURISTICS[h_id]
        print(f"\n[{pid:2d}/{total}] {heuristic['name']} (v{item['variant']})")

        best_code, best_status = None, "failed"
        slot = 0
        while slot < MAX_RETRIES_PER_SLOT and global_attempts < MAX_GLOBAL_ATTEMPTS:
            slot += 1
            global_attempts += 1
            try:
                prompt = build_prompt(heuristic, few_shot_text, item["variant"],
                                      heuristic_approaches.get(h_id) or None)
                raw = client.messages.create(
                    model=MODEL, max_tokens=5000, temperature=0.7,
                    messages=[{"role": "user", "content": prompt}],
                )
                tb = next((b for b in raw.content if b.type == "text"), None)
                if tb is None:
                    print(f"  attempt {slot}: no text block"); continue
                code = extract_code(tb.text)
                ok, msg = validate_code(code)
                if not ok:
                    print(f"  attempt {slot}: INVALID ({msg})"); continue
                if too_similar(code, all_codes, SIMILARITY_THRESHOLD):
                    print(f"  attempt {slot}: TOO SIMILAR"); continue
                best_code, best_status = code, "success"
                break
            except Exception as e:  # noqa: BLE001
                print(f"  attempt {slot}: API ERROR ({e})")
                best_status = f"error: {e}"

        filename = f"judge_{pid}.py"
        if best_code is not None:
            (OUTPUT_DIR / filename).write_text(best_code, encoding="utf-8")
            all_codes.append(best_code)
            heuristic_approaches[h_id].append(summarize_approach(best_code))
            success += 1
            print(f"  -> {filename} OK")
        else:
            (OUTPUT_DIR / filename).write_text(
                f"# FAILED: {best_status}\n"
                "def judging_function(ingredient, usda_match):\n"
                "    return 0.0\n", encoding="utf-8")
            print(f"  -> {filename} FAILED ({best_status})")

        manifest = [e for e in manifest if e.get("program_id") != pid]
        entry = {"program_id": pid, "filename": filename, "heuristic_id": h_id,
                 "heuristic_name": heuristic["name"], "variant": item["variant"],
                 "status": best_status}
        if best_code is not None:
            entry["approach_summary"] = summarize_approach(best_code)
        manifest.append(entry)
        manifest.sort(key=lambda x: x["program_id"])
        save_state(manifest)

    print(f"\nDone. {success}/{total} succeeded. Programs in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
