"""
Independent-agent program synthesis (v5): v4 settings + a hybrid redundancy filter.

Same as v4: 20 rubrics x 4 variants, 25 random validation examples per slot (the v4 prompts
are copied unchanged), one independent agent per slot, same validation cases, up to 5
attempts per slot, 300 global attempts.

New in v5: after a program passes the usual checks, it is compared with every accepted
program on two things, and the two are combined into one redundancy score.

  code_sim    token-level similarity of the code (difflib on code tokens, autojunk off).
              The paper's character-level 0.60 rule is kept as a hard rule too.
  err_jaccard behaviour: Jaccard overlap of the two programs' ERROR sets on the 380
              validation rows. Each program is scored with its own min-max normalisation
              and its own tuned threshold, exactly as the PAJAMA pipeline would do.

  redundancy(j) = W_CODE * min(1, code_sim_j / CODE_SCALE) + W_ERR * err_jaccard_j
  combined      = max over accepted programs j
  reject if combined > TAU. A program with validation accuracy below MIN_VAL_ACC is
  also rejected, so a program cannot pass by being simply bad.

Only validation labels are used. Test data is never touched. Agents see only a generic
rejection message, never a number or another program.

Fallback: if all 5 attempts are rejected and at least one was valid but redundant, the least
redundant attempt is accepted (flagged forced_redundant) instead of leaving a placeholder.
A slot with no valid attempt still gets a FAILED placeholder, as before.

Commands (run from substitutability/ with ../.venv/bin/python):
    python synth_v5_tool.py init
    python synth_v5_tool.py submit <pid> <file>
    python synth_v5_tool.py status
    python synth_v5_tool.py calibrate <programs_dir>    # replay an existing set through the filter
"""

from __future__ import annotations

import difflib
import fcntl
import json
import re
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path

import numpy as np

import generate_programs as G
import pipeline as P
import synth_v4_tool as V4

W_CODE, W_ERR, CODE_SCALE = 0.3, 0.7, 0.60
TAU = 0.65
MIN_VAL_ACC = 0.55

HERE = Path(__file__).resolve().parent
VAL_PATH = HERE / "data_synth_v2" / "pajama_paper" / "val.jsonl"
OUT_DIR = HERE / "programs_synth_v5"
PROMPTS = OUT_DIR / "_prompts"
REJ_DIR = OUT_DIR / "_redundant"
MANIFEST = OUT_DIR / "manifest.json"
ATTEMPTS = OUT_DIR / "attempts.json"
ERRS = OUT_DIR / "val_errors.json"
REJECTED = OUT_DIR / "redundant_candidates.json"
DECISIONS = OUT_DIR / "decisions.jsonl"
LOCK = OUT_DIR / ".lock"

PLAN, HEURISTICS = V4.PLAN, V4.HEURISTICS
VAL = [json.loads(l) for l in open(VAL_PATH, encoding="utf-8") if l.strip()]
YV = np.array([int(r["label"]) for r in VAL])


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


# ── Behaviour and similarity ───────────────────────────────────────────────


def val_errors(code: str) -> tuple[list[int], float]:
    """Error vector (1 = wrong vote) and covered accuracy on the validation set, PAJAMA-style."""
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
    err = ((votes != -1) & (votes != YV)).astype(int)
    return err.tolist(), float(a[0])


def tokens(code: str) -> list[str]:
    return re.findall(r"\w+|[^\w\s]", G.clean_for_similarity(code))


def code_sim(ta: list[str], tb: list[str]) -> float:
    return difflib.SequenceMatcher(None, ta, tb, autojunk=False).ratio()


def err_jaccard(a: list[int], b: list[int]) -> float:
    a, b = np.array(a, bool), np.array(b, bool)
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def redundancy(code: str, err: list[int], pool: dict[int, tuple[str, list[int]]]) -> dict:
    """Highest combined redundancy against any accepted program (pool: pid -> (code, err))."""
    tk = tokens(code)
    best = {"combined": 0.0, "nearest": None, "code_sim": 0.0, "err_jaccard": 0.0}
    for j, (cj, ej) in pool.items():
        cs, ej_ = code_sim(tk, tokens(cj)), err_jaccard(err, ej)
        comb = W_CODE * min(1.0, cs / CODE_SCALE) + W_ERR * ej_
        if comb > best["combined"]:
            best = {"combined": round(comb, 4), "nearest": j, "code_sim": round(cs, 4),
                    "err_jaccard": round(ej_, 4)}
    return best


