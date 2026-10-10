"""
Pointwise-binary PAJAMA modeling for the substitutability judge.

This is the single-score analog of ``demo/pipeline.py`` / ``pajama_workflow/run.py``.

Key difference from upstream PAJAMA (which is PAIRWISE):
  * Upstream scores two responses and thresholds the *difference* `diff = norm(s1) - norm(s2)`
    around 0 (the intrinsic decision point), tuning the abstention band `tau`.
  * Here each program scores ONE pair `judging_function(ingredient, usda_match) -> float`
    (higher = more substitutable). There is no intrinsic decision point, so we tune a
    per-program decision threshold `theta` on the normalized [0,1] score, with an optional
    fixed abstention margin `band` producing a dead-zone [theta - band, theta + band].

Vote convention in the Snorkel label matrix (cardinality=2):
    1  = substitutable        (norm_score  > theta + band)
    0  = not substitutable    (norm_score  < theta - band)
   -1  = abstain              (inside dead-zone, or score missing)
Ground-truth labels: 1 = substitutable, 0 = not. `soft = predict_proba[:, 1]` = P(substitutable).
"""

from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from snorkel.labeling import LFAnalysis
from snorkel.labeling.model import LabelModel, MajorityLabelVoter

SNORKEL_CARDINALITY = 2
SNORKEL_EPOCHS = 500
SNORKEL_SEED = 123
SNORKEL_L2 = 0.01
SNORKEL_LR = 0.01
MIN_ACCURACY_THRESHOLD = 0.50
# Candidate per-program decision thresholds on the normalized [0, 1] score.
THRESHOLD_CANDIDATES = np.round(np.arange(0.10, 0.901, 0.05), 4)


# ── Program loading / execution ──────────────────────────────────────────


@dataclass
class Program:
    program_id: int
    filename: str
    code: str
    fn: Any = None
    status: str = "success"

    @property
    def display_name(self) -> str:
        return f"judge_{self.program_id}"


def compile_program(code: str):
    """Compile a judge program string and return its judging_function(ingredient, usda_match)."""
    ns: dict = {}
    exec(compile(code, "<judge>", "exec"), ns)
    fn = ns.get("judging_function")
    if fn is None:
        raise ValueError("Program does not define judging_function(ingredient, usda_match)")
    return fn


def load_programs_from_dir(judges_dir: str | Path) -> list[Program]:
    judges_dir = str(judges_dir)
    files = sorted(
        (f for f in os.listdir(judges_dir) if f.startswith("judge_") and f.endswith(".py")),
        key=lambda f: int(f[len("judge_"): -len(".py")]),
    )
    programs: list[Program] = []
    for fname in files:
        pid = int(fname[len("judge_"): -len(".py")])
        with open(os.path.join(judges_dir, fname), encoding="utf-8") as f:
            code = f.read()
        try:
            fn = compile_program(code)
            status = "success"
        except Exception as exc:  # noqa: BLE001
            fn, status = None, f"compile_error: {exc}"
        programs.append(Program(program_id=pid, filename=fname, code=code, fn=fn, status=status))
    return programs


def load_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def labels_of(rows: list[dict]) -> np.ndarray:
    return np.array([int(r["label"]) for r in rows], dtype=int)


# ── Scoring ──────────────────────────────────────────────────────────────


def collect_scores(rows: list[dict], programs: list[Program], progress_cb=None) -> np.ndarray:
    """Score every (ingredient, usda_match) with every program. Returns (n, m); NaN on failure."""
    n, m = len(rows), len(programs)
    S = np.full((n, m), np.nan)
    for i, row in enumerate(rows):
        ing = str(row.get("ingredient", ""))
        usda = str(row.get("usda_match", ""))
        for j, p in enumerate(programs):
            if p.fn is None:
                continue
            try:
                S[i, j] = float(p.fn(ing, usda))
            except Exception:  # noqa: BLE001
                pass
        if progress_cb is not None:
            progress_cb(i + 1, n)
    return S


# ── Normalization ─────────────────────────────────────────────────────────


def compute_norm_params(S: np.ndarray) -> list[tuple[float, float]]:
    """Per-program robust min-max bounds (P1/P99) over finite scores."""
    m = S.shape[1]
    params: list[tuple[float, float]] = []
    for j in range(m):
        col = S[:, j]
        finite = col[np.isfinite(col)]
        if finite.size > 1 and np.ptp(finite) > 0:
            lo = float(np.percentile(finite, 1))
            hi = float(np.percentile(finite, 99))
            if hi <= lo:
                lo, hi = float(finite.min()), float(finite.max())
                if hi == lo:
                    hi = lo + 1.0
        else:
            lo, hi = 0.0, 1.0
        params.append((lo, hi))
    return params


