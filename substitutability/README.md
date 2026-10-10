# Substitutability — pointwise-binary PAJAMA adaptation

Adapts PAJAMA (pairwise preference) to a **pointwise binary** judge that reproduces the
USDA-ingredient *substitutability* LLM judge from `backend/rerun_subjudge.py`:

> `judging_function(ingredient, usda_match) -> float`  (higher = more substitutable)

Self-contained; **no upstream PAJAMA files are modified**.

## Pairwise → pointwise, in one table

| PAJAMA (upstream) | Here |
|---|---|
| `judging_function(query, response)` scored twice (s1, s2) | `judging_function(ingredient, usda_match)` scored once (S) |
| `diff = norm(s1) − norm(s2)`, threshold the sign | normalize score to [0,1], tune a per-program decision threshold `theta` |
| tune abstention band `tau` (decision point fixed at 0) | tune `theta` (band `--band` optional, default 0) |
| label from `verdict ∈ {1,2}` | label from `substitutable ∈ {True,False}` → {1,0} |
| Snorkel `LabelModel(cardinality=2)`, top-k, filter ≥0.50, `predict_proba[:,1]` | **unchanged** |

## Run

```bash
cd substitutability
python data_prep.py                      # build data/{val,test}.jsonl from the labeled CSV
python run.py                            # fit on val + evaluate on test, using baseline_programs/
```

`run.py` reports accuracy / precision / recall / F1 / coverage of the aggregated committee
against the LLM judge's labels, plus a majority baseline, and writes
`outputs/evaluation_metrics.json` and `outputs/test_predictions.jsonl`.

## Synthesize real programs (optional, needs an LLM key)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python generate_programs.py              # 10 substitutability rubrics × 8 variants -> programs/
python run.py --judges programs
```

## Files

| File | Role |
|---|---|
| `heuristics.py` | 10 substitutability rubrics (steer synthesis) |
| `data_prep.py` | labeled CSV → stratified val/test JSONL |
| `generate_programs.py` | LLM program synthesis (pointwise binary) |
| `pipeline.py` | modeling: score → normalize → tune θ → filter → top-k → Snorkel |
| `run.py` | fit on val, evaluate on test, dump metrics |
| `baseline_programs/` | 4 deterministic judges so the pipeline runs with no API key |

## Notes
- `generate_programs.py` targets `claude-opus-4-6` (as upstream) — verify the model id/params
  against the current Anthropic API before running.
- Reuses PAJAMA's `requirements.txt` (snorkel, scikit-learn, numpy; anthropic only for synthesis).
