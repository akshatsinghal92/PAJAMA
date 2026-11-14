import re

# Physical/preservation states and the lexical cues that signal them.
_STATE_CUES = {
    "fresh": ["fresh", "raw", "uncooked", "ripe", "whole"],
    "frozen": ["frozen", "freeze", "thawed", "defrosted"],
    "canned": ["canned", "tinned", "can of", "in syrup", "in juice", "in water", "in oil", "drained", "sauce", "applesauce"],
    "dried": ["dried", "dry", "dehydrated", "sun-dried", "sundried", "ground", "flakes", "flaked"],
    "jarred": ["jarred", "jar", "bottled", "pickled", "brined", "marinated"],
    "paste": ["paste", "puree", "pureed", "concentrate", "concentrated", "tube"],
    "powder": ["powder", "powdered", "granulated", "granules"],
    "liquid": ["broth", "stock", "juice", "milk", "liquid"],
    "prepared": ["soup", "ready-to-serve", "ready to serve", "prepared", "mix", "condensed", "instant"],
    "cooked": ["cooked", "fried", "roasted", "baked", "boiled", "toasted", "grilled", "smoked", "leftover", "steamed"],
}

# Cost of going from ingredient-state (row) to usda-state (col); 0 = same/recoverable, 1 = severe.
_TRANSITION = {
    ("fresh", "frozen"): 0.25, ("frozen", "fresh"): 0.2,
    ("fresh", "canned"): 0.55, ("canned", "fresh"): 0.5,
    ("fresh", "dried"): 0.85, ("dried", "fresh"): 0.8,
    ("fresh", "powder"): 0.9, ("powder", "fresh"): 0.9,
    ("fresh", "paste"): 0.6, ("paste", "fresh"): 0.55,
    ("fresh", "jarred"): 0.6, ("jarred", "fresh"): 0.6,
    ("fresh", "prepared"): 0.8, ("prepared", "fresh"): 0.8,
    ("fresh", "cooked"): 0.5, ("cooked", "fresh"): 0.55,
    ("frozen", "canned"): 0.5, ("canned", "frozen"): 0.5,
    ("frozen", "dried"): 0.85, ("dried", "frozen"): 0.85,
    ("canned", "jarred"): 0.15, ("jarred", "canned"): 0.15,
    ("canned", "paste"): 0.45, ("paste", "canned"): 0.45,
    ("dried", "powder"): 0.3, ("powder", "dried"): 0.3,
    ("paste", "powder"): 0.7, ("powder", "paste"): 0.7,
    ("liquid", "prepared"): 0.75, ("prepared", "liquid"): 0.7,
    ("liquid", "powder"): 0.6, ("powder", "liquid"): 0.6,
    ("liquid", "paste"): 0.55, ("paste", "liquid"): 0.55,
    ("cooked", "frozen"): 0.4, ("frozen", "cooked"): 0.4,
    ("cooked", "canned"): 0.35, ("canned", "cooked"): 0.35,
}

_STOP = set("""g kg mg ml l oz lb cup cups tbsp tsp of and or the a an for with without to
in on optional serving chopped diced sliced minced cubed shredded grated peeled
large small medium about plus more taste ns as major""".split())


def _clean(text):
    text = str(text or "").lower()
    text = re.sub(r"\(([^)]*)\)", r" \1 ", text)
    text = re.sub(r"^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _states(text):
    found = {}
    for state, cues in _STATE_CUES.items():
        hits = 0
        for cue in cues:
            if " " in cue or "-" in cue:
                if cue in text:
                    hits += 1
            elif re.search(r"\b" + re.escape(cue) + r"\b", text):
                hits += 1
        if hits:
            found[state] = hits
    return found


def _stems(text):
    toks = re.findall(r"[a-z]+", text)
    out = set()
    for t in toks:
        if t in _STOP or len(t) < 3:
            continue
        if t.endswith("ies"):
            t = t[:-3] + "y"
        elif t.endswith("es") and len(t) > 4:
            t = t[:-2]
        elif t.endswith("s") and len(t) > 3:
            t = t[:-1]
        out.add(t)
    return out


def _pair_cost(a, b):
    if a == b:
        return 0.0
    return _TRANSITION.get((a, b), 0.65)


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usd = _clean(usda_match)
        if not ing or not usd:
            return 0.0

        ing_states = _states(ing)
        usd_states = _states(usd)

        # Nearest-state matching cost (like a minimal assignment, greedy).
        if not ing_states and not usd_states:
            form_cost = 0.15
        elif not ing_states:
            # Ingredient unqualified: fresh/raw is the default reading.
            form_cost = min(_pair_cost("fresh", s) for s in usd_states)
        elif not usd_states:
            form_cost = min(_pair_cost(s, "fresh") for s in ing_states) * 0.8
        else:
            fwd = [min(_pair_cost(a, b) for b in usd_states) for a in ing_states]
            bwd = [min(_pair_cost(a, b) for a in ing_states) for b in usd_states]
            form_cost = 0.6 * max(fwd) + 0.4 * (sum(bwd) / len(bwd))

        # Concentration-altering mismatches get an extra hit.
        concentrated = {"dried", "powder", "paste", "prepared"}
        if (set(ing_states) & concentrated) != (set(usd_states) & concentrated):
            if set(ing_states) ^ set(usd_states):
                form_cost += 0.1

        form_score = max(0.0, 1.0 - form_cost)

        # Identity anchor: the primary USDA food (before first comma) should appear.
        primary = usd.split(",")[0]
        p_stems = _stems(primary)
        i_stems = _stems(ing)
        u_stems = _stems(usd)
        if p_stems:
            anchor = len(p_stems & i_stems) / len(p_stems)
        else:
            anchor = 0.0
        partial = 0.0
        for p in p_stems:
            for t in i_stems:
                if len(p) >= 4 and len(t) >= 4 and (p.startswith(t[:4]) or t.startswith(p[:4])):
                    partial = max(partial, 0.6)
        anchor = max(anchor, partial)
        coverage = len(i_stems & u_stems) / max(1, len(i_stems))

        identity = 0.65 * anchor + 0.35 * coverage

        score = 100.0 * (0.55 * form_score + 0.45 * identity)
        # Severe form mismatch caps the score.
        if form_cost > 0.75:
            score = min(score, 40.0)
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
