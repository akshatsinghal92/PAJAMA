"""
Sequential single-agent program synthesis (v6).

One agent builds all 80 programs in order and keeps its own memory. After each accepted
program the harness runs it on the validation set and shows the agent a report (accuracy
plus misclassified rows). The agent writes a short lesson with `note`, then moves on to the
next slot. Accepted programs are frozen.

Same as v4: 20 rubrics x 4 variants (heuristics_20.py), the identical v4 prompts (25 random
validation examples per slot, "variant i/4"), the same validation cases, similarity filter on
code text only (the paper's character-level 0.60 rule), up to 5 attempts per slot (then a
FAILED placeholder), 300 global attempts.

Enforced order: slots must be submitted in order 1..80, and slot k+1 can only be submitted
after the lesson note for slot k has been written (if slot k was accepted).

The report shows only ingredient, USDA entry, label and score. It never shows tier or
pair-type codes. Test data is never touched.

Commands (run from substitutability/ with ../.venv/bin/python):
    python synth_v6_tool.py init
    python synth_v6_tool.py status
    python synth_v6_tool.py submit <pid> <file>
    python synth_v6_tool.py note <pid> <file>      # append the lesson for an accepted slot
"""

from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

import numpy as np

import generate_programs as G
import pipeline as P
import synth_v4_tool as V4

HERE = Path(__file__).resolve().parent
VAL_PATH = HERE / "data_synth_v2" / "pajama_paper" / "val.jsonl"
OUT_DIR = HERE / "programs_synth_v6"
PROMPTS = OUT_DIR / "_prompts"
REPORTS = OUT_DIR / "_reports"
MANIFEST = OUT_DIR / "manifest.json"
ATTEMPTS = OUT_DIR / "attempts.json"
NOTES = OUT_DIR / "notes.md"
NOTES_DONE = OUT_DIR / "notes_done.json"
SHOWN = 15  # mistakes shown per side in the printed report; the full list is in the report file

PLAN, HEURISTICS = V4.PLAN, V4.HEURISTICS
VAL = [json.loads(l) for l in open(VAL_PATH, encoding="utf-8") if l.strip()]
YV = np.array([int(r["label"]) for r in VAL])


