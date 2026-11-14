import re
from collections import Counter

def _clean(s):
    s = re.sub(r"\([^)]*\)", " ", str(s or "").lower())
    s = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", s)
    return s

def _grams(s, n):
    s = re.sub(r"[^a-z]+", "_", s).strip("_")
    s = "_" + s + "_"
    return Counter(s[i:i + n] for i in range(max(0, len(s) - n + 1)))

def _containment(a, b):
    # fraction of a's gram mass found in b
    tot = sum(a.values())
    if not tot:
        return 0.0
    return sum(min(c, b.get(g, 0)) for g, c in a.items()) / float(tot)

_STRIP = re.compile(r"\b(fresh|thawed|chopped|diced|minced|sliced|shredded|grated|cubed|crushed|peeled|halved|torn|crumbled|shelled|rinsed|warmed|melted|softened|ripe|large|small|medium|finely|optional|boneless|skinless|cold|hot|taste|tube|jar|store|bought|homemade|drained|packed|equal|parts|plain|regular|type|separable|trimmed|choice|select|grade|nfs|raw|cooked|only|lean|fat|whole|and|of|the|with|in|for|from|or|a)\b")

_SYN = [("clementine", "tangerine"), ("mandarin", "tangerine"), ("filbert", "hazelnut"), ("fava", "broadbean"), ("maize", "corn"), ("crawfish", "crayfish"), ("prawn", "shrimp"), ("garbanzo", "chickpea"), ("yoghurt", "yogurt"), ("pinyon", "pine nut"), ("linseed", "flaxseed"), ("bison", "buffalo"), ("dehydrated", "dried"), ("granada", "pomegranate")]

# rule table: (name, test(ing, usda, ingmain, usdafirst), delta)
_RULES = [
    ("usda_form_new", lambda i, u, im, uf: bool(re.search(r"\b(oil|juice|syrup|sauce|soup|pudding|cookie|cake|candy|jerky|flour|snack|taco|sandwich|entree|spices|stew|nectar)\b", uf)) and not re.search(r"\b(oil|juice|syrup|sauce|soup|pudding|cookie|cake|candy|jerky|flour|snack|taco|sandwich|entree|spices|stew|nectar)\b", i), -3.0),
    ("usda_dried_only", lambda i, u, im, uf: bool(re.search(r"dried|dehydrated|powder", u)) != bool(re.search(r"dried|dehydrated|powder", i)), -1.8),
    ("usda_cooked_only", lambda i, u, im, uf: bool(re.search(r"cooked|boiled|baked|braised|fried|simmered|broiled", u)) and not re.search(r"cooked|boiled|baked|braised|fried|simmered|broiled|roasted|steamed|toasted", i), -1.8),
    ("ing_cooked_only", lambda i, u, im, uf: bool(re.search(r"cooked|boiled|baked|braised|fried|simmered|broiled|toasted|roasted", i)) and not re.search(r"cooked|boiled|baked|braised|fried|simmered|broiled|roasted|steamed|dry heat|moist heat|toasted", u), -1.5),
    ("diet_mod", lambda i, u, im, uf: bool(re.search(r"low ?fat|non ?fat|reduced|fat free|low sodium|decaf|lactose|deli|luncheon|imported|beaked|diet", u)) and not re.search(r"low|reduced|free|nonfat|light|diet|lean", i), -1.5),
    ("brand", lambda i, u, im, uf: bool(re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u)), -3.0),
    ("ground_whole", lambda i, u, im, uf: bool(re.search(r"\bground|powder", u)) != bool(re.search(r"\bground|powder", i)), -1.0),
    ("frozen_name", lambda i, u, im, uf: bool(re.search(r"^frozen", uf)) and "frozen" not in i, -2.5),
]

def judging_function(ingredient, usda_match):
    try:
        i = _clean(ingredient)
        u = _clean(usda_match)
        for a, b in _SYN:
            i = i.replace(a, b)
            u = u.replace(a, b)
        im = i.split(",")[0]
        uf = u.split(",")[0]
        a = _STRIP.sub(" ", im)
        b_all = _STRIP.sub(" ", u)
        b_first = _STRIP.sub(" ", uf)
        if not re.search(r"[a-z]", a):
            return 0.0
        # char-gram containment at two granularities
        s3 = _containment(_grams(a, 3), _grams(b_all, 3))
        s4 = _containment(_grams(a, 4), _grams(b_all, 4))
        # reverse containment against the first USDA segment: is the USDA name explained?
        r3 = _containment(_grams(b_first, 3), _grams(a + " " + i, 3))
        # head word exact presence (word boundary), singular-tolerant
        words = a.split()
        head = words[-1] if words else ""
        hs = head[:-1] if len(head) > 3 and head.endswith("s") else head
        head_hit = 1.0 if re.search(r"\b" + re.escape(hs), b_all) else 0.0
        mods = words[:-1]
        mod_hit = sum(1 for m in mods if re.search(r"\b" + re.escape(m.rstrip("s") if len(m) > 3 else m), b_all))
        mod_miss = len(mods) - mod_hit
        score = 3.0 * s3 + 3.0 * s4 + 2.5 * r3 + 2.0 * head_hit - 1.4 * mod_miss
        for _, test, delta in _RULES:
            try:
                if test(i, u, im, uf):
                    score += delta
            except Exception:
                pass
        return float(score)
    except Exception:
        return 0.0