# ── Commands ───────────────────────────────────────────────────────────────


def cmd_init() -> None:
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST} exists; refusing to re-initialise")
    src = V4.PROMPTS
    if not src.exists():
        raise SystemExit("v4 prompts missing")
    PROMPTS.mkdir(parents=True, exist_ok=True)
    for f in src.glob("p*.txt"):
        shutil.copy(f, PROMPTS / f.name)
    shutil.copy(V4.FEWSHOT_LOG, OUT_DIR / "fewshot_per_slot.json")
    MANIFEST.write_text("[]")
    ERRS.write_text("{}")
    print(f"copied {len(list(PROMPTS.glob('p*.txt')))} v4 prompts (identical few-shot draws)")


def _accept(pid, item, code, n, err, acc, red, forced=False):
    h = HEURISTICS[item["heuristic_id"]]
    filename = f"judge_{pid}.py"
    (OUT_DIR / filename).write_text(code + "\n", encoding="utf-8")
    manifest = _load(MANIFEST, [])
    errs = _load(ERRS, {})
    errs[str(pid)] = {"err": err, "acc": acc}
    ERRS.write_text(json.dumps(errs))
    manifest.append({"program_id": pid, "filename": filename, "heuristic_id": item["heuristic_id"],
                     "heuristic_name": h["name"], "variant": item["variant"], "status": "success",
                     "attempts": n, "val_acc": round(acc, 4), "redundancy": red,
                     "forced_redundant": forced, "approach_summary": G.summarize_approach(code)})
    manifest.sort(key=lambda x: x["program_id"])
    MANIFEST.write_text(json.dumps(manifest, indent=2))


def cmd_submit(pid: int, path: str) -> None:
    item = _slot(pid)
    raw = Path(path).read_text(encoding="utf-8")
    code = G.extract_code(raw) if "```" in raw else raw.strip()
    ok, msg = G.validate_code(code)
    err, acc = None, 0.0
    if ok:  # score on validation outside the lock (runs the program 380 times)
        try:
            err, acc = val_errors(code)
        except Exception as e:  # noqa: BLE001
            ok, msg = False, f"Runtime error on check set: {e}"

    with _locked():
        manifest, attempts = _load(MANIFEST, []), _load(ATTEMPTS, {})
        if any(e["program_id"] == pid for e in manifest):
            raise SystemExit(f"slot {pid} is already final")
        if sum(attempts.values()) >= G.MAX_GLOBAL_ATTEMPTS:
            raise SystemExit("global attempt cap reached")
        n = attempts.get(str(pid), 0) + 1
        attempts[str(pid)] = n
        ATTEMPTS.write_text(json.dumps(attempts, indent=2))

        pool = {e["program_id"]: ((OUT_DIR / e["filename"]).read_text(), _load(ERRS, {})[str(e["program_id"])]["err"])
                for e in manifest if e["status"] == "success" and (OUT_DIR / e["filename"]).exists()
                and str(e["program_id"]) in _load(ERRS, {})}
        red, public, redundant = {}, msg, False
        if ok and acc < MIN_VAL_ACC:
            ok, msg = False, "WEAK"
            public = "WEAK: this program does not separate good from bad matches well enough on a hidden check set. Rethink the approach."
        if ok and G.too_similar(code, [c for c, _ in pool.values()], G.SIMILARITY_THRESHOLD):
            ok, msg = False, "TOO SIMILAR"
            public = f"TOO SIMILAR (>{G.SIMILARITY_THRESHOLD:.0%} to an existing program)"
        if ok:
            red = redundancy(code, err, pool)
            if red["combined"] > TAU:
                ok, redundant, msg = False, True, "REDUNDANT"
                public = ("REDUNDANT: this program behaves too much like programs already accepted for other slots "
                          "(checked on a hidden check set). Write a substantively different approach, not just different code.")
        with open(DECISIONS, "a") as f:
            f.write(json.dumps({"pid": pid, "attempt": n, "outcome": "accepted" if ok else msg, "val_acc": round(acc, 4),
                                **red}) + "\n")

        if redundant:  # keep as fallback candidate
            REJ_DIR.mkdir(exist_ok=True)
            fp = REJ_DIR / f"p{pid}_a{n}.py"
            fp.write_text(code + "\n")
            rj = _load(REJECTED, {})
            rj.setdefault(str(pid), []).append({"file": fp.name, "combined": red["combined"], "val_acc": acc,
                                                "err": err, "red": red})
            REJECTED.write_text(json.dumps(rj))

        if ok:
            _accept(pid, item, code, n, err, acc, red)
            print(f"ACCEPTED slot {pid} after {n} attempt(s): Valid")
            return
        if n < G.MAX_RETRIES_PER_SLOT:
            print(f"REJECTED attempt {n}/{G.MAX_RETRIES_PER_SLOT}: {public}")
            return
        cands = _load(REJECTED, {}).get(str(pid), [])
        if cands:
            b = min(cands, key=lambda c: c["combined"])
            _accept(pid, item, (REJ_DIR / b["file"]).read_text().strip(), n, b["err"], b["val_acc"], b["red"], True)
            print(f"ACCEPTED slot {pid} after {n} attempt(s): least redundant attempt kept (forced)")
            return
        h = HEURISTICS[item["heuristic_id"]]
        (OUT_DIR / f"judge_{pid}.py").write_text(
            f"# FAILED: {msg}\ndef judging_function(ingredient, usda_match):\n    return 0.0\n", encoding="utf-8")
        manifest.append({"program_id": pid, "filename": f"judge_{pid}.py", "heuristic_id": item["heuristic_id"],
                         "heuristic_name": h["name"], "variant": item["variant"], "status": f"failed: {msg}",
                         "attempts": n})
        manifest.sort(key=lambda x: x["program_id"])
        MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"SLOT FAILED (placeholder written) slot {pid} after {n} attempt(s): {msg}")


