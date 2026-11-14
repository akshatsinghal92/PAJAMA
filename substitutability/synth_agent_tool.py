"""
Program-synthesis harness for an agent acting as the synthesizer LLM.

Reproduces generate_programs.py exactly (same prompt, plan order, validation, 0.60
similarity filter, retry limits, manifest), except that the program text is supplied by
the agent instead of an API call.

Commands:
    python synth_agent_tool.py prompt <pid>          # print the exact synthesis prompt for slot pid
    python synth_agent_tool.py submit <pid> <file>   # validate + similarity-check + save
    python synth_agent_tool.py status                # progress summary

Slot plan: pid 1..80 = heuristics in heuristics.py order x variants 1..8.
Per slot: up to 5 attempts (MAX_RETRIES_PER_SLOT); after 5 failures the slot is written
as a FAILED placeholder, exactly like generate_programs.py. Global cap 300 attempts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import generate_programs as G

HERE = Path(__file__).resolve().parent
FEWSHOT = HERE / "data_synth_v2" / "pajama_paper" / "fewshot.jsonl"
OUT_DIR = HERE / "programs_synth_v2"
MANIFEST = OUT_DIR / "manifest.json"
ATTEMPTS = OUT_DIR / "attempts.json"

PLAN = [{"heuristic_id": h, "variant": v}
        for h in G.HEURISTICS for v in range(1, G.PROGRAMS_PER_HEURISTIC + 1)]


def _load(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def _few_shot_text() -> str:
    rows = [json.loads(l) for l in open(FEWSHOT, encoding="utf-8") if l.strip()]
    return G.format_few_shot(rows)


def _slot(pid: int) -> dict:
    if not 1 <= pid <= len(PLAN):
        raise SystemExit(f"pid must be 1..{len(PLAN)}")
    return PLAN[pid - 1]


def _saved_codes(manifest: list[dict]) -> dict[int, str]:
    codes = {}
    for e in manifest:
        if e["status"] == "success":
            fp = OUT_DIR / e["filename"]
            if fp.exists():
                codes[e["program_id"]] = fp.read_text()
    return codes


def cmd_prompt(pid: int) -> None:
    item = _slot(pid)
    manifest = _load(MANIFEST, [])
    codes = _saved_codes(manifest)
    approaches = [G.summarize_approach(codes[e["program_id"]]) for e in manifest
                  if e["status"] == "success" and e["heuristic_id"] == item["heuristic_id"]
                  and e["program_id"] in codes]
    print(G.build_prompt(G.HEURISTICS[item["heuristic_id"]], _few_shot_text(),
                         item["variant"], approaches or None))


def cmd_submit(pid: int, path: str) -> None:
    item = _slot(pid)
    OUT_DIR.mkdir(exist_ok=True)
    manifest = _load(MANIFEST, [])
    attempts = _load(ATTEMPTS, {})
    if any(e["program_id"] == pid for e in manifest):
        raise SystemExit(f"slot {pid} is already final ({[e['status'] for e in manifest if e['program_id']==pid][0]})")
    total = sum(attempts.values())
    if total >= G.MAX_GLOBAL_ATTEMPTS:
        raise SystemExit("global attempt cap reached")

    n = attempts.get(str(pid), 0) + 1
    attempts[str(pid)] = n
    ATTEMPTS.write_text(json.dumps(attempts, indent=2))

    raw = Path(path).read_text(encoding="utf-8")
    code = G.extract_code(raw) if "```" in raw else raw.strip()
    ok, msg = G.validate_code(code)
    if ok:
        codes = list(_saved_codes(manifest).values())
        if G.too_similar(code, codes, G.SIMILARITY_THRESHOLD):
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
    done = {e["program_id"] for e in manifest}
    ok = sum(e["status"] == "success" for e in manifest)
    nxt = next((p for p in range(1, len(PLAN) + 1) if p not in done), None)
    print(f"final slots: {len(done)}/{len(PLAN)}  success: {ok}  failed: {len(done) - ok}  "
          f"attempts used: {sum(attempts.values())}/{G.MAX_GLOBAL_ATTEMPTS}  next pid: {nxt}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    c = sys.argv[1]
    if c == "prompt":
        cmd_prompt(int(sys.argv[2]))
    elif c == "submit":
        cmd_submit(int(sys.argv[2]), sys.argv[3])
    elif c == "status":
        cmd_status()
    else:
        raise SystemExit(__doc__)
