"""Shared helpers for the 4K data-generation pipeline (see ../DATA_GENERATION_PLAN_4K.md).

* The API key is read ONLY from the ANTHROPIC_API_KEY environment variable. It is never written to disk.
* Every Haiku call goes through run_batch(), which enforces a spend guard against a ledger.
  Costs are tracked at STANDARD prices (the batch discount is not assumed), so the real bill is <= ledger.
"""
from __future__ import annotations

import csv
import difflib
import json
import os
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
WORK.mkdir(exist_ok=True)
DATA = HERE.parent / "data"

MODEL = "claude-haiku-5-5"
PRICE_IN = 0.10 / 1e6       # $/token, standard
PRICE_OUT = 0.50 / 1e6
GUARD_CAP = 4.75            # raised for the full Haiku judge run; still under the $5 HARD_CAP, and the ledger is at STANDARD price (real batch bill ~half)
HARD_CAP = 5.00             # the user's limit

LEDGER = WORK / "ledger.json"
BATCHES = WORK / "batches.json"


# ── spend ledger ───────────────────────────────────────────────────────────

def _load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def ledger() -> dict:
    return _load(LEDGER, {"spent_standard": 0.0, "recorded_batches": [], "log": []})


def spent() -> float:
    return ledger()["spent_standard"]


def guard(worst_case: float, label: str) -> None:
    s = spent()
    if s + worst_case > GUARD_CAP:
        raise SystemExit(f"[guard] REFUSING {label}: spent ${s:.3f} + worst-case ${worst_case:.3f} "
                         f"> guard cap ${GUARD_CAP:.2f} (hard cap ${HARD_CAP:.2f})")
    print(f"[guard] {label}: worst-case ${worst_case:.3f}; spent so far ${s:.3f}; cap ${GUARD_CAP:.2f}  OK")


def record(batch_id: str, label: str, in_tok: int, out_tok: int) -> None:
    led = ledger()
    if batch_id in led["recorded_batches"]:
        return
    cost = in_tok * PRICE_IN + out_tok * PRICE_OUT
    led["spent_standard"] += cost
    led["recorded_batches"].append(batch_id)
    led["log"].append({"batch": batch_id, "label": label, "in_tokens": in_tok, "out_tokens": out_tok,
                       "cost_standard": round(cost, 5), "cost_if_batch_discount": round(cost / 2, 5)})
    LEDGER.write_text(json.dumps(led, indent=2))
    print(f"[ledger] {label}: {in_tok} in / {out_tok} out = ${cost:.4f} standard "
          f"(~${cost/2:.4f} with batch discount). Total spent (standard): ${led['spent_standard']:.4f}")


# ── API / batches ──────────────────────────────────────────────────────────

def client():
    import anthropic
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set in the environment")
    return anthropic.Anthropic()


def est_tokens(text: str) -> int:
    return int(len(text) / 3) + 8     # deliberately conservative (real is ~len/4)


