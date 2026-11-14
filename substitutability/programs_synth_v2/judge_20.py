import re

# Preservation and Form Match, variant 4: conversion-action accounting.
# For a USDA form F_u and a recipe form F_i, we list the concrete kitchen
# actions needed to turn F_u into F_i (thaw, drain, rinse, rehydrate,
# dilute, reduce, blend, strain ...). Each action has an effort cost and a
# "fidelity loss" (how much the result still differs). Conversions that no
# action can achieve (dried herb -> fresh herb, juice -> whole fruit) are
# marked impossible. Score = 10 - effort - 2*fidelity_loss.

_ACTIONS = {
    "thaw": (0.3, 0.1), "drain": (0.3, 0.3), "rinse": (0.2, 0.2),
    "rehydrate": (1.5, 1.2), "dilute": (0.6, 0.4), "reduce": (1.2, 0.8),
    "blend": (0.8, 0.6), "strain": (0.6, 0.6), "freeze": (0.6, 0.3),
    "dissolve": (0.6, 0.5), "cook_down": (1.5, 1.0),
}
_CONVERT = {
    ("frozen", "fresh"): ["thaw"],
    ("fresh", "frozen"): ["freeze"],
    ("canned", "fresh"): ["drain", "rinse"],
    ("canned", "frozen"): ["drain"],
    ("frozen", "canned"): ["thaw", "cook_down"],
    ("fresh", "canned"): ["cook_down"],
    ("dried", "fresh"): None,
    ("dried", "frozen"): None,
    ("dried", "canned"): ["rehydrate", "cook_down"],
    ("fresh", "dried"): None,
    ("powder", "fresh"): None,
    ("powder", "dried"): [],
    ("dried", "powder"): ["blend"],
    ("fresh", "paste"): ["blend", "reduce"],
    ("canned", "paste"): ["blend", "reduce"],
    ("paste", "fresh"): None,
    ("paste", "liquid"): ["dilute"],
    ("liquid", "paste"): ["reduce", "reduce"],
    ("concentrate", "liquid"): ["dilute"],
    ("liquid", "concentrate"): ["reduce"],
    ("powder", "liquid"): ["dissolve"],
    ("liquid", "powder"): None,
    ("liquid", "fresh"): None,
    ("fresh", "liquid"): ["blend", "strain"],
    ("frozen", "liquid"): ["thaw", "blend", "strain"],
    ("ready", "concentrate"): ["reduce"],
    ("concentrate", "ready"): ["dilute"],
    ("ready", "liquid"): ["strain"],
    ("liquid", "ready"): None,
    ("powder", "paste"): ["dissolve"],
    ("paste", "powder"): None,
}
_FORM_WORDS = [
    ("concentrate", r"\bconcentrat\w*|\bcondensed\b|\bbouillon\b|\bbase\b"),
    ("ready", r"\bready[- ]to[- ]serve\b|\bsoup\b|\bchowder\b|\bprepared\b"),
    ("powder", r"\bpowder\w*|\binstant\b|\bground\b(?! (beef|pork|turkey|chicken|lamb|meat))|\bspices\b"),
    ("paste", r"\bpaste\b|\bpuree\b|\btube\b"),
    ("liquid", r"\bjuice\b|\bbroth\b|\bstock\b|\bnectar\b|\bmilk\b"),
    ("dried", r"\bdried\b|\bdehydrated\b|\bdry\b(?! heat)|\bflakes\b|\braisins?\b"),
    ("canned", r"\bcanned\b|\btinned\b|\bjarred\b|\bbottled\b|\bsolids and liquids\b"),
    ("frozen", r"\bfrozen\b"),
    ("fresh", r"\bfresh\b|\braw\b"),
]


def _form(text):
    for name, rx in _FORM_WORDS:
        if re.search(rx, text):
            return name, True
    return "fresh", False


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        head = re.sub(r"\([^)]*\)", " ", ing).split(",")
        main = head[0]
        tail = " ".join(head[1:]) + " " + " ".join(re.findall(r"\(([^)]*)\)", ing))
        fi, ei = _form(main)
        fu, eu = _form(usda)
        # "frozen X, thawed": recipe intends to thaw - frozen product matches
        if fi == "frozen" and re.search(r"\bthawed\b|\bdefrosted\b", tail):
            fi = "frozen"
        if fi == fu:
            score = 10.0 if (ei or eu) else 8.8
            return round(score, 2)
        plan = _CONVERT.get((fu, fi), ["blend", "reduce"])
        if plan is None:
            return 1.0 if fu in ("dried", "powder", "liquid") else 1.5
        effort = sum(_ACTIONS[a][0] for a in plan)
        loss = sum(_ACTIONS[a][1] for a in plan)
        score = 10.0 - effort - 2.0 * loss
        return round(max(0.5, min(10.0, score)), 2)
    except Exception:
        return 0.0