def _load(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def _slot(pid: int) -> dict:
    if not 1 <= pid <= len(PLAN):
        raise SystemExit(f"pid must be 1..{len(PLAN)}")
    return PLAN[pid - 1]


def _next_pending(manifest) -> int | None:
    done = {e["program_id"] for e in manifest}
    return next((p for p in range(1, len(PLAN) + 1) if p not in done), None)


def evaluate(code: str) -> dict:
    """Run the program on validation PAJAMA-style: own P1/P99 normalisation, tuned threshold."""
    fn = P.compile_program(code)
    s = np.full(len(VAL), np.nan)
    for i, r in enumerate(VAL):
        try:
            s[i] = float(fn(str(r["ingredient"]), str(r["usda_match"])))
        except Exception:  # noqa: BLE001
            pass
    S = s[:, None]
    n = P.normalize(S, P.compute_norm_params(S))
    t, a = P.tune_thresholds(n, YV)
    votes = P.apply_decision(n[:, 0], float(t[0]), 0.0)
    return {"acc": float(a[0]), "thr": float(t[0]), "votes": votes, "norm": n[:, 0], "raw": s}


def report(pid: int, ev: dict) -> str:
    v, n = ev["votes"], ev["norm"]
    fy = [i for i in range(len(VAL)) if v[i] == 1 and YV[i] == 0]
    fn_ = [i for i in range(len(VAL)) if v[i] == 0 and YV[i] == 1]
    ab = int((v == -1).sum())
    yes_rate = float((v == 1).mean())
    head = (f"VALIDATION REPORT for slot {pid} (380 rows, {YV.mean():.0%} are 'substitutable')\n"
            f"  accuracy {ev['acc']:.3f} at tuned threshold {ev['thr']:.2f} (score min-max normalised on these rows)\n"
            f"  says 'substitutable' on {yes_rate:.0%} of rows; wrong: {len(fy)} false yes + {len(fn_)} false no"
            f"{f'; {ab} rows abstained (score exactly at threshold)' if ab else ''}\n")

    def fmt(idx):
        return "".join(f"  - {VAL[i]['ingredient']}  ->  {VAL[i]['usda_match']}   [norm score {n[i]:.2f}]\n" for i in idx)

    rng = random.Random(1000 + pid)
    sfy = sorted(rng.sample(fy, min(SHOWN, len(fy))))
    sfn = sorted(rng.sample(fn_, min(SHOWN, len(fn_))))
    short = (head + f"FALSE YES (program said yes, label says NOT substitutable) - {len(sfy)} of {len(fy)} shown:\n" + fmt(sfy)
             + f"FALSE NO (program said no, label says substitutable) - {len(sfn)} of {len(fn_)} shown:\n" + fmt(sfn))
    REPORTS.mkdir(exist_ok=True)
    full = (head + f"ALL FALSE YES ({len(fy)}):\n" + fmt(fy) + f"ALL FALSE NO ({len(fn_)}):\n" + fmt(fn_))
    (REPORTS / f"p{pid}_val.txt").write_text(full, encoding="utf-8")
    return short + f"  (full list of every mistake: {REPORTS}/p{pid}_val.txt)\n"


def cmd_init() -> None:
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST} exists; refusing to re-initialise")
    PROMPTS.mkdir(parents=True, exist_ok=True)
    for f in V4.PROMPTS.glob("p*.txt"):
        shutil.copy(f, PROMPTS / f.name)
    shutil.copy(V4.FEWSHOT_LOG, OUT_DIR / "fewshot_per_slot.json")
    MANIFEST.write_text("[]")
    NOTES_DONE.write_text("[]")
    NOTES.write_text("# Lessons from validation error analysis, one entry per accepted slot\n\n")
    print(f"copied {len(list(PROMPTS.glob('p*.txt')))} v4 prompts (identical few-shot draws)")


def cmd_status() -> None:
    manifest, attempts = _load(MANIFEST, []), _load(ATTEMPTS, {})
    nxt = _next_pending(manifest)
    ok = sum(e["status"] == "success" for e in manifest)
    print(f"final slots: {len(manifest)}/{len(PLAN)}  accepted: {ok}  failed: {len(manifest) - ok}  "
          f"attempts used: {sum(attempts.values())}/{G.MAX_GLOBAL_ATTEMPTS}")
    if nxt is None:
        print("ALL 80 SLOTS ARE FINAL. You are done.")
        return
    done_notes = set(_load(NOTES_DONE, []))
    need = [e["program_id"] for e in manifest if e["status"] == "success" and e["program_id"] not in done_notes]
    if need:
        print(f"NEXT ACTION: write the lesson note for accepted slot {need[0]} (python synth_v6_tool.py note {need[0]} <file>).")
    else:
        item = PLAN[nxt - 1]
        print(f"NEXT ACTION: build slot {nxt} ({HEURISTICS[item['heuristic_id']]['name']}, variant {item['variant']}/4). "
              f"Prompt: {PROMPTS}/p{nxt}.txt   attempts already used on this slot: {attempts.get(str(nxt), 0)}")
    print(f"Your notes so far: {NOTES}")