def normalize(S: np.ndarray, params: list[tuple[float, float]]) -> np.ndarray:
    """Map each program's scores into [0, 1]; NaN preserved."""
    n, m = S.shape
    out = np.full((n, m), np.nan)
    for j in range(m):
        lo, hi = params[j]
        rng = hi - lo
        col = S[:, j]
        if rng > 0:
            out[:, j] = np.clip((col - lo) / rng, 0.0, 1.0)
        else:
            out[:, j] = np.where(np.isnan(col), np.nan, 0.5)
        out[np.isnan(col), j] = np.nan
    return out


# ── Per-program decision thresholding ─────────────────────────────────────


def apply_decision(norm_col: np.ndarray, theta: float, band: float = 0.0) -> np.ndarray:
    """Vote per row: 1 (sub) above theta+band, 0 (not) below theta-band, -1 abstain/NaN."""
    votes = np.full(norm_col.shape, -1, dtype=int)
    votes[norm_col > theta + band] = 1
    votes[norm_col < theta - band] = 0
    votes[np.isnan(norm_col)] = -1
    return votes


def tune_thresholds(
    val_norm: np.ndarray,
    y_val: np.ndarray,
    candidates: np.ndarray = THRESHOLD_CANDIDATES,
    band: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Grid-search a per-program decision threshold maximizing covered-row val accuracy."""
    m = val_norm.shape[1]
    best_t = np.full(m, 0.5)
    best_acc = np.zeros(m)
    for j in range(m):
        top_acc, top_t = -1.0, 0.5
        for t in candidates:
            votes = apply_decision(val_norm[:, j], float(t), band)
            valid = votes != -1
            if valid.sum() == 0:
                continue
            a = accuracy_score(y_val[valid], votes[valid])
            if a > top_acc or (a == top_acc and float(t) < top_t):
                top_acc, top_t = a, float(t)
        best_t[j] = top_t
        best_acc[j] = max(top_acc, 0.0)
    return best_t, best_acc


def build_label_matrix(
    norm: np.ndarray, cols: list[int], thresholds: np.ndarray, band: float = 0.0
) -> np.ndarray:
    n = norm.shape[0]
    M = np.full((n, len(cols)), -1, dtype=int)
    for c, j in enumerate(cols):
        M[:, c] = apply_decision(norm[:, j], float(thresholds[j]), band)
    return M


# ── Metrics ────────────────────────────────────────────────────────────────


def binary_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Metrics over covered rows (y_pred != -1); positive class = 1 (substitutable)."""
    covered = y_pred != -1
    cov = float(covered.mean()) if len(covered) else 0.0
    if covered.sum() == 0:
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "coverage": 0.0}
    yt, yp = y_true[covered], y_pred[covered]
    return {
        "accuracy": float(accuracy_score(yt, yp)),
        "precision": float(precision_score(yt, yp, pos_label=1, zero_division=0)),
        "recall": float(recall_score(yt, yp, pos_label=1, zero_division=0)),
        "f1": float(f1_score(yt, yp, pos_label=1, zero_division=0)),
        "coverage": cov,
    }


# ── Full pipeline ───────────────────────────────────────────────────────────


@dataclass
class FittedPipeline:
    norm_params: list[tuple[float, float]]
    best_thresholds: np.ndarray
    best_accuracies: np.ndarray
    selected_cols: list[int]
    selected_program_ids: list[int]
    band: float
    label_model: Any
    best_k: int
    summary: dict = field(default_factory=dict)


def _fit_label_model(M: np.ndarray, y_dev: np.ndarray | None, epochs: int):
    """Fit a Snorkel LabelModel robustly.

    Snorkel can throw "Loss is NaN" on near-degenerate label matrices; retry at
    progressively lower learning rates, then fall back to MajorityLabelVoter.
    """
    if M.shape[1] < 3:
        return MajorityLabelVoter(cardinality=SNORKEL_CARDINALITY)
    for lr in (SNORKEL_LR, 0.001, 0.0001):
        try:
            lm = LabelModel(cardinality=SNORKEL_CARDINALITY, verbose=False)
            fit_kwargs = dict(L_train=M, n_epochs=epochs, l2=SNORKEL_L2, lr=lr, seed=SNORKEL_SEED)
            if y_dev is not None:
                fit_kwargs["Y_dev"] = y_dev
            lm.fit(**fit_kwargs)
            return lm
        except Exception:  # noqa: BLE001
            continue
    return MajorityLabelVoter(cardinality=SNORKEL_CARDINALITY)


