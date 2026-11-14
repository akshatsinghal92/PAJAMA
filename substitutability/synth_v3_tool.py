"""
Independent-agent program synthesis (v3).

Differences from synth_agent_tool.py (v2):
  * Each slot (program) gets its OWN random sample of 10 few-shot examples from the
    validation set (plain random.sample, seed = 42*1000 + pid, so it is reproducible).
  * The prompt carries no information about other programs (no "already implemented"
    approach list), so every synthesizer works without memory of the others.
  * submit is safe for many parallel agents: a file lock serialises the similarity check
    and the manifest update.

Everything else matches generate_programs.py / the paper: same prompt template, same
validation cases, 0.60 code-similarity filter against every accepted program, up to 5
attempts per slot (then a FAILED placeholder), 300 global attempts.

Commands (run from substitutability/ with ../.venv/bin/python):
    python synth_v3_tool.py init                 # write per-slot prompts + few-shot records
    python synth_v3_tool.py submit <pid> <file>  # validate + similarity-check + save
    python synth_v3_tool.py status
"""

from __future__ import annotations

import fcntl
import json
import random
import sys
from contextlib import contextmanager
from pathlib import Path

import generate_programs as G

HERE = Path(__file__).resolve().parent
VAL = HERE / "data_synth_v2" / "pajama_paper" / "val.jsonl"
OUT_DIR = HERE / "programs_synth_v3"
PROMPTS = OUT_DIR / "_prompts"
MANIFEST = OUT_DIR / "manifest.json"
ATTEMPTS = OUT_DIR / "attempts.json"
FEWSHOT_LOG = OUT_DIR / "fewshot_per_slot.json"
LOCK = OUT_DIR / ".lock"

PLAN = [{"heuristic_id": h, "variant": v}
        for h in G.HEURISTICS for v in range(1, G.PROGRAMS_PER_HEURISTIC + 1)]


def _load(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


@contextmanager
def _locked():
    OUT_DIR.mkdir(exist_ok=True)
    with open(LOCK, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _slot(pid: int) -> dict:
    if not 1 <= pid <= len(PLAN):
        raise SystemExit(f"pid must be 1..{len(PLAN)}")
    return PLAN[pid - 1]


def cmd_init() -> None:
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST} exists; refusing to re-initialise")
    rows = [json.loads(l) for l in open(VAL, encoding="utf-8") if l.strip()]
    PROMPTS.mkdir(parents=True, exist_ok=True)
    log = {}
    for pid, item in enumerate(PLAN, 1):
        rng = random.Random(G.SEED * 1000 + pid)
        shots = rng.sample(rows, G.NUM_FEW_SHOT_EXAMPLES)
        log[pid] = {"ids": [r["id"] for r in shots], "n_yes": sum(int(r["label"]) for r in shots)}
        prompt = G.build_prompt(G.HEURISTICS[item["heuristic_id"]], G.format_few_shot(shots),
                                item["variant"], None)
        (PROMPTS / f"p{pid}.txt").write_text(prompt, encoding="utf-8")
    FEWSHOT_LOG.write_text(json.dumps(log, indent=1))
    MANIFEST.write_text("[]")
    ys = [v["n_yes"] for v in log.values()]
    print(f"wrote {len(PLAN)} prompts; yes-examples per slot: min {min(ys)} "
          f"mean {sum(ys)/len(ys):.1f} max {max(ys)}")


def cmd_submit(pid: int, path: str) -> None:
    item = _slot(pid)
    raw = Path(path).read_text(encoding="utf-8")
    code = G.extract_code(raw) if "```" in raw else raw.strip()
    ok, msg = G.validate_code(code)  # run outside the lock (executes untrusted-ish code)

    with _locked():
        manifest = _load(MANIFEST, [])
        attempts = _load(ATTEMPTS, {})
        if any(e["program_id"] == pid for e in manifest):
            raise SystemExit(f"slot {pid} is already final")
        if sum(attempts.values()) >= G.MAX_GLOBAL_ATTEMPTS:
            raise SystemExit("global attempt cap reached")
        n = attempts.get(str(pid), 0) + 1
        attempts[str(pid)] = n
        ATTEMPTS.write_text(json.dumps(attempts, indent=2))

        if ok:
            existing = [(OUT_DIR / e["filename"]).read_text() for e in manifest
                        if e["status"] == "success" and (OUT_DIR / e["filename"]).exists()]
            if G.too_similar(code, existing, G.SIMILARITY_THRESHOLD):
                ok, msg = False, f"TOO SIMILAR (>{G.SIMILARITY_THRESHOLD:.0%} to an existing program)"

        h = G.HEURISTICS[item["heuristic_id"]]
        filename = f"judge_{pid}.py"
        if ok:
            (OUT_DIR / filename).write_text(code + "\n", encoding="utf-8")
            status = "success"
        elif n >= G.MAX_RETRIES_PER_SLOT:
            (OUT_DIR / filename).write_text(
                f"# FAILED: {msg}\ndef judging_function(ingredient, usda_match):\n    return 0.0\n",
                encoding="utf-8")
            status = f"failed: {msg}"
        else:
            print(f"REJECTED attempt {n}/{G.MAX_RETRIES_PER_SLOT}: {msg}")
            return

        entry = {"program_id": pid, "filename": filename, "heuristic_id": item["heuristic_id"],
                 "heuristic_name": h["name"], "variant": item["variant"], "status": status,
                 "attempts": n}
        if ok:
            entry["approach_summary"] = G.summarize_approach(code)
        manifest.append(entry)
        manifest.sort(key=lambda x: x["program_id"])
        MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(("ACCEPTED" if ok else "SLOT FAILED (placeholder written)") + f" slot {pid} after {n} attempt(s): {msg}")


def cmd_status() -> None:
    manifest = _load(MANIFEST, [])
    attempts = _load(ATTEMPTS, {})
    ok = sum(e["status"] == "success" for e in manifest)
    print(f"final slots: {len(manifest)}/{len(PLAN)}  success: {ok}  failed: {len(manifest) - ok}  "
          f"attempts used: {sum(attempts.values())}/{G.MAX_GLOBAL_ATTEMPTS}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    c = sys.argv[1]
    if c == "init":
        cmd_init()
    elif c == "submit":
        cmd_submit(int(sys.argv[2]), sys.argv[3])
    elif c == "status":
        cmd_status()
    else:
        raise SystemExit(__doc__)