def cmd_submit(pid: int, path: str) -> None:
    item = _slot(pid)
    manifest, attempts = _load(MANIFEST, []), _load(ATTEMPTS, {})
    if any(e["program_id"] == pid for e in manifest):
        raise SystemExit(f"slot {pid} is already final")
    nxt = _next_pending(manifest)
    if pid != nxt:
        raise SystemExit(f"slots must be built in order: the next slot is {nxt}, not {pid}")
    done_notes = set(_load(NOTES_DONE, []))
    for e in manifest:
        if e["status"] == "success" and e["program_id"] not in done_notes:
            raise SystemExit(f"write the lesson note for slot {e['program_id']} first: "
                             f"python synth_v6_tool.py note {e['program_id']} <file>")
    if sum(attempts.values()) >= G.MAX_GLOBAL_ATTEMPTS:
        raise SystemExit("global attempt cap reached")

    raw = Path(path).read_text(encoding="utf-8")
    code = G.extract_code(raw) if "```" in raw else raw.strip()
    ok, msg = G.validate_code(code)
    n = attempts.get(str(pid), 0) + 1
    attempts[str(pid)] = n
    ATTEMPTS.write_text(json.dumps(attempts, indent=2))
    if ok:
        existing = [(OUT_DIR / e["filename"]).read_text() for e in manifest
                    if e["status"] == "success" and (OUT_DIR / e["filename"]).exists()]
        if G.too_similar(code, existing, G.SIMILARITY_THRESHOLD):
            ok, msg = False, f"TOO SIMILAR (>{G.SIMILARITY_THRESHOLD:.0%} to an existing program)"

    h = HEURISTICS[item["heuristic_id"]]
    filename = f"judge_{pid}.py"
    entry = {"program_id": pid, "filename": filename, "heuristic_id": item["heuristic_id"],
             "heuristic_name": h["name"], "variant": item["variant"], "attempts": n}
    if ok:
        (OUT_DIR / filename).write_text(code + "\n", encoding="utf-8")
        entry["status"] = "success"
        entry["approach_summary"] = G.summarize_approach(code)
    elif n >= G.MAX_RETRIES_PER_SLOT:
        (OUT_DIR / filename).write_text(
            f"# FAILED: {msg}\ndef judging_function(ingredient, usda_match):\n    return 0.0\n", encoding="utf-8")
        entry["status"] = f"failed: {msg}"
    else:
        print(f"REJECTED attempt {n}/{G.MAX_RETRIES_PER_SLOT}: {msg}")
        return

    if ok:
        try:
            ev = evaluate(code)
            entry["val_acc"] = round(ev["acc"], 4)
            rep = report(pid, ev)
        except Exception as e:  # noqa: BLE001
            rep = f"(validation run failed: {e})\n"
    manifest.append(entry)
    manifest.sort(key=lambda x: x["program_id"])
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    if ok:
        print(f"ACCEPTED slot {pid} after {n} attempt(s): Valid\n")
        print(rep)
        print(f"NEXT: do your error analysis, then write your lesson with:  python synth_v6_tool.py note {pid} <file>")
    else:
        print(f"SLOT FAILED (placeholder written) slot {pid} after {n} attempt(s): {msg}\nNo report and no note needed; continue with the next slot.")


def cmd_note(pid: int, path: str) -> None:
    manifest = _load(MANIFEST, [])
    e = next((x for x in manifest if x["program_id"] == pid), None)
    if e is None or e["status"] != "success":
        raise SystemExit(f"slot {pid} is not an accepted slot")
    done = _load(NOTES_DONE, [])
    if pid in done:
        raise SystemExit(f"note for slot {pid} already written")
    text = Path(path).read_text(encoding="utf-8").strip()
    if len(text) < 80:
        raise SystemExit("note too short: write what you found in the errors and what the next programs should do differently")
    with open(NOTES, "a", encoding="utf-8") as f:
        f.write(f"## Slot {pid} - {e['heuristic_name']} (variant {e['variant']}/4) - val accuracy {e.get('val_acc')}\n{text}\n\n")
    done.append(pid)
    NOTES_DONE.write_text(json.dumps(done))
    print(f"note for slot {pid} saved. Run `python synth_v6_tool.py status` for your next action.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    c = sys.argv[1]
    if c == "init":
        cmd_init()
    elif c == "status":
        cmd_status()
    elif c == "submit":
        cmd_submit(int(sys.argv[2]), sys.argv[3])
    elif c == "note":
        cmd_note(int(sys.argv[2]), sys.argv[3])
    else:
        raise SystemExit(__doc__)
