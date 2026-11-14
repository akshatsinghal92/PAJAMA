import re
import math

# Preservation and Form Match, variant 7: field-salience weighted evidence
# with a tanh squashing function.
# A form word in the USDA PRIMARY field ("Fruit juice", "Frozen yogurt",
# "Soup, ...") defines a different product type, so it is highly salient;
# the same word in a trailing descriptor field is a mere modifier.
# Likewise in the recipe text, form words before the comma describe the
# product to buy, while post-comma / parenthetical words are cook actions
# (thawed, drained) that make some forms recoverable.
# Evidence: +salience for forms present on both sides, -salience for forms
# on only one side, with synonym groups collapsed; squashed into 0..10.

_GROUPS = {
    "frozen": {"frozen", "iqf", "thawed", "defrosted"},
    "canned": {"canned", "tinned", "jarred", "bottled", "can", "jar"},
    "dried": {"dried", "dehydrated", "sundried", "dry", "raisin", "raisins"},
    "powder": {"powder", "powdered", "granulated", "instant", "ground"},
    "paste": {"paste", "puree", "pureed", "concentrate", "tube"},
    "juice": {"juice", "juiced", "nectar"},
    "broth": {"broth", "stock", "bouillon", "consomme"},
    "soup": {"soup", "chowder", "bisque"},
    "condensed": {"condensed", "concentrated", "evaporated"},
    "syrup": {"syrup"},
    "fresh": {"fresh", "raw"},
}
_SALIENCE = {"frozen": 0.8, "canned": 1.3, "dried": 2.0, "powder": 2.0, "paste": 1.8,
             "juice": 2.4, "broth": 1.8, "soup": 2.2, "condensed": 1.6, "syrup": 1.2,
             "fresh": 0.6}
_WORD2G = {w: g for g, ws in _GROUPS.items() for w in ws}
_MEAT = {"beef", "pork", "turkey", "chicken", "lamb", "meat", "veal"}


def _scan(fields, weights):
    ev = {}
    all_words = [w for f in fields for w in f]
    for f, wt in zip(fields, weights):
        for i, w in enumerate(f):
            g = _WORD2G.get(w)
            if not g:
                continue
            if w == "dry" and i + 1 < len(f) and f[i + 1] == "heat":
                continue
            if w == "ground" and set(all_words) & _MEAT:
                continue
            ev[g] = max(ev.get(g, 0.0), wt)
    return ev


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower().replace("-", " ")
        usda = str(usda_match or "").lower().replace("-", " ")
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        paren = " ".join(re.findall(r"\(([^)]*)\)", ing))
        ing_np = re.sub(r"\([^)]*\)", " ", ing)
        parts = ing_np.split(",")
        i_fields = [re.findall(r"[a-z]+", parts[0]),
                    re.findall(r"[a-z]+", " ".join(parts[1:]) + " " + paren)]
        u_raw = [re.findall(r"[a-z]+", f) for f in usda.split(",")]
        u_fields = [f for f in u_raw if f]
        if not u_fields or not i_fields[0]:
            return 0.0
        ei = _scan(i_fields, [1.0, 0.5])
        eu = _scan(u_fields, [1.0] + [0.55] * (len(u_fields) - 1))

        # recoverable: "frozen ..., thawed" or "canned ..., drained" both exist
        evidence = 0.0
        for g in set(ei) | set(eu):
            a, b = ei.get(g, 0.0), eu.get(g, 0.0)
            s = _SALIENCE[g]
            if a and b:
                evidence += s * min(a, b)
            else:
                # one-sided form; frozen and fresh mismatch are lightly penalised
                evidence -= s * max(a, b) * 1.3
        # implicit fresh-vs-fresh (no info) sits a bit above neutral
        if not ei and not eu:
            evidence = 0.6
        score = 5.0 + 5.0 * math.tanh(0.7 * evidence)
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
