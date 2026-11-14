import re
import math

_NOISE = set("""fresh frozen canned dried dry cooked raw chopped diced sliced minced ground crushed grated shredded
peeled cubed crumbled drained thawed large small medium whole fine finely boneless skinless bagged mixed
packed ripe optional plain regular for the of and with from in a an to or into cut pieces piece segmented
softened melted toasted commercial nfs all varieties variety prepared made""".split())

# known compounds: a lexicon of (words) -> canonical identity; detecting these makes them atomic units
_LEX = [
    "sweet potato", "coconut milk", "peanut butter", "green tea", "sea bass", "half and half", "ice cream",
    "sour cream", "cream cheese", "cottage cheese", "hot dog", "soy sauce", "fish sauce", "olive oil",
    "sesame oil", "corn syrup", "maple syrup", "black bean", "green bean", "kidney bean", "lima bean",
    "bell pepper", "black pepper", "chili powder", "garlic powder", "onion powder", "baking soda",
    "baking powder", "brown sugar", "powdered sugar", "corn starch", "corn meal", "apple juice",
    "orange juice", "lemon juice", "lime juice", "egg white", "egg yolk", "pork sausage", "beef jerky",
    "blood sausage", "fish tofu", "ugli fruit", "nut butter", "almond milk", "soy milk", "butter milk",
    "ground beef", "ground turkey", "ground pork", "turkey bacon", "water chestnut", "butternut squash",
    "root beer", "bean sprout", "peanut oil", "ginger ale", "apple cider", "wine vinegar", "rice vinegar",
]


def _norm(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("ches", "shes", "oes", "sses", "xes")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _words(s):
    return [_norm(w) for w in re.findall(r"[a-z]+", s.lower())]


_LEXN = [tuple(_words(c)) for c in _LEX]


def _atomize(ws):
    """merge known compounds into single atoms; returns list of atoms (tuples joined by '_')."""
    out = []
    i = 0
    while i < len(ws):
        hit = None
        for c in _LEXN:
            L = len(c)
            if tuple(ws[i:i + L]) == c and (hit is None or L > len(hit)):
                hit = c
        if hit:
            out.append("_".join(hit))
            i += len(hit)
        else:
            out.append(ws[i])
            i += 1
    return out


def _longest_run(a, b):
    best = 0
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            if k > best:
                best = k
    return best


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|oz|ml|lb)?\b", " ", ing)
        ing_main = ing.split(",")[0].replace("-", " ")
        usda = re.sub(r"\([^)]*\)", " ", usda).replace("-", " ")

        iw = [w for w in _words(ing_main) if w not in _NOISE]
        if not iw:
            return 0.0
        segs = [[w for w in _words(s)] for s in usda.split(",")]
        segs = [s for s in segs if s]
        if not segs:
            return 0.0

        # build natural-order phrase candidates from USDA: "cheese, cottage, lowfat" -> "cottage cheese", "lowfat cottage cheese"
        cands = []
        head = segs[0]
        cands.append(head)
        for k in range(1, len(segs)):
            cands.append(segs[k] + head)
            cands.append(head + segs[k])
        cands.append([w for s in segs for w in s])
        cands = [[w for w in c if w not in _NOISE] for c in cands]
        cands = [c for c in cands if c]
        if not cands:
            return 0.0

        ia = _atomize(iw)
        # atoms present in the ingredient that are lexicon compounds
        ing_compounds = [a for a in ia if "_" in a]
        best = -9.0
        for c in cands:
            ca = _atomize(c)
            cset = set(ca)
            # run-based alignment on atoms
            run = _longest_run(ia, ca)
            frac_ing = run / len(ia)
            # fraction of ingredient atoms matched anywhere (bag)
            bag = sum(1 for a in ia if a in cset) / len(ia)
            # leftover atoms in candidate not in ingredient (foreign modifiers)
            foreign = sum(1 for a in ca if a not in ia)
            fpen = foreign / max(1, len(ca))
            # compound broken: ingredient compound's parts present while atom is not
            broken = 0
            for a in ing_compounds:
                if a not in cset:
                    parts = a.split("_")
                    if any(p in cset for p in parts):
                        broken += 1
            # candidate compound not in ingredient but whose parts are: new food formed
            formed = 0
            for a in ca:
                if "_" in a and a not in ia:
                    parts = a.split("_")
                    if any(p in ia for p in parts):
                        formed += 1
            s = 5.0 * frac_ing + 3.0 * bag - 2.5 * fpen - 2.0 * broken - 2.5 * formed
            if s > best:
                best = s
        # head-primary bonus: ingredient last atom equals the primary food of USDA
        prim = _atomize([w for w in head if w not in _NOISE])
        if prim and ia and (ia[-1] in prim or any(a in ia for a in prim)):
            best += 1.5
        return max(-5.0, min(10.0, best))
    except Exception:
        return 0.0
