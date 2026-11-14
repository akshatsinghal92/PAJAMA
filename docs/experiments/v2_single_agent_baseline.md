# v2: single-agent baseline (80 programs from one shared example set)

Documented: 2026-11-13. Status: finished. This doc is a summary. The full analysis is in
`substitutability/PROGRAM_FAILURE_ANALYSIS.md`, which stays the detailed source for v2.

## 1. Question and motivation
First paper-faithful replication of the PAJAMA baseline on the synthetic ingredient to USDA
dataset `data_synth_v2` (Haiku v3 labels), plus a diagnosis of why the programs were weak. An
earlier program set (made from real few-shot examples) scored about 75% on real test data.

## 2. What changed
This is the reference point for v3 onward.

| Setting | Value |
|---|---|
| Programs | `programs_synth_v2/`, 80 programs: 10 rubrics (`heuristics.py`) x 8 variants |
| Who writes them | One agent, in one conversation, one slot after another |
| Few-shot examples | The same 10 for every program, drawn once at random from validation with seed 42. The draw had **1 substitutable and 9 not** |
| Sees other programs | Yes. The prompt lists approaches already accepted for the same rubric ("use a substantially different algorithm") |
| Similarity filter | Code text, 0.60 |
| Harness | `synth_agent_tool.py` (prompt, validate, similarity check, save, manifest) |
| Split | `prep_paper_split.py`: validation 380, test 3,799, split by core food |

## 3. How it was run
- Prompts were produced by `synth_agent_tool.py prompt <pid>` and programs submitted with
  `synth_agent_tool.py submit <pid> <file>`. The agent supplied the program text instead of an
  API call. Prompt, plan order, validation cases, 0.60 filter and retry limits match
  `generate_programs.py`.
- Baseline run with `run.py` (command in [../README.md](../README.md)) into
  `outputs/paper_baseline_synth_v2/`.

## 4. Results
- 78 of 80 programs passed the 50% validation filter. Top-k kept **3** (programs 40, 37, 33).
- Committee accuracy: **72.76%** on generated test, **74.55%** on real.
- Single programs: 47.4% to 72.3% on test, median 59%. Validation and test accuracy correlate
  0.91 across programs.
- Adding programs did not help (k = 1: 71.4%, 3: 72.8%, 8: 72.3%, 20: 69.2%, all 78: 63.2%).

## 5. Comparison
First experiment, nothing earlier to compare. See [README.md](README.md) for later versions.

## 6. Error analysis (full detail in PROGRAM_FAILURE_ANALYSIS.md)
1. **Flat default:** 30 of 80 programs gave one identical score to at least half of the test
   rows because their rule only fires when a listed word appears. On those rows accuracy is
   45 to 58%, about a coin flip.
2. **Word-overlap proxy:** 59 of 80 programs followed shared-word overlap more than the label.
   Across programs, accuracy follows how closely the score tracks overlap (correlation 0.87).
3. **List gaps:** 70 of 80 programs rely on hand-written word lists. Only 19 mention "sodium"
   and only 4 contain a synonym table. In 240 "no" rows where the USDA name adds a fat, salt or
   sugar qualifier, 57% of programs still said yes.
4. **Comma cut:** 65 of 80 programs keep only the ingredient text before the first comma.
5. **Worst and best:** the 10 worst programs say yes on 77 to 99% of rows. The 10 best are
   strict word-overlap matchers (21 to 41% yes, missing about half of true matches).
6. **Few-shot draw:** the 10 examples had 1 yes and 9 no. Scored on those rows the committee
   got 5 of 10 right. This was not the whole explanation, because the worst programs lean to
   yes, the opposite of what a no-heavy draw would cause.

## 7. Validity and caveats
- Labels are Haiku v3 judgments, so accuracy is agreement with that judge.
- An exploratory run let programs abstain when their rule was silent (treating a program's
  most common score as "no opinion"). It raised the committee to 74.0% test and 82.0% real
  with k = 11. It was a single exploratory run and `run.py` was not changed.

## 8. Conclusions and what it motivated
The paper's setting is independent API calls with their own examples, and v2 used one agent
with a shared, skewed example set. That motivated **v3**: independent agents, each with its own
random examples.

## 9. Files and reproduction
- Programs: `substitutability/programs_synth_v2/`. Harness: `synth_agent_tool.py`.
- Outputs: `outputs/paper_baseline_synth_v2/`, `outputs/routing_paper_baseline/`.
- Analysis scripts: `analysis_programs/` (`perprog.py`, `ksweep.py`, `fs.py`, `deep*.py`,
  `abst.py`), outputs in `analysis_programs/out/`.
