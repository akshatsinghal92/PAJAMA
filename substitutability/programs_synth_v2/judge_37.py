import re

# Specificity and Generality Alignment, variant 5: taxonomy-path similarity
# (Wu-Palmer style).
# A USDA description is already a path in a food hierarchy:
#   "Cheese, cottage, lowfat, 2% milkfat" = cheese > cottage > lowfat > 2%
# The recipe phrase is turned into the same kind of path by reading it
# head-first: "low fat cottage cheese" = cheese > cottage > low fat.
# Path nodes are matched in order-insensitive fashion along the path
# (a node matches if it appears anywhere at the same or deeper level),
# then Wu-Palmer similarity 2*common / (len_a + len_b) is computed and
# sharpened with an extra penalty for unmatched nodes on the ingredient side
# (the USDA entry is too generic).

_SKIP = set("""g kg ml oz lb cup tbsp tsp fresh chopped diced minced sliced shredded
grated thawed segmented peeled drained rinsed and or of with the a an to in for
from as nfs ns regular plain raw unprepared commercial made type style""".split())
_MERGE = [("low fat", "lowfat"), ("reduced fat", "reducedfat"), ("fat free", "nonfat"),
          ("extra virgin", "extravirgin"), ("light meat", "lightmeat"),
          ("dark meat", "darkmeat"), ("dry heat", "dryheat"), ("moist heat", "moistheat"),
          ("low sodium", "lowsodium"), ("reduced calorie", "reducedcalorie"),
          ("ready to eat", "readytoeat"), ("ready-to-eat", "readytoeat"),
          ("skin not eaten", "skinless"), ("peel eaten", "peel")]


def _canon(text):
    t = " " + text.lower() + " "
    for a, b in _MERGE:
        t = t.replace(a, b)
    return t


def _norm(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _usda_path(text):
    path = []
    for field in _canon(text).split(","):
        words = [_norm(w) for w in re.findall(r"[a-z0-9%]+", field) if w not in _SKIP]
        if not words:
            continue
        # within a field the head is last; push head first, then its modifiers
        path.append(words[-1])
        path.extend(reversed(words[:-1]))
    return path


def _ing_path(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower()).split(",")[0]
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", t)
    words = [_norm(w) for w in re.findall(r"[a-z]+", _canon(t)) if w not in _SKIP]
    return list(reversed(words))


def judging_function(ingredient, usda_match):
    try:
        ip = _ing_path(str(ingredient or ""))
        up = _usda_path(str(usda_match or ""))
        if not ip or not up:
            return 0.0
        # root (head) must line up within the first two USDA nodes
        if ip[0] not in up[:3]:
            return 0.5
        common = 0
        used = set()
        for depth, node in enumerate(ip):
            for j, unode in enumerate(up):
                if j in used:
                    continue
                if unode == node or (len(node) > 4 and len(unode) > 4 and node[:5] == unode[:5]):
                    used.add(j)
                    common += 1
                    break
        wup = 2.0 * common / (len(ip) + len(up))
        missing = len(ip) - common           # ingredient detail USDA lacks
        extra = len(up) - common             # USDA detail ingredient did not imply
        score = 10.0 * wup - 0.9 * missing
        # small allowance: one extra boilerplate node is rarely noticed
        if extra == 1 and missing == 0:
            score = max(score, 7.5)
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
