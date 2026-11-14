import re
import math


def _grams(s, n=3):
    s = " " + re.sub(r"[^a-z]+", " ", s.lower()).strip() + " "
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def _dice(a, b):
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").strip()
        usda = str(usda_match or "").strip()
        if not ing or not usda:
            return 0.0
        ing = re.sub(r"^\d+(\.\d+)?\s*[a-zA-Z]{0,3}\s+", "", ing)
        ing_main = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        ing_post = ",".join(ing.split(",")[1:]).lower()

        parts = [p.strip() for p in usda.split(",") if p.strip()]
        head = parts[0] if parts else usda
        tail = parts[1:]

        # 1. character-trigram similarity of ingredient vs USDA head (primary food)
        s_head = _dice(_grams(ing_main), _grams(head))
        s_full = _dice(_grams(ing_main), _grams(usda))
        # last-word (head noun) agreement
        iw = re.findall(r"[a-z]+", ing_main.lower())
        hw = re.findall(r"[a-z]+", head.lower())
        noun = 0.0
        if iw and hw:
            a, b = iw[-1].rstrip("s"), hw[-1].rstrip("s")
            first = hw[0].rstrip("s")
            if a == b or a in [w.rstrip("s") for w in hw] or first in [w.rstrip("s") for w in iw]:
                noun = 1.0

        cw = [w.rstrip("s") for w in iw if len(w) > 2 and w not in ("fresh", "dried", "raw", "the", "and")]
        uw = set(w.rstrip("s") for w in re.findall(r"[a-z]+", usda.lower()))
        cov = (sum(1 for w in cw if w in uw) / len(cw)) if cw else 0.0
        base = 0.15 * s_head + 0.15 * s_full + 0.15 * noun + 0.55 * cov
        if cov < 0.5:
            base *= 0.4

        # 2. commercial marker analysis on the USDA string
        markers = 0.0
        for t in re.findall(r"[A-Za-z&'\.]+", usda):
            letters = re.sub(r"[^A-Za-z]", "", t)
            if len(letters) >= 3 and letters.isupper():
                markers += 1.0
        markers += len(re.findall(r"[®™©]", usda)) * 1.0
        # trailing segment capitalised like a proper noun (brand names ending a USDA description)
        if len(parts) > 2:
            last = parts[-1]
            if re.match(r"^[A-Z][A-Za-z&']+(\s[A-Z][A-Za-z&']+)*$", last) and last.lower() not in ("raw", "cooked"):
                markers += 0.7
        if re.search(r"\b(restaurant|fast foods?|babyfood|school lunch|commercial|brand)\b", usda, re.I):
            markers += 0.8

        ing_markers = 0.0
        for t in re.findall(r"[A-Za-z&']+", ing):
            if len(t) >= 3 and t.isupper():
                ing_markers += 1
        ing_markers += len(re.findall(r"[®™©]", ing))
        ing_markers += len(re.findall(r"\(([^)]*[A-Z][^)]*)\)", ing)) * 0.5

        # 3. flavour / base divergence: tail descriptors that appear nowhere in ingredient
        ing_set = set(re.findall(r"[a-z]+", ing.lower()))
        novel = 0
        for seg in tail:
            ws = re.findall(r"[a-z]+", seg.lower())
            if ws and not (set(w.rstrip("s") for w in ws) & set(w.rstrip("s") for w in ing_set)):
                novel += 1
        novel_frac = novel / max(1, len(tail)) if tail else 0.0
        # modifiers in ingredient not mapped to USDA (e.g. vegan, coconut)
        iw_mod = [w for w in iw[:-1] if len(w) > 3]
        uset = set(w.rstrip("s") for w in re.findall(r"[a-z]+", usda.lower()))
        unmapped = sum(1 for w in iw_mod if w.rstrip("s") not in uset)
        unmapped_frac = unmapped / max(1, len(iw_mod)) if iw_mod else 0.0

        net_markers = max(0.0, markers - 0.5 * ing_markers)
        penalty = math.exp(-0.9 * net_markers) * (1.0 - 0.35 * novel_frac) * (1.0 - 0.45 * unmapped_frac)
        if "vegan" in ing_set or "imitation" in ing_set:
            penalty *= 0.5

        return round(100.0 * base * penalty, 3)
    except Exception:
        return 0.0
