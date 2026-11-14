import re
import math

# Doneness ladder: position on a 0..10 "how transformed by heat" axis, plus fat gain.
_LADDER = {
    "raw": (0.0, 0.0), "uncooked": (0.0, 0.0), "fresh": (0.0, 0.0),
    "steamed": (3.0, 0.0), "boiled": (3.5, 0.0), "poached": (3.0, 0.0), "blanched": (2.0, 0.0),
    "simmered": (3.5, 0.0), "stewed": (4.0, 0.0), "braised": (4.5, 0.0), "microwaved": (3.0, 0.0),
    "cooked": (4.0, 0.3), "heated": (3.0, 0.0),
    "baked": (6.0, 0.2), "roasted": (7.0, 0.3), "toasted": (7.5, 0.0), "grilled": (7.0, 0.1),
    "broiled": (7.0, 0.1), "smoked": (5.0, 0.0),
    "sauteed": (6.5, 1.5), "fried": (8.0, 3.0), "pan-fried": (8.0, 2.5), "deep-fried": (9.0, 4.0),
    "battered": (8.5, 3.5), "breaded": (7.5, 2.5),
}

_PRESERVE = {"canned", "frozen", "dried", "dehydrated", "pickled", "cured", "candied", "sweetened",
             "unsweetened", "salted", "unsalted", "powdered", "juice", "syrup", "concentrate"}


def _prep(s):
    s = str(s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*[\d./]+\s*[a-z]{0,2}\b", " ", s)
    return s.replace("deep fried", "deep-fried").replace("pan fried", "pan-fried")


def _events(text):
    out = []
    for w in re.findall(r"[a-z\-]+", text):
        if w in _LADDER:
            out.append(w)
    return out


def _grams(w, n=3):
    w = " " + w + " "
    return set(w[i:i + n] for i in range(max(1, len(w) - n + 1)))


def _dice(a, b):
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


def judging_function(ingredient, usda_match):
    try:
        ing = _prep(ingredient)
        usd = _prep(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0

        ei, eu = _events(ing), _events(usd)
        # heat/fat position; unstated => neutral anchored at raw-or-generic
        def pos(ev):
            if not ev:
                return None
            return (max(_LADDER[e][0] for e in ev), max(_LADDER[e][1] for e in ev))

        pi, pu = pos(ei), pos(eu)
        if pi is None and pu is None:
            gap = 0.0
        elif pi is None:
            gap = max(0.0, pu[0] - 1.5) * 0.7 + pu[1] * 0.8
            if all(e == "cooked" for e in eu):
                gap = 1.0
        elif pu is None:
            gap = 0.5 + max(0.0, pi[0] - 1.5) * 0.15
            if all(e in ("raw", "fresh", "uncooked") for e in ei):
                gap = 0.0
        else:
            gap = abs(pi[0] - pu[0]) * 0.8 + abs(pi[1] - pu[1]) * 0.9
        # logistic squash of the mismatch into a compatibility probability
        method_ok = 1.0 / (1.0 + math.exp(gap - 3.0))

        # preservation words
        wi = set(re.findall(r"[a-z]+", ing))
        wu = set(re.findall(r"[a-z]+", usd))
        pdiff = len((wi ^ wu) & _PRESERVE)

        # food identity via character trigram Dice on head phrase vs ingredient body
        head = usd.split(",")[0].strip()
        ing_body = re.split(r",", ing)[0].strip()
        sim_head = _dice(_grams(head), _grams(ing_body))
        rest_words = [w for w in re.findall(r"[a-z]{3,}", ing_body)]
        hit = sum(1 for w in rest_words if w[:5] in usd) / float(len(rest_words)) if rest_words else 0.0
        identity = 0.5 * sim_head + 0.5 * hit

        score = 100.0 * (0.6 * identity + 0.4 * method_ok)
        score *= 0.8 ** pdiff
        if identity < 0.15:
            score *= 0.4
        return float(score)
    except Exception:
        return 0.0
