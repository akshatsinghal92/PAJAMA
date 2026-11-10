"""Run the production substitutability prompt (verbatim) with gpt-oss-120b on Groq.
Usage: ANTHROPIC-free; key from env GROQ_API_KEY only.  judge_groq.py [--limit N]
Inputs : data_synth_v2/prejudge_input.jsonl + robustness.jsonl + 10% re-run sample
Output : data_synth_v2/judge_out.jsonl  (resumable; one line per call key)
"""
import json, os, random, sys, time, threading, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
D = Path(__file__).resolve().parent.parent / "data_synth_v2"
MODEL = "openai/gpt-oss-120b"
KEY = os.environ.get("GROQ_API_KEY", "")
PACE = float(os.environ.get("PACE", 4.6))   # seconds between call starts (~13/min stays under 8k TPM)
_pl, _next, STOP = threading.Lock(), [0.0], threading.Event()

def prompt(ingredient, usda_match):
    return (f'You are evaluating whether a USDA food database entry is an acceptable match '
        f'for a recipe ingredient.\n\n'
        f'Ingredient: "{ingredient}"\n'
        f'USDA match: "{usda_match}"\n\n'
        f'A match counts as "substitutable" if and only if BOTH conditions hold:\n'
        f'  1. It could be used in place of the ingredient without changing how the dish is prepared.\n'
        f'  2. A person eating the dish would not notice any difference in taste, texture, or appearance.\n\n'
        f'If the match would alter cooking method, change the dish\'s flavour, texture, or appearance, '
        f'or if a diner would notice they were eating something different, it is not substitutable.\n\n'
        f'Reason through whether both conditions are met. '
        f'Reply with JSON only, no markdown:\n'
        f'{{"reasoning": "<step-by-step analysis>", "substitutable": true_or_false}}')

def rows():
    base = [json.loads(l) for l in open(D / "prejudge_input.jsonl")]
    rob = [json.loads(l) for l in open(D / "robustness.jsonl")]
    items = [(r["id"], r["ingredient"], r["usda_match"]) for r in base + rob]
    rr = random.Random(7).sample(base, len(base) // 10)
    items += [(r["id"] + "#rerun", r["ingredient"], r["usda_match"]) for r in rr]
    return items

def call(ing, usda):
    body = json.dumps({"model": MODEL, "temperature": 0, "max_completion_tokens": 3000,
                       "messages": [{"role": "user", "content": prompt(ing, usda)}]}).encode()
    for attempt in range(8):
        if STOP.is_set(): return {"error": "stopped: daily limit"}
        with _pl:
            w = max(0, _next[0] - time.time()); _next[0] = max(time.time(), _next[0]) + PACE
        time.sleep(w)
        req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", body,
            {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "User-Agent": "pajama-datagen/1.0"})
        try:
            return json.load(urllib.request.urlopen(req, timeout=90))
        except urllib.error.HTTPError as e:
            wait = float(e.headers.get("retry-after") or 0) or min(60, 2 ** attempt * 2)
            if e.code not in (429, 500, 502, 503): return {"error": f"{e.code} {e.read()[:200]!r}"}
            if e.code == 429:
                msg = e.read().decode("utf8", "ignore")
                print("429:", msg[:300].replace("\n", " "), "| retry-after", wait, flush=True)
                if "per day" in msg or "(RPD)" in msg or "(TPD)" in msg:
                    STOP.set(); print("DAILY LIMIT reached", flush=True); return {"error": "stopped: daily limit"}
                time.sleep(min(wait, 90) + random.random()); continue
            time.sleep(wait + random.random())
        except Exception as e:
            time.sleep(2 ** attempt)
    return {"error": "retries exhausted"}

def parse(text):
    t = text.strip().strip("`")
    if t.startswith("json"): t = t[4:]
    try:
        o = json.loads(t[t.index("{"): t.rindex("}") + 1])
        v = o.get("substitutable")
        if isinstance(v, str): v = v.lower() == "true"
        return o.get("reasoning", ""), v
    except Exception:
        return text, None

def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    out = D / ("judge_test.jsonl" if limit else "judge_out.jsonl")
    done = set()
    if out.exists():
        done = {json.loads(l)["key"] for l in open(out) if json.loads(l).get("judge_label") is not None}
    todo = [x for x in rows() if x[0] not in done][:limit]
    print(f"{len(todo)} to run ({len(done)} done)")
    lock, n = threading.Lock(), [0]
    f = open(out, "a")
    def work(x):
        k, ing, usda = x
        r = call(ing, usda)
        if "error" in r: rec = {"key": k, "judge_label": None, "error": r["error"]}
        else:
            reasoning, v = parse(r["choices"][0]["message"].get("content") or "")
            rec = {"key": k, "judge_label": None if v is None else int(bool(v)), "reasoning": reasoning,
                   "tokens": r.get("usage", {}).get("total_tokens")}
        with lock:
            f.write(json.dumps(rec) + "\n"); f.flush(); n[0] += 1
            if n[0] % 100 == 0: print(n[0], flush=True)
    with ThreadPoolExecutor(int(os.environ.get("WORKERS", 8))) as ex: list(ex.map(work, todo))
if __name__ == "__main__":
    main()
