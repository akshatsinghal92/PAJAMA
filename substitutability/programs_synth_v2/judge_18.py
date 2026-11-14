import re

# Preservation and Form Match, variant 2: regex-detected delivery formats.
# USDA descriptions encode delivery form with multi-word phrases
# ("ready-to-serve", "condensed", "dry mix", "packed in water",
# "solids and liquids", "from concentrate", "heavy syrup").
# We detect a FORMAT label plus a PACKING-MEDIUM label on each side via
# regexes and score agreement on both, with explicit recoverability rules.

_FORMAT_RX = [
    ("drymix", r"\bdry mix\b|\bmix,? dry\b|\bdry form\b|\binstant\b|\bdehydrated\b"),
    ("condensed", r"\bcondensed\b|\bconcentrat\w*\b|\bbouillon\b|\bbase\b"),
    ("rts", r"\bready[- ]to[- ](serve|drink|eat)\b|\bprepared with\b|\breconstituted\b"),
    ("powder", r"\bpowder(ed)?\b|\bground\b(?! (beef|turkey|pork|chicken|meat|lamb))"),
    ("paste", r"\bpaste\b|\bpuree\b|\btube\b"),
    ("dried", r"\bdried\b|\bdry\b(?! heat)|\bsun[- ]?dried\b|\bflakes\b"),
    ("canned", r"\bcanned\b|\btinned\b|\bjar(red)?\b|\bbottled\b"),
    ("frozen", r"\bfrozen\b|\bthawed\b|\bdefrosted\b"),
    ("fresh", r"\bfresh\b|\braw\b"),
]
_MEDIUM_RX = [
    ("syrup", r"\bsyrup\b"),
    ("juice", r"\bjuice pack\b|\bin juice\b|\bjuice\b"),
    ("oil", r"\bin oil\b|\bpacked in oil\b|\boil[- ]packed\b"),
    ("water", r"\bin water\b|\bwater pack\w*\b|\bbrine\b"),
    ("liquid", r"\bsolids and liquids\b|\bwith liquid\b"),
    ("drained", r"\bdrained\b|\bsolids only\b|\bdrained solids\b"),
]

# compatibility of formats (symmetric unless noted)
_FMT_OK = {
    ("fresh", "frozen"): 7.5, ("frozen", "fresh"): 8.0, ("fresh", "canned"): 4.0,
    ("canned", "fresh"): 3.5, ("frozen", "canned"): 4.0, ("canned", "frozen"): 4.0,
    ("rts", "condensed"): 4.5, ("condensed", "rts"): 4.0, ("rts", "drymix"): 3.0,
    ("drymix", "rts"): 3.0, ("condensed", "drymix"): 4.0, ("drymix", "condensed"): 4.0,
    ("fresh", "dried"): 2.0, ("dried", "fresh"): 1.5, ("powder", "dried"): 6.0,
    ("dried", "powder"): 6.0, ("paste", "fresh"): 3.0, ("fresh", "paste"): 2.5,
    ("paste", "powder"): 3.0, ("powder", "paste"): 3.0, ("fresh", "powder"): 1.5,
    ("powder", "fresh"): 1.5, ("canned", "paste"): 4.0, ("paste", "canned"): 4.5,
    ("canned", "rts"): 7.0, ("rts", "canned"): 7.0, ("frozen", "dried"): 1.5,
}


def _labels(text, table):
    found = []
    for lab, rx in table:
        if re.search(rx, text):
            found.append(lab)
    return found


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        fi = _labels(ing, _FORMAT_RX)
        fu = _labels(usda, _FORMAT_RX)
        mi = _labels(ing, _MEDIUM_RX)
        mu = _labels(usda, _MEDIUM_RX)

        # primary format: first (most specific) label, fresh default
        pi = fi[0] if fi else "fresh"
        pu = fu[0] if fu else "fresh"
        if pi == pu:
            fmt = 10.0
        else:
            fmt = _FMT_OK.get((pi, pu), 2.5)
        # frozen ingredient that is thawed vs frozen USDA is exact
        if "frozen" in fi and "frozen" in fu:
            fmt = max(fmt, 9.5)

        # packing medium: only matters if both are packaged
        med = 0.0
        if mi and mu:
            med = 1.0 if set(mi) & set(mu) else -2.0
        elif mu and pi in ("fresh", "frozen"):
            # fresh ingredient vs syrup/oil packed product changes the dish
            med = -1.5 if set(mu) & {"syrup", "oil"} else -0.5

        score = fmt + med
        if not fi and not fu:
            score -= 1.0          # unknown; mild uncertainty
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
