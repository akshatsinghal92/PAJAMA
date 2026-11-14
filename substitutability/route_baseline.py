"""
Routing at a fixed escalation budget on top of the paper-baseline committee.

Implements the router family from ROUTING_AND_ABSTENTION.md and
PROGRAM_IMPROVEMENT_AND_ROUTING.md: rank rows by how likely the committee is to be wrong, send the
top BUDGET share to the LLM judge, keep the committee's answer for the rest.

Protocol (no test leakage):
  * Committee: fit on the 380-row paper validation split (same as run.py).
  * Router training set: the 943 rows of the held-out `router` split that sit in the paper test
    pool (foods disjoint from the evaluation rows). Router target: committee_wrong.
  * Evaluation set: the remaining 2,856 test rows. The router never sees them.
  * Method selection: by 5-fold food-grouped cross-validation on the router training set only.
    The evaluation set is scored once, after the choice.
  * Escalated rows count as correct (they receive the LLM judge's stored label), the
    convention used in ROUTING_AND_ABSTENTION.md. Labels here are Haiku v3.

Usage: python route_baseline.py [--budget 0.25] [--judges programs_synth_v2]
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

import pipeline as P

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
D = HERE / "data_synth_v2"


def rows_of(p):
    return P.load_jsonl(p)


# ── committee state ─────────────────────────────────────────────────────────


def committee_state(rows, programs, pipe, cache: Path | None):
    if cache and cache.exists():
        S = np.load(cache)
    else:
        S = P.collect_scores(rows, programs)
        if cache:
            np.save(cache, S)
    norm = P.normalize(S, pipe.norm_params)
    all_cols = list(range(norm.shape[1]))
    V_all = P.build_label_matrix(norm, all_cols, pipe.best_thresholds, pipe.band)  # 80 votes
    M_sel = P.build_label_matrix(norm, pipe.selected_cols, pipe.best_thresholds, pipe.band)
    proba = np.full(len(rows), 0.5)
    cov = ~(M_sel == -1).all(axis=1)
    if cov.any():
        proba[cov] = pipe.label_model.predict_proba(L=M_sel[cov])[:, 1]
    return norm, V_all, M_sel, proba


def vote_var(M):
    """Disagreement among non-abstaining votes: p(1-p) of the share voting 1."""
    v = np.where(M == -1, np.nan, M).astype(float)
    p = np.nanmean(v, axis=1)
    p = np.where(np.isnan(p), 0.5, p)
    return p * (1 - p)


def committee_features(rows, norm, V_all, M_sel, proba):
    f = {}
    f["post"] = proba
    f["margin"] = np.abs(proba - 0.5)
    f["vvar_sel"] = vote_var(M_sel)
    f["vvar_all"] = vote_var(V_all)
    valid = np.where(V_all == -1, np.nan, V_all).astype(float)
    f["mean_vote_all"] = np.nan_to_num(np.nanmean(valid, axis=1), nan=0.5)
    f["abstain_all"] = (V_all == -1).mean(axis=1)
    nz = np.nan_to_num(norm, nan=0.5)
    f["norm_mean"], f["norm_std"] = nz.mean(1), nz.std(1)
    f["norm_min"], f["norm_max"] = nz.min(1), nz.max(1)
    tok = lambda s: set("".join(c if c.isalnum() else " " for c in s.lower()).split())
    jac = []
    for r in rows:
        a, b = tok(r["ingredient"]), tok(r["usda_match"])
        jac.append(len(a & b) / max(1, len(a | b)))
    f["jaccard"] = np.array(jac)
    f["len_ing"] = np.array([len(r["ingredient"].split()) for r in rows], float)
    f["len_usda"] = np.array([len(r["usda_match"].split()) for r in rows], float)
    names = list(f)
    X = np.column_stack([f[k] for k in names] + [nz])  # + each program's normalized score
    return X, names


class TextFeats:
    """Char n-gram TF-IDF -> SVD(12) per string, |diff| (12), cosine (1). Unsupervised."""

    def fit(self, rows):
        self.v1 = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2).fit([r["ingredient"] for r in rows])
        self.v2 = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2).fit([r["usda_match"] for r in rows])
        self.s1 = TruncatedSVD(12, random_state=0).fit(self.v1.transform([r["ingredient"] for r in rows]))
        self.s2 = TruncatedSVD(12, random_state=0).fit(self.v2.transform([r["usda_match"] for r in rows]))
        self.vj = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2).fit(
            [r["ingredient"] for r in rows] + [r["usda_match"] for r in rows])
        return self

    def transform(self, rows):
        a = self.s1.transform(self.v1.transform([r["ingredient"] for r in rows]))
        b = self.s2.transform(self.v2.transform([r["usda_match"] for r in rows]))
        ja = self.vj.transform([r["ingredient"] for r in rows])
        jb = self.vj.transform([r["usda_match"] for r in rows])
        cos = np.asarray(ja.multiply(jb).sum(axis=1)).ravel()
        return np.column_stack([a, b, np.abs(a - b), cos])


# ── routing evaluation ──────────────────────────────────────────────────────


def acc_at_budget(score_wrong, committee_wrong, budget):
    """Escalate the top `budget` share by score; escalated rows become correct."""
    n = len(score_wrong)
    k = int(round(budget * n))
    order = np.argsort(-score_wrong, kind="stable")
    wrong = committee_wrong.copy().astype(bool)
    wrong[order[:k]] = False
    return 1.0 - wrong.mean()


def make_models():
    return {
        "logreg": lambda: LogisticRegression(C=0.3, max_iter=2000),
        "gbm": lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=250,
                                                      l2_regularization=1.0, random_state=0),
    }


def fit_predict(kind, Xtr, ytr, Xte):
    m = make_models()[kind]()
    if kind == "logreg":
        sc = StandardScaler().fit(Xtr)
        m.fit(sc.transform(Xtr), ytr)
        return m.predict_proba(sc.transform(Xte))[:, 1]
    m.fit(Xtr, ytr)
    return m.predict_proba(Xte)[:, 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=0.25)
    ap.add_argument("--judges", default=str(HERE / "programs_synth_v2"))
    ap.add_argument("--out", default=str(HERE / "outputs" / "routing_paper_baseline"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    programs = P.load_programs_from_dir(args.judges)
    val = rows_of(D / "pajama_paper" / "val.jsonl")
    test = rows_of(D / "pajama_paper" / "test.jsonl")
    real = rows_of(D / "pajama" / "real_external.jsonl")
    router_ids = {r["id"] for r in rows_of(D / "pajama" / "router.jsonl")}
    rtr = [r for r in test if r["id"] in router_ids]
    ev = [r for r in test if r["id"] not in router_ids]
    print(f"committee fit rows={len(val)}  router-train={len(rtr)}  eval={len(ev)}  real={len(real)}")

    pipe = P.fit(val, programs)
    print(f"committee: surviving={pipe.summary['n_surviving_programs']} k={pipe.best_k} "
          f"programs={pipe.selected_program_ids}")

    cache = out / "_scores"
    cache.mkdir(exist_ok=True)
    sets = {"router": rtr, "eval": ev, "real": real}
    X, Y, W, COM = {}, {}, {}, {}
    for name, rows in sets.items():
        norm, V, M, proba = committee_state(rows, programs, pipe, cache / f"{name}.npy")
        X[name], names = committee_features(rows, norm, V, M, proba)
        Y[name] = P.labels_of(rows)
        pred = (proba >= 0.5).astype(int)
        W[name] = (pred != Y[name]).astype(int)
        COM[name] = dict(proba=proba, vvar_sel=vote_var(M), vvar_all=vote_var(V))
        print(f"  {name:6s} n={len(rows):5d}  committee acc={1 - W[name].mean():.4f}  errors={W[name].sum()}")

    tf = TextFeats().fit(rtr)
    T = {k: tf.transform(sets[k]) for k in sets}

    B = args.budget
    groups = np.array([r.get("core_food") or r["id"] for r in rtr])
    cands = {
        "random": None,
        "vote variance (selected committee)": "vvar_sel",
        "vote variance (all 80 programs)": "vvar_all",
        "posterior margin": "margin",
        "LogReg (committee features)": ("logreg", False),
        "LogReg + TF-IDF text": ("logreg", True),
        "GBM (committee features)": ("gbm", False),
        "GBM + TF-IDF text": ("gbm", True),
    }

    def feats(name, with_text):
        return np.column_stack([X[name], T[name]]) if with_text else X[name]

    def score(spec, tr_name, te_name, Xtr_override=None):
        if spec == "vvar_sel":
            return COM[te_name]["vvar_sel"]
        if spec == "vvar_all":
            return COM[te_name]["vvar_all"]
        if spec == "margin":
            return -np.abs(COM[te_name]["proba"] - 0.5)
        kind, txt = spec
        return fit_predict(kind, feats(tr_name, txt), W[tr_name], feats(te_name, txt))

    # 1) selection by food-grouped CV on the router-training set only
    cv = {}
    gkf = GroupKFold(n_splits=5)
    rng = np.random.default_rng(0)
    for label, spec in cands.items():
        if spec is None:
            cv[label] = float(np.mean([acc_at_budget(rng.random(len(W["router"])), W["router"], B)
                                       for _ in range(200)]))
            continue
        if isinstance(spec, str):
            cv[label] = acc_at_budget(score(spec, "router", "router"), W["router"], B)
            continue
        oof = np.zeros(len(rtr))
        for tri, tei in gkf.split(X["router"], W["router"], groups):
            kind, txt = spec
            oof[tei] = fit_predict(kind, feats("router", txt)[tri], W["router"][tri], feats("router", txt)[tei])
        cv[label] = acc_at_budget(oof, W["router"], B)
    chosen = max((k for k in cv if k != "random"), key=cv.get)

    # 2) one pass on the untouched evaluation set (and the real data), all candidates
    res = {}
    for label, spec in cands.items():
        row = {"cv_router_set": round(cv[label], 4)}
        for name in ("eval", "real"):
            if spec is None:
                a = float(np.mean([acc_at_budget(rng.random(len(W[name])), W[name], B) for _ in range(200)]))
            elif isinstance(spec, str):
                a = acc_at_budget(score(spec, name, name), W[name], B)
            else:
                a = acc_at_budget(score(spec, "router", name), W[name], B)
            row[name] = round(a, 4)
        res[label] = row
    res["oracle (upper bound)"] = {
        "cv_router_set": round(acc_at_budget(W["router"].astype(float), W["router"], B), 4),
        "eval": round(acc_at_budget(W["eval"].astype(float), W["eval"], B), 4),
        "real": round(acc_at_budget(W["real"].astype(float), W["real"], B), 4)}

    base = {n: round(1 - W[n].mean(), 4) for n in sets}
    print(f"\nescalation budget = {B:.0%}   (committee alone: {base})")
    print(f"{'method':38s} {'CV(router)':>10s} {'eval':>8s} {'real':>8s}")
    for k, v in res.items():
        mark = "  <- chosen by CV" if k == chosen else ""
        print(f"{k:38s} {v['cv_router_set']:10.4f} {v['eval']:8.4f} {v['real']:8.4f}{mark}")

    # error-ranking quality of the chosen router on eval
    from sklearn.metrics import roc_auc_score
    spec = cands[chosen]
    s_ev = score(spec, "router", "eval") if not isinstance(spec, str) else score(spec, "eval", "eval")
    auc = float(roc_auc_score(W["eval"], s_ev))
    print(f"\nchosen: {chosen}   wrong-AUC on eval = {auc:.3f}")

    # escalation needed to reach 0.95 / 0.99 agreement with the chosen router
    def esc_needed(target):
        for b in np.arange(0, 1.0001, 0.01):
            if acc_at_budget(s_ev, W["eval"], b) >= target:
                return round(float(b), 2)
        return 1.0
    needs = {"0.90": esc_needed(0.90), "0.95": esc_needed(0.95), "0.99": esc_needed(0.99)}
    print("escalation needed (chosen router, eval):", needs)

    report = {"budget": B, "committee_accuracy": base,
              "n": {"committee_fit": len(val), "router_train": len(rtr), "eval": len(ev), "real": len(real)},
              "committee": {"k": pipe.best_k, "program_ids": pipe.selected_program_ids},
              "chosen_by_cv": chosen, "wrong_auc_eval": round(auc, 4),
              "escalation_needed": needs, "results": res}
    (out / "routing_results.json").write_text(json.dumps(report, indent=2))

    # row-level output for the chosen router on eval
    with open(out / "eval_routing_predictions.jsonl", "w", encoding="utf-8") as f:
        k = int(round(B * len(ev)))
        top = set(np.argsort(-s_ev, kind="stable")[:k].tolist())
        for i, r in enumerate(ev):
            f.write(json.dumps({"id": r["id"], "ingredient": r["ingredient"], "usda_match": r["usda_match"],
                                "label": int(Y["eval"][i]), "committee_pred": int(COM["eval"]["proba"][i] >= .5),
                                "p_wrong": round(float(s_ev[i]), 4), "escalated": i in top}) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