def submit_batch(name: str, system: str, items: list[dict], effort: str = "medium") -> None:
    """items: [{"id": str, "user": str, "max_tokens": int}]. Idempotent per `name`."""
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    batches = _load(BATCHES, {})
    if name in batches:
        print(f"[batch] {name} already submitted: {batches[name]['id']}")
        return
    worst = sum(est_tokens(system) + est_tokens(i["user"]) for i in items) * PRICE_IN \
        + sum(i["max_tokens"] for i in items) * PRICE_OUT
    guard(worst, f"submit {name} ({len(items)} requests)")
    reqs = [Request(custom_id=i["id"], params=MessageCreateParamsNonStreaming(
        model=MODEL, max_tokens=i["max_tokens"], system=system,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": i["user"]}])) for i in items]
    b = client().messages.batches.create(requests=reqs)
    batches[name] = {"id": b.id, "n": len(items), "worst_case": round(worst, 4), "created": time.time()}
    BATCHES.write_text(json.dumps(batches, indent=2))
    (WORK / f"{name}_requests.json").write_text(json.dumps(items))
    print(f"[batch] submitted {name}: id={b.id} n={len(items)}")


def collect_batch(name: str, wait: bool = False, poll: int = 30) -> list[dict] | None:
    """Fetch results (optionally waiting). Writes work/{name}_results.jsonl, records spend."""
    batches = _load(BATCHES, {})
    if name not in batches:
        raise SystemExit(f"no batch named {name}")
    bid = batches[name]["id"]
    c = client()
    while True:
        b = c.messages.batches.retrieve(bid)
        rc = b.request_counts
        print(f"[batch] {name}: {b.processing_status} processing={rc.processing} ok={rc.succeeded} "
              f"err={rc.errored} exp={rc.expired}")
        if b.processing_status == "ended":
            break
        if not wait:
            return None
        time.sleep(poll)
    out, in_tok, out_tok, think = [], 0, 0, 0
    for r in c.messages.batches.results(bid):
        rec = {"id": r.custom_id, "status": r.result.type}
        if r.result.type == "succeeded":
            m = r.result.message
            u = m.usage
            i_t = (u.input_tokens or 0) + (u.cache_creation_input_tokens or 0) + (u.cache_read_input_tokens or 0)
            o_t = u.output_tokens or 0
            th = getattr(getattr(u, "output_tokens_details", None), "thinking_tokens", 0) or 0
            in_tok += i_t; out_tok += o_t; think += th
            rec.update(text="".join(b.text for b in m.content if b.type == "text"),
                       stop=m.stop_reason, in_tok=i_t, out_tok=o_t, think_tok=th)
        else:
            rec["error"] = str(getattr(r.result, "error", ""))[:300]
        out.append(rec)
    (WORK / f"{name}_results.jsonl").write_text("\n".join(json.dumps(x) for x in out))
    record(bid, name, in_tok, out_tok)
    n_ok = sum(1 for x in out if x["status"] == "succeeded")
    print(f"[batch] {name}: {n_ok}/{len(out)} succeeded; thinking tokens {think} of {out_tok} output")
    return out


def run_sync(name: str, system: str, items: list[dict], effort: str = "medium", workers: int = 8) -> list[dict]:
    """Same contract as submit_batch+collect_batch but with ordinary (full-price) calls; for small/urgent runs.
    Writes work/{name}_results.jsonl in the same format. Resumable: ids already in the file are not re-run."""
    from concurrent.futures import ThreadPoolExecutor
    path = WORK / f"{name}_results.jsonl"
    done = {}
    if path.exists():
        for l in path.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                if r["status"] == "succeeded" and r.get("stop") != "max_tokens":   # truncated -> re-run
                    done[r["id"]] = r
    todo = [i for i in items if i["id"] not in done]
    worst = sum(est_tokens(system) + est_tokens(i["user"]) for i in todo) * PRICE_IN \
        + sum(i["max_tokens"] for i in todo) * PRICE_OUT
    if not todo:
        print(f"[sync] {name}: nothing to do")
        return list(done.values())
    guard(worst, f"sync {name} ({len(todo)} calls, standard price)")
    c = client()

    def one(i):
        try:
            m = c.messages.create(model=MODEL, max_tokens=i["max_tokens"], system=system,
                                  output_config={"effort": effort},
                                  messages=[{"role": "user", "content": i["user"]}])
            u = m.usage
            return {"id": i["id"], "status": "succeeded", "text": "".join(b.text for b in m.content if b.type == "text"),
                    "stop": m.stop_reason,
                    "in_tok": (u.input_tokens or 0) + (u.cache_creation_input_tokens or 0) + (u.cache_read_input_tokens or 0),
                    "out_tok": u.output_tokens or 0,
                    "think_tok": getattr(getattr(u, "output_tokens_details", None), "thinking_tokens", 0) or 0}
        except Exception as e:  # noqa: BLE001
            return {"id": i["id"], "status": "errored", "error": str(e)[:300]}

    with ThreadPoolExecutor(workers) as ex:
        new = list(ex.map(one, todo))
    allr = list(done.values()) + new
    path.write_text("\n".join(json.dumps(x) for x in allr))
    in_t = sum(x.get("in_tok", 0) for x in new)
    out_t = sum(x.get("out_tok", 0) for x in new)
    record(f"sync-{name}-{int(time.time())}", f"{name} (sync)", in_t, out_t)
    ok = sum(1 for x in new if x["status"] == "succeeded")
    print(f"[sync] {name}: {ok}/{len(new)} succeeded; thinking tokens {sum(x.get('think_tok',0) for x in new)} of {out_t} output")
    return allr


def load_results(name: str) -> list[dict]:
    p = WORK / f"{name}_results.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def parse_json(text: str):
    """Extract the first JSON object/array from model text (tolerates code fences)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i, j = t.find(open_c), t.rfind(close_c)
        if i != -1 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except Exception:
                pass
    return None


# ── text normalisation (matches data_prep._group_key) ─────────────────────

QTY_RE = re.compile(r"^\s*\d+(\.\d+)?\s*g\b", re.I)


def strip_qty(s: str) -> str:
    return QTY_RE.sub("", s.strip()).strip()


def norm(s: str) -> str:
    s = strip_qty(s).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def canon_key(ingredient: str, usda: str) -> tuple[str, str]:
    return (norm(ingredient), norm(usda))


def singular(t: str) -> str:
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("oes"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


STOP = {"fresh", "g", "raw", "and", "or", "the", "of", "with", "a", "nfs", "chopped", "diced", "shredded", "in", "to",
        "from", "no", "added", "ns", "as", "for"}


def tokens(s: str) -> set[str]:
    return {singular(t) for t in norm(s).split() if t not in STOP and not t.isdigit()}


def jaccard(a: str, b: str) -> float:
    x, y = tokens(a), tokens(b)
    return len(x & y) / max(1, len(x | y))


# ── FoodData Central index ─────────────────────────────────────────────────

_FDC = None


def fdc() -> list[dict]:
    global _FDC
    if _FDC is None:
        _FDC = list(csv.DictReader(open(DATA / "fdc_descriptions.csv", encoding="utf-8")))
    return _FDC
