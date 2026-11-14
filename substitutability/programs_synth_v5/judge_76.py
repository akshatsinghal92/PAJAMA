import re

_NOISE = set("""g kg mg oz lb lbs ml l cup cups tbsp tsp optional taste garnish for to of the a an and or with in from into
about fresh large small medium piece pieces pieces extra some more less""".split())

_SLOTS = {
    "heat": {"raw": {"raw", "fresh", "uncooked"},
             "cooked": {"cooked", "boiled", "baked", "roasted", "broiled", "grilled", "simmered", "steamed", "braised", "stewed", "fried", "sauteed", "toasted"}},
    "preserve": {"dried": {"dried", "dehydrated", "dry"},
                 "frozen": {"frozen"}, "canned": {"canned", "tinned"},
                 "smoked": {"smoked", "cured"}, "pickled": {"pickled", "brined"}},
    "fat": {"lean": {"lean", "lowfat", "low-fat", "nonfat", "skim", "reduced", "light"},
            "full": {"whole", "regular", "full", "fat", "fatty"}},
    "skin": {"skin": {"skin", "skinon", "skin-on"}, "noskin": {"skinless", "boneless", "meat"}},
    "form": {"ground": {"ground", "minced", "mince", "powder", "powdered"},
             "paste": {"paste", "puree", "pate"},
             "juice": {"juice"}, "sauce": {"sauce"},
             "liquid": {"melted", "liquid"}},
    "sweet": {"sweet": {"sweetened", "sugar", "sweet"}, "unsweet": {"unsweetened", "plain"}},
    "flavor": {"vanilla": {"vanilla"}, "chocolate": {"chocolate"}, "garlic": {"garlic"},
               "vegetables": {"vegetables", "vegetable", "veggie", "veggies"},
               "meat": {"meat"}, "granola": {"granola"}},
}

_FLAT = {}
for _s, _d in _SLOTS.items():
    for _v, _ws in _d.items():
        for _w in _ws:
            _FLAT[_w] = (_s, _v)


def _toks(s):
    s = s.lower()
    s = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|oz|lb|lbs|ml|l)\b", " ", s)
    s = re.sub(r"[^a-z0-9%\- ]", " ", s)
    out = []
    for t in s.split():
        if t.endswith("ies") and len(t) > 4:
            t = t[:-3] + "y"
        elif t.endswith("s") and len(t) > 3 and not t.endswith("ss"):
            t = t[:-1]
        if t and t not in _NOISE and not re.fullmatch(r"\d+", t):
            out.append(t)
    return out


def _slotmap(tokens):
    m = {}
    for t in tokens:
        if t in _FLAT:
            s, v = _FLAT[t]
            m.setdefault(s, set()).add(v)
    return m


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        itok = _toks(ing)
        utok = _toks(usda)
        if not itok or not utok:
            return 0.0
        iset, uset = set(itok), set(utok)
        islots, uslots = _slotmap(itok), _slotmap(utok)

        # Head food words: ingredient content words not in slot vocab
        icontent = [t for t in itok if t not in _FLAT]
        ucontent = set(t for t in utok if t not in _FLAT)
        if icontent:
            hit = 0.0
            for i, t in enumerate(icontent):
                w = 1.5 if i == len(icontent) - 1 else 1.0  # head noun last
                if t in ucontent or any(len(t) > 4 and (t[:5] == u[:5]) for u in ucontent):
                    hit += w
            tot = sum(1.5 if i == len(icontent) - 1 else 1.0 for i in range(len(icontent)))
            cover = hit / tot
        else:
            cover = 0.5

        score = 6.0 * cover

        # Qualifier slots: reward agreement, penalize contradiction / omission
        for s, vals in islots.items():
            uv = uslots.get(s)
            if uv is None:
                score -= 0.5
            elif vals & uv:
                score += 1.0
            else:
                score -= 2.0
        # USDA specifies qualifiers the ingredient lacks
        for s, vals in uslots.items():
            if s not in islots:
                if s in ("flavor", "fat", "sweet", "form"):
                    score -= 1.2
                elif s == "heat" and "cooked" in vals:
                    score -= 0.8
                else:
                    score -= 0.4

        # Leftover unexplained USDA descriptor words (percentages, brands, extras)
        extra = [t for t in utok if t not in iset and t not in _FLAT]
        pct = sum(1 for t in extra if "%" in t)
        score -= 0.25 * min(len(extra), 6) + 0.5 * min(pct, 2)

        # Exact-ish string identity bonus
        if " ".join(itok) == " ".join(utok):
            score += 2.0
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