def cmd_status() -> None:
    manifest, attempts = _load(MANIFEST, []), _load(ATTEMPTS, {})
    ok = sum(e["status"] == "success" for e in manifest)
    forced = sum(bool(e.get("forced_redundant")) for e in manifest)
    outcomes = {}
    if DECISIONS.exists():
        for l in open(DECISIONS):
            o = json.loads(l)["outcome"]
            outcomes[o] = outcomes.get(o, 0) + 1
    print(f"final slots: {len(manifest)}/{len(PLAN)}  success: {ok} (forced redundant: {forced})  "
          f"failed: {len(manifest) - ok}  attempts used: {sum(attempts.values())}/{G.MAX_GLOBAL_ATTEMPTS}")
    print("attempt outcomes (validated attempts only):", outcomes)


def cmd_calibrate(d: str) -> None:
    """Replay an existing program set in slot order and report the redundancy score distribution."""
    d = Path(d)
    man = [e for e in json.loads((d / "manifest.json").read_text()) if e["status"] == "success"]
    pool, rows = {}, []
    for e in man:
        code = (d / e["filename"]).read_text()
        err, acc = val_errors(code)
        red = redundancy(code, err, pool) if pool else {"combined": 0.0, "nearest": None, "code_sim": 0, "err_jaccard": 0}
        rows.append((e["program_id"], acc, red)); pool[e["program_id"]] = (code, err)
    comb = np.array([r[2]["combined"] for r in rows[1:]])
    cs = np.array([r[2]["code_sim"] for r in rows[1:]]); ej = np.array([r[2]["err_jaccard"] for r in rows[1:]])
    print(f"{len(rows)} programs replayed. max-over-earlier combined: p50 {np.median(comb):.3f} p75 {np.percentile(comb,75):.3f} "
          f"p90 {np.percentile(comb,90):.3f} max {comb.max():.3f}")
    print(f"  at that max: mean code_sim {cs.mean():.3f}, mean err_jaccard {ej.mean():.3f}")
    low = [r[0] for r in rows if r[1] < MIN_VAL_ACC]
    print("  below accuracy floor:", low)
    for tau in (0.50, 0.55, 0.60, 0.62, 0.65, 0.70):
        rej = [r[0] for r in rows[1:] if r[2]["combined"] > tau]
        print(f"  tau {tau:.2f}: would reject {len(rej)} of {len(rows)}  e.g. {rej[:12]}")


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
    elif c == "calibrate":
        cmd_calibrate(sys.argv[2])
    else:
        raise SystemExit(__doc__)