def fit(
    val_rows: list[dict],
    programs: list[Program],
    *,
    band: float = 0.0,
    min_accuracy: float = MIN_ACCURACY_THRESHOLD,
    candidates: np.ndarray = THRESHOLD_CANDIDATES,
) -> FittedPipeline:
    """Stages 2-6 on the validation split: normalize -> tune -> filter -> top-k -> Snorkel."""
    y_val = labels_of(val_rows)
    S_val = collect_scores(val_rows, programs)

    norm_params = compute_norm_params(S_val)
    val_norm = normalize(S_val, norm_params)

    best_thresholds, best_accuracies = tune_thresholds(val_norm, y_val, candidates, band)

    surviving = np.where(best_accuracies >= min_accuracy)[0]
    ranked_surv = [int(i) for i in np.argsort(best_accuracies)[::-1] if best_accuracies[i] >= min_accuracy]

    # Top-k sweep: pick the k with best covered val agreement.
    best_k, best_agree = max(len(ranked_surv), 1), -1.0
    for k in range(1, len(ranked_surv) + 1):
        try:
            cols = ranked_surv[:k]
            M_k = build_label_matrix(val_norm, cols, best_thresholds, band)
            lm_k = _fit_label_model(M_k, y_val if k >= 3 else None, epochs=200)
            yh = lm_k.predict(L=M_k, tie_break_policy="random")
        except Exception:  # noqa: BLE001
            continue
        v = yh != -1
        if v.sum() > 0:
            agree = accuracy_score(y_val[v], yh[v])
            if agree > best_agree:
                best_agree, best_k = agree, k

    selected_cols = ranked_surv[:best_k] if ranked_surv else []
    M_val = build_label_matrix(val_norm, selected_cols, best_thresholds, band)
    label_model = _fit_label_model(M_val, y_val if best_k >= 3 else None, epochs=SNORKEL_EPOCHS)

    summary = {
        "task": "substitutability",
        "n_total_programs": len(programs),
        "n_surviving_programs": int(len(surviving)),
        "best_k": int(best_k),
        "band": band,
        "val_best_agreement": round(float(best_agree), 4),
        "selected_program_ids": [programs[c].program_id for c in selected_cols],
        "selected_thresholds": [round(float(best_thresholds[c]), 4) for c in selected_cols],
        "selected_val_accuracies": [round(float(best_accuracies[c]), 4) for c in selected_cols],
    }
    return FittedPipeline(
        norm_params=norm_params,
        best_thresholds=best_thresholds,
        best_accuracies=best_accuracies,
        selected_cols=selected_cols,
        selected_program_ids=[programs[c].program_id for c in selected_cols],
        band=band,
        label_model=label_model,
        best_k=int(best_k),
        summary=summary,
    )


def predict(rows: list[dict], programs: list[Program], pipe: FittedPipeline) -> tuple[np.ndarray, np.ndarray]:
    """Apply a fitted pipeline. Returns (hard in {-1,0,1}, soft = P(substitutable), NaN if abstained)."""
    S = collect_scores(rows, programs)
    norm = normalize(S, pipe.norm_params)
    M = build_label_matrix(norm, pipe.selected_cols, pipe.best_thresholds, pipe.band)

    n = M.shape[0]
    hard = np.full(n, -1, dtype=int)
    soft = np.full(n, np.nan)
    covered = ~(M == -1).all(axis=1)
    if covered.any():
        hard[covered] = pipe.label_model.predict(L=M[covered], tie_break_policy="abstain")
        proba = pipe.label_model.predict_proba(L=M[covered])
        soft[covered] = proba[:, 1]
    return hard, soft


def program_diagnostics(rows: list[dict], programs: list[Program], pipe: FittedPipeline) -> dict:
    """Per-selected-program coverage + conflict (LFAnalysis) on the given rows."""
    S = collect_scores(rows, programs)
    norm = normalize(S, pipe.norm_params)
    M = build_label_matrix(norm, pipe.selected_cols, pipe.best_thresholds, pipe.band)
    coverage = (M != -1).mean(axis=0)
    try:
        conflicts = LFAnalysis(L=M).lf_summary()["Conflicts"].to_numpy()
    except Exception:  # noqa: BLE001
        conflicts = np.zeros(len(pipe.selected_cols))
    return {
        "selected_program_ids": pipe.selected_program_ids,
        "coverage": [round(float(c), 4) for c in coverage],
        "conflicts": [round(float(c), 4) for c in conflicts],
    }
