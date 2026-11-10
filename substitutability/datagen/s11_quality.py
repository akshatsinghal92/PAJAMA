"""Step 11 — measure the quality of ../data_synth_v2 against the audit's findings (no API calls)."""
import collections as C, json, re, sys, warnings, io, contextlib
warnings.filterwarnings("ignore")
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from blocklist import core_of
from common import DATA, WORK, canon_key, strip_qty, norm
V = sys.argv[1] if len(sys.argv) > 1 else "data_synth_v2"
D = DATA.parent
R = [json.loads(l) for l in open(D / V / "all.jsonl")]
y = np.array([r["label"] for r in R]); n = len(R)
ing = [strip_qty(r["ingredient"]).lower() for r in R]; usda = [r["usda_match"].lower() for r in R]
grp = [r["group_id"] for r in R]
pct = lambda a, b: f"{100*a/max(1,b):.1f}%"
print(f"\n===== {V}: {n} rows =====")
print("label (intended, UNJUDGED): positive", pct(y.sum(), n))
tc = C.Counter(r["tier"] for r in R); print("tiers:", {t: f"{tc[t]} ({pct(tc[t], n)}, pos {pct(sum(r['label'] for r in R if r['tier']==t), tc[t])})" for t in ("easy", "medium", "hard", "edge")})
print("splits:", dict(C.Counter(r["split"] for r in R)))
print("\n-- LEAKS --")
rk = set()
for sp in ("val", "test"):
    for l in open(DATA / f"{sp}.jsonl"):
        r = json.loads(l); rk.add(canon_key(r["ingredient"], r["usda_match"]))
block = set(json.load(open(WORK / "blocklist.json")))
print("exact copies of real pairs        :", sum(canon_key(r["ingredient"], r["usda_match"]) in rk for r in R), "(target 0)")
print("ingredient core in reserved block :", sum(core_of(strip_qty(r["ingredient"])) in block for r in R), "(target 0)")
gs = C.defaultdict(set)
for r in R: gs[r["group_id"]].add(r["split"])
print("groups spanning >1 split          :", sum(len(s) > 1 for s in gs.values()), "(target 0)")
print("duplicate canonical pairs         :", n - len({canon_key(r['ingredient'], r['usda_match']) for r in R}), "(target 0)")
print("duplicate ids                     :", n - len({r['id'] for r in R}), "(target 0)")
cs = C.defaultdict(set)
for r, i in zip(R, ing): cs[core_of(i)].add(r["split"])
print("ingredient cores in test AND other:", sum(1 for s in cs.values() if "test" in s and len(s) > 1), "of", len(cs))
print("\n-- SURFACE CUES (positive rate when the cue is present; overall %.0f%%) --" % (100 * y.mean()))
for name, f in [("parenthetical note", lambda s: "(" in s), ("' and '", lambda s: " and " in s),
                ("smoked", lambda s: "smoked" in s), ("toasted", lambda s: "toasted" in s), ("ground", lambda s: "ground" in s),
                ("powder", lambda s: "powder" in s), ("room temp/chilled/refrig", lambda s: bool(re.search(r"room temp|chilled|refrigerated", s))),
                ("starts with 'raw '", lambda s: s.startswith("raw ")), ("has comma clause", lambda s: "," in s)]:
    m = np.array([f(s) for s in ing])
    if m.sum(): print(f"  {name:26s} n={m.sum():4d}  rate-in-data {pct(m.sum(), n):>6s}  positive {pct(y[m].sum(), m.sum()):>6s}")
print("\n-- SHORTCUT MODELS (grouped 5-fold CV AUC; 0.5 = none) --")
def cv(make):
    p = np.zeros(n)
    for tr, te in GroupKFold(5).split(ing, y, grp):
        a, b = make(tr, te); p[te] = LogisticRegression(C=1, max_iter=3000).fit(a, y[tr]).predict_proba(b)[:, 1]
    return roc_auc_score(y, p)
def tf(texts):
    def mk(tr, te):
        v = TfidfVectorizer(ngram_range=(1, 2), min_df=2).fit([texts[i] for i in tr]); return v.transform([texts[i] for i in tr]), v.transform([texts[i] for i in te])
    return mk
qty = np.array([float(re.match(r"\s*(\d+)", r["ingredient"]).group(1)) for r in R])
S = np.array([[len(ing[i]), len(usda[i]), len(ing[i].split()), len(usda[i].split()), usda[i].count(","), int("nfs" in usda[i]), int(R[i]["fdc_source"] == "FNDDS"), int(" and " in ing[i]), int("(" in ing[i]), int("," in ing[i]), np.log1p(qty[i])] for i in range(n)])
def sf(a, b):
    s = StandardScaler().fit(S[a]); return s.transform(S[a]), s.transform(S[b])
print(f"  ingredient words only          : {cv(tf(ing)):.3f}   (audit: 0.65-0.67; target ~0.55)")
print(f"  USDA words only                : {cv(tf(usda)):.3f}")
print(f"  surface stats (no overlap)     : {cv(sf):.3f}")
print(f"  word overlap (jaccard) overall : {roc_auc_score(y, [r['jaccard'] for r in R]):.3f}   (informational; matching happens after the judge)")
for t in ("easy", "medium", "hard", "edge"):
    m = np.array([r["tier"] == t for r in R])
    if len(set(y[m])) == 2: print(f"     jaccard AUC in {t:6s}: {roc_auc_score(y[m], [R[i]['jaccard'] for i in np.where(m)[0]]):.3f}")
print("\n-- TYPE COVERAGE IN TEST (target >= 15 each) --")
tcnt = C.Counter(r["relation_code"] for r in R if r["split"] == "test")
print("  ", dict(sorted(tcnt.items())), "| below 15:", {k: v for k, v in tcnt.items() if v < 15} or "none")
print("  relation re-tagged vs claimed:", pct(sum(r['relation_code'] != r['relation_claimed'] for r in R), n), "| blind audit polarity conflicts flagged:", sum(r["audit_polarity_conflict"] for r in R))
print("\n-- REALISM vs REAL PRODUCTION --")
q = lambda a: np.percentile(a, [10, 50, 90]).astype(int).tolist()
print(f"  ingredient words mean {np.mean([len(s.split()) for s in ing]):.1f} (real 2.3) | comma clause {pct(sum(',' in s for s in ing), n)} (real 12%) | note {pct(sum('(' in s for s in ing), n)} (real 1%)")
print(f"  grams p10/50/90 {q(qty)} (real [10,100,400]) | max {int(qty.max())}")
print("\n-- DIFFICULTY SANITY: real 80-program committee (fit on REAL val) error by tier, vs intended labels --")
sys.path.insert(0, str(D)); import pipeline as P
progs = P.load_programs_from_dir(str(D / "programs")); val = P.load_jsonl(str(DATA / "val.jsonl"))
with contextlib.redirect_stderr(io.StringIO()):
    pipe = P.fit(val, progs); hard, _ = P.predict(R, progs, pipe)
print("  overall accuracy %.3f" % np.mean(hard == y))
for t in ("easy", "medium", "hard", "edge"):
    m = np.array([r["tier"] == t for r in R]); print(f"  {t:6s} error {1-np.mean(hard[m]==y[m]):.2f} (n={m.sum()})")
