import re
import heapq

# Preparation-State Equivalence, variant 7: kitchen-operation graph search.
# Preparation states are nodes; directed edges are operations a home cook can
# perform, weighted by how much effort / outcome-change they introduce.
# We find the cheapest path that turns the USDA product state into the state
# the recipe asks for (Dijkstra). Irreversible directions (cooked -> raw,
# fried -> fresh, dried -> fresh) have no edge, so they fall back to a large
# "impossible" cost. Score decays with path cost.

_EDGES = {
    "raw": {"cut": 0.0, "frozen": 0.6, "boiled": 1.4, "roasted": 1.8, "fried": 2.2,
            "pureed": 1.2, "dried": 3.0},
    "cut": {"raw": 0.1, "boiled": 1.4, "roasted": 1.8, "fried": 2.2, "pureed": 1.0},
    "frozen": {"thawed": 0.15},
    "thawed": {"raw": 0.35, "cut": 0.35, "boiled": 1.5, "roasted": 1.9, "fried": 2.3},
    "boiled": {"pureed": 0.6, "fried": 1.6, "roasted": 1.6, "canned": 1.4},
    "canned": {"boiled": 0.8, "pureed": 0.7},
    "roasted": {"cut": 0.3},
    "fried": {},
    "pureed": {},
    "dried": {"boiled": 2.0},
    "cured": {},
}
_IMPOSSIBLE = 6.0

_WORD_STATE = {
    "raw": "raw", "fresh": "raw", "uncooked": "raw",
    "chopped": "cut", "diced": "cut", "minced": "cut", "sliced": "cut",
    "shredded": "cut", "grated": "cut", "cubed": "cut", "segmented": "cut",
    "frozen": "frozen", "thawed": "thawed", "defrosted": "thawed",
    "cooked": "boiled", "boiled": "boiled", "steamed": "boiled", "poached": "boiled",
    "stewed": "boiled", "braised": "boiled", "simmered": "boiled", "moist": "boiled",
    "roasted": "roasted", "baked": "roasted", "grilled": "roasted", "broiled": "roasted",
    "toasted": "roasted", "dry": "roasted",
    "fried": "fried", "sauteed": "fried", "breaded": "fried", "battered": "fried",
    "canned": "canned", "creamed": "pureed", "pureed": "pureed", "mashed": "pureed",
    "dried": "dried", "dehydrated": "dried", "smoked": "cured", "cured": "cured",
    "pickled": "cured",
}
_RANK = ["fried", "cured", "dried", "canned", "pureed", "roasted", "boiled",
         "frozen", "thawed", "cut", "raw"]


def _state(words, default):
    found = {_WORD_STATE[w] for w in words if w in _WORD_STATE}
    if "dry" in words and "heat" not in words:
        found.discard("roasted")
        if not found and default == "raw":
            found.add("dried")
    for s in _RANK:
        if s in found:
            return s, True
    return default, False


def _path_cost(src, dst):
    if src == dst:
        return 0.0
    dist = {src: 0.0}
    pq = [(0.0, src)]
    while pq:
        d, node = heapq.heappop(pq)
        if node == dst:
            return d
        if d > dist.get(node, 1e9):
            continue
        for nxt, w in _EDGES.get(node, {}).items():
            nd = d + w
            if nd < dist.get(nxt, 1e9):
                dist[nxt] = nd
                heapq.heappush(pq, (nd, nxt))
    return _IMPOSSIBLE


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing).replace("-", " ")
        iw = re.findall(r"[a-z]+", ing)
        uw = re.findall(r"[a-z]+", usda.replace("-", " "))
        target, i_explicit = _state(iw, "raw")
        source, u_explicit = _state(uw, "raw")
        cost = _path_cost(source, target)
        # equivalent-ish terminal states (e.g. cut vs raw both ways) are cheap
        score = 10.0 / (1.0 + 0.9 * cost * cost)
        if not i_explicit and not u_explicit:
            score -= 0.6
        elif i_explicit and u_explicit and cost == 0.0:
            score = 10.0
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
