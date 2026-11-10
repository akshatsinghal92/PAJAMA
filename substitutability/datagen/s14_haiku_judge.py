"""Haiku (batch, effort=medium) as a stand-in judge on rows already labeled by gpt-oss-120b; reports agreement.
Usage: s14_haiku_judge.py submit | collect [--wait]"""
import collections as C, json, sys
from common import WORK, collect_batch, load_results, parse_json, submit_batch
from judge_groq import prompt   # NOTE: importing runs nothing heavy only if guarded; see below
from judge_groq import D

NAME = "s14_haiku_judge"
SYS = "You are a careful food-data annotator."

def gpt_labels():
    out = {}
    for l in open(D / "judge_out.jsonl"):
        r = json.loads(l)
        if r["judge_label"] is not None and not r["key"].endswith("#rerun"):
            out[r["key"]] = r["judge_label"]
    return out

def submit():
    base = {}
    for f in ("prejudge_input.jsonl", "robustness.jsonl"):
        for l in open(D / f):
            r = json.loads(l); base[r["id"]] = r
    lab = gpt_labels()
    items = [{"id": k, "user": prompt(base[k]["ingredient"], base[k]["usda_match"]), "max_tokens": 3000} for k in lab if k in base]
    print(len(items), "rows")
    submit_batch(NAME, SYS, items, effort="medium")

def process():
    lab = gpt_labels(); res = {}; bad = 0
    for r in load_results(NAME):
        if r["status"] != "succeeded": bad += 1; continue
        o = parse_json(r["text"]); v = o.get("substitutable") if isinstance(o, dict) else None
        if isinstance(v, str): v = v.lower() == "true"
        if v is None: bad += 1; continue
        res[r["id"]] = int(bool(v))
    (D / "judge_haiku.json").write_text(json.dumps(res))
    ks = [k for k in res if k in lab]; ag = sum(res[k] == lab[k] for k in ks)
    print(f"parsed {len(res)}, unusable {bad}; agreement with gpt-oss: {ag}/{len(ks)} = {ag/max(1,len(ks)):.1%}")
    c = C.Counter((lab[k], res[k]) for k in ks)
    print("rows (gpt-oss label, haiku label):", dict(c))
    print("positive rate  gpt-oss %.1f%%  haiku %.1f%%" % (100*sum(lab[k] for k in ks)/len(ks), 100*sum(res[k] for k in ks)/len(ks)))
    base = {}
    for l in open(D / "prejudge_input.jsonl"):
        r = json.loads(l); base[r["id"]] = r
    dis = [k for k in ks if res[k] != lab[k]][:8]
    for k in dis:
        r = base.get(k)
        if r: print(f"  gpt={lab[k]} haiku={res[k]}  {r['ingredient']!r} -> {r['usda_match']!r}")

if __name__ == "__main__":
    if sys.argv[1] == "submit": submit()
    elif sys.argv[1] == "collect":
        if collect_batch(NAME, wait="--wait" in sys.argv) is not None: process()
    else: process()
