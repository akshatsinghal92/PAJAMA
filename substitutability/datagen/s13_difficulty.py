"""Step 13 — add MEASURED difficulty to every row (feedback point 4): how confidently the real 80-program committee
(fit on REAL val data only) gets the row right. Proxy until the judge runs; recompute against judge labels afterwards.
Fields: committee_p (P substitutable), committee_p_correct (prob. mass on the row's label), difficulty_measured (terciles)."""
import io, contextlib, json, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np
from common import DATA, HERE
D = DATA.parent
sys.path.insert(0, str(D)); import pipeline as P
V = D / "data_synth_v2"
rows = [json.loads(l) for l in open(V / "all.jsonl")]
progs = P.load_programs_from_dir(str(D / "programs")); val = P.load_jsonl(str(DATA / "val.jsonl"))
with contextlib.redirect_stderr(io.StringIO()):
    pipe = P.fit(val, progs); hard, soft = P.predict(rows, progs, pipe)
soft = np.where(np.isnan(soft), 0.5, soft)
pc = np.array([s if r["label"] == 1 else 1 - s for r, s in zip(rows, soft)])
lo, hi = np.percentile(pc, [33.3, 66.7])
for r, s, c in zip(rows, soft, pc):
    r["committee_p"] = round(float(s), 4); r["committee_p_correct"] = round(float(c), 4)
    r["difficulty_measured"] = "easy" if c >= hi else ("hard" if c < lo else "medium")
by = {r["id"]: r for r in rows}
for name in ("all", "fewshot", "fit", "router", "test"):
    p = V / f"{name}.jsonl"; cur = [json.loads(l) for l in open(p)]
    with open(p, "w", encoding="utf-8") as f:
        for r in cur: f.write(json.dumps(by[r["id"]], ensure_ascii=False) + "\n")
import collections as C
tab = C.Counter((r["tier"], r["difficulty_measured"]) for r in rows)
print("type-based tier (rows) vs measured difficulty (columns):")
print(f"{'':8s}" + "".join(f"{m:>9s}" for m in ("easy", "medium", "hard")))
for t in ("easy", "medium", "hard", "edge"):
    tot = sum(tab[(t, m)] for m in ("easy", "medium", "hard"))
    print(f"{t:8s}" + "".join(f"{100*tab[(t,m)]/tot:8.0f}%" for m in ("easy", "medium", "hard")) + f"   n={tot}")
print(f"committee accuracy vs intended labels: {np.mean(hard == np.array([r['label'] for r in rows])):.3f}")
