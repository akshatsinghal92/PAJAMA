"""Haiku v3 judge (verbatim production prompt + judge_guidelines.GUIDELINES) over ALL rows, in sequential batch chunks.
Budget: before each chunk, projected = ledger + n * measured_cost_per_call * 1.5 must stay <= GUARD_CAP.
Output: data_synth_v2/judge_haiku_v3.jsonl  {id, haiku_v3, reasoning, rerun}
Usage: s16_haiku_judge_all.py run"""
import json, random, sys, time
from pathlib import Path
from common import GUARD_CAP, MODEL, client, parse_json, record, spent
from judge_groq import prompt
from judge_guidelines import GUIDELINES
D = Path(__file__).resolve().parent.parent / "data_synth_v2"
OUT = D / "judge_haiku_v3.jsonl"
SYS = "You are a careful food-data annotator."
CHUNK, MAXTOK = 1000, 2500
COST_PER_CALL = 0.2028 / 584          # measured on the s15 batch (standard price)

def all_items():
    base = [json.loads(l) for l in open(D / "prejudge_input.jsonl")]
    rob = [json.loads(l) for l in open(D / "robustness.jsonl")]
    items = [(r["id"], r["ingredient"], r["usda_match"]) for r in base + rob]
    rr = random.Random(7).sample(base, len(base) // 20)          # 5% self-consistency re-runs
    items += [(r["id"] + "_rerun", r["ingredient"], r["usda_match"]) for r in rr]
    return items

def done_ids():
    if not OUT.exists(): return set()
    import collections
    rows = [json.loads(l) for l in open(OUT)]
    tries = collections.Counter(r["key"] for r in rows)
    return {r["key"] for r in rows if r.get("haiku_v3") is not None} | {k for k, n in tries.items() if n >= 2}

def run():
    c = client()
    while True:
        todo = [x for x in all_items() if x[0] not in done_ids()]
        if not todo: print("ALL DONE"); return
        chunk = todo[:CHUNK]
        proj = spent() + len(chunk) * COST_PER_CALL * 1.5
        if proj > GUARD_CAP:
            print(f"[budget] STOP: spent ${spent():.3f}, projected ${proj:.3f} > cap ${GUARD_CAP}"); return
        print(f"[chunk] {len(chunk)} calls ({len(todo)} remaining); spent ${spent():.3f}, projected ${proj:.3f}", flush=True)
        keymap = {f"j{i:05d}": x for i, x in enumerate(chunk)}
        reqs = [{"custom_id": cid, "params": {"model": MODEL, "max_tokens": MAXTOK, "system": SYS,
                 "output_config": {"effort": "medium"},
                 "messages": [{"role": "user", "content": prompt(ing, u) + GUIDELINES}]}}
                for cid, (k, ing, u) in keymap.items()]
        b = c.messages.batches.create(requests=reqs)
        print(f"[chunk] batch {b.id}", flush=True)
        wait_ended(c, b.id)
        collect(c, b.id, keymap, len(chunk))

def wait_ended(c, bid):
    while True:
        try:
            if c.messages.batches.retrieve(bid).processing_status == "ended": return
        except Exception as e:
            print(f"[poll] {type(e).__name__}, retrying", flush=True)
        time.sleep(30)

def fetch_results(c, bid):
    for attempt in range(6):
        try:
            return list(c.messages.batches.results(bid))
        except Exception as e:
            print(f"[fetch] retry {attempt+1} after {type(e).__name__}", flush=True); time.sleep(20 * (attempt + 1))
    raise SystemExit("could not download batch results")

def collect(c, bid, keymap, n):
    have = done_ids()
    tin = tout = 0; ok = 0
    with open(OUT, "a") as f:
        for r in fetch_results(c, bid):
                k = keymap[r.custom_id][0]
                if k in have:
                    m = getattr(r.result, "message", None)
                    if m: tin += (m.usage.input_tokens or 0); tout += m.usage.output_tokens or 0
                    continue
                k = keymap[r.custom_id][0]
                if r.result.type != "succeeded":
                    f.write(json.dumps({"key": k, "haiku_v3": None, "error": r.result.type}) + "\n"); continue
                m = r.result.message; u = m.usage
                tin += (u.input_tokens or 0) + (u.cache_creation_input_tokens or 0) + (u.cache_read_input_tokens or 0)
                tout += u.output_tokens or 0
                text = "".join(x.text for x in m.content if x.type == "text")
                o = parse_json(text); v = o.get("substitutable") if isinstance(o, dict) else None
                if isinstance(v, str): v = v.lower() == "true"
                if m.stop_reason == "max_tokens": v = None
                f.write(json.dumps({"key": k, "haiku_v3": None if v is None else int(bool(v)),
                                    "reasoning": (o.get("reasoning", "") if isinstance(o, dict) else text)[:2000]}) + "\n")
                ok += v is not None
    record(bid, "s16_haiku_judge_all", tin, tout)
    print(f"[chunk] parsed {ok} new / {n}", flush=True)

def recover(bid, first_n_done):
    """Rebuild the keymap of an interrupted chunk: it was the first CHUNK items not in the first `first_n_done` saved keys."""
    rows = [json.loads(l) for l in open(OUT)]
    prior = {r["key"] for r in rows[:first_n_done]}
    chunk = [x for x in all_items() if x[0] not in prior][:CHUNK]
    keymap = {f"j{i:05d}": x for i, x in enumerate(chunk)}
    c = client(); wait_ended(c, bid)
    collect(c, bid, keymap, len(chunk))

if __name__ == "__main__":
    if sys.argv[1] == "recover": recover(sys.argv[2], int(sys.argv[3]))
    run()
