import re


_ALIASES = {
    "favas": "broadbean", "fava": "broadbean", "broadbeans": "broadbean",
    "puree": "sauce", "purée": "sauce", "applesauce": "apple sauce",
    "chile": "chili", "chilli": "chili", "garbanzo": "chickpea",
    "cilantro": "coriander", "scallion": "onion", "scallions": "onion",
    "prawn": "shrimp", "prawns": "shrimp", "courgette": "zucchini",
    "aubergine": "eggplant", "yoghurt": "yogurt",
}

_PREP = {
    "fresh", "frozen", "dried", "dry", "chopped", "minced", "sliced", "diced",
    "cubed", "thawed", "grated", "shredded", "peeled", "raw", "cooked",
    "large", "small", "medium", "whole", "ground", "crushed", "finely",
    "roughly", "boneless", "skinless", "nonfat", "lowfat", "low", "fat",
    "organic", "plain", "regular", "packed", "softened", "melted", "leaves",
    "leaf", "of", "the", "a", "an", "to", "taste", "for", "from", "tube",
    "jar", "can", "canned", "uncooked", "unsalted", "salted", "hot",
}


def _stem(w):
    w = _ALIASES.get(w, w)
    if " " in w:
        return w
    for suf in ("ies", "oes", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            if suf in ("oes", "es") and not w.endswith("ses"):
                return w[:-2]
            return w[:-1]
    return w


def _words(text):
    text = text.lower().replace("é", "e")
    toks = re.findall(r"[a-z]+", text)
    out = []
    for t in toks:
        s = _stem(t)
        out.extend(s.split())
    return out


def _clean_ingredient(ing):
    s = ing.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", s)
    main, _, post = s.partition(",")
    return main, post


def _grams(word):
    w = "#" + word + "#"
    return {w[i:i + 3] for i in range(len(w) - 2)}


def _sim(a, b):
    if a == b:
        return 1.0
    ga, gb = _grams(a), _grams(b)
    if not ga or not gb:
        return 0.0
    return 2.0 * len(ga & gb) / (len(ga) + len(gb))


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        main, post = _clean_ingredient(str(ingredient))
        core = [w for w in _words(main) if w not in _PREP]
        post_core = [w for w in _words(post) if w not in _PREP]
        if not core:
            core = post_core
        if not core:
            return 0.0

        segs = [seg.strip() for seg in str(usda_match).split(",") if seg.strip()]
        if not segs:
            return 0.0
        seg_words = [[w for w in _words(seg) if w not in _PREP] for seg in segs]
        primary = seg_words[0]
        # positional weights: the primary food segment matters most
        weights = [1.0, 0.8, 0.6] + [0.35] * max(0, len(seg_words) - 3)

        head = core[-1]          # head noun of the ingredient phrase
        modifiers = core[:-1] + post_core

        # best alignment of the head noun against USDA words, by position
        head_best = 0.0
        for i, ws in enumerate(seg_words):
            for w in ws:
                v = _sim(head, w) * weights[i]
                if v > head_best:
                    head_best = v

        # primary segment must be covered by the ingredient words
        all_ing = core + post_core
        if primary:
            cover = sum(max(_sim(p, q) for q in all_ing) for p in primary) / len(primary)
        else:
            cover = 0.0

        # modifiers recall in the USDA entry
        usda_flat = [w for ws in seg_words for w in ws]
        if modifiers and usda_flat:
            mod = sum(1.0 if max(_sim(m, u) for u in usda_flat) >= 0.6 else 0.0
                      for m in modifiers) / len(modifiers)
        else:
            mod = 0.6

        score = 5.5 * head_best + 3.0 * cover + 1.5 * mod

        # identity gate: if head noun hardly resembles anything, core food differs
        if head_best < 0.45:
            score *= 0.35

        # mixed/compound ingredient penalty
        low = str(ingredient).lower()
        if re.search(r"\band\b|\bmixed\b|\bblend\b|&", low):
            score -= 2.0

        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
