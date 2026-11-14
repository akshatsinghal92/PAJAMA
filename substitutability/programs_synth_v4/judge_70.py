import re

# Part lexicon: part label -> (family, keyword patterns)
_PARTS = {
    # plant parts
    "leaf": ("plant", ["greens", "leaves", "leaf", "leafy", "tops"]),
    "root": ("plant", ["root", "roots", "tuber", "tubers", "bulb"]),
    "stem": ("plant", ["stem", "stems", "stalk", "stalks", "shoots", "shoot"]),
    "seed": ("plant", ["seed", "seeds", "kernel", "kernels", "mature seeds"]),
    "flower": ("plant", ["flower", "flowers", "blossom", "blossoms", "florets"]),
    "sprout": ("plant", ["sprouts", "sprouted"]),
    "pod": ("plant", ["pod", "pods", "immature"]),
    "peel": ("fruitpart", ["peel", "zest", "rind", "skin", "skins"]),
    "juice": ("fruitpart", ["juice"]),
    "heart": ("plant", ["hearts of palm", "artichoke hearts"]),
    # poultry
    "breast": ("poultry", ["breast", "breasts"]),
    "thigh": ("poultry", ["thigh", "thighs"]),
    "wing": ("poultry", ["wing", "wings"]),
    "drumstick": ("poultry", ["drumstick", "drumsticks", "leg", "legs"]),
    "neck": ("poultry", ["neck", "necks"]),
    "back": ("poultry", ["back", "backs"]),
    "giblets": ("organ", ["giblets", "gizzard", "gizzards"]),
    # organs
    "liver": ("organ", ["liver", "livers"]),
    "organheart": ("organ", ["beef heart", "chicken heart", "pork heart", "heart, raw", "hearts, raw"]),
    "kidney": ("organ", ["kidney", "kidneys"]),
    "tongue": ("organ", ["tongue"]),
    "tripe": ("organ", ["tripe"]),
    # red meat primal cuts
    "loin": ("meat", ["loin", "tenderloin", "sirloin", "strip", "porterhouse", "t-bone"]),
    "tri-tip": ("meat", ["tri-tip", "tri tip"]),
    "shoulder": ("meat", ["shoulder", "chuck", "blade", "butt"]),
    "rib": ("meat", ["rib", "ribs", "ribeye", "rib eye", "spareribs"]),
    "round": ("meat", ["round", "rump", "eye of round", "top round", "bottom round"]),
    "shank": ("meat", ["shank", "shin", "hock"]),
    "brisket": ("meat", ["brisket"]),
    "belly": ("meat", ["belly", "bacon"]),
    "flank": ("meat", ["flank", "skirt", "plate"]),
    "ham": ("meat", ["ham", "leg of"]),
    "chop": ("meat", ["chop", "chops", "cutlet", "cutlets"]),
    # egg
    "yolk": ("egg", ["yolk", "yolks"]),
    "white": ("egg", ["egg white", "egg whites", "white, raw", "whites"]),
    # fish
    "fillet": ("fish", ["fillet", "fillets", "filet", "filets"]),
    "roe": ("fish", ["roe", "caviar"]),
}

# Form/grind descriptors (whole vs ground vs processed)
_FORMS = {
    "ground": ["ground", "minced", "mince", "hamburger"],
    "whole": ["whole"],
    "processed": ["frankfurter", "sausage", "patty", "patties", "nuggets", "merguez",
                  "hot dog", "bologna", "salami", "luncheon", "loaf", "pudding", "puddings",
                  "mix"],
}

# Ingredient-side words that do NOT force a ground form in USDA (ground spices etc)
_STOP = set("""
g kg mg ml l oz lb cup cups tbsp tsp a an the of and or with without for to in
raw fresh frozen thawed cooked chopped sliced diced cubed minced optional serving
large small medium fine finely roughly about plus more taste canned dried
boiled drained baked salt added regular style type
""".split())


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b", " ", t)
    t = re.sub(r"\d+(\.\d+)?%?", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _has(text, phrase):
    return re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", text) is not None


def _parts(text):
    found = {}
    for label, (fam, kws) in _PARTS.items():
        for kw in kws:
            if _has(text, kw):
                found[label] = fam
                break
    return found


def _forms(text):
    out = set()
    for label, kws in _FORMS.items():
        if any(_has(text, k) for k in kws):
            out.add(label)
    return out


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(text):
    return {_stem(w) for w in re.findall(r"[a-z]+", text) if w not in _STOP and len(w) > 2}


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0

        # Head-food identity: USDA primary food is first comma segment
        head = usda.split(",")[0].strip()
        ing_main = ing.split(",")[0].strip()
        it = _tokens(ing_main)
        ut = _tokens(usda)
        ht = _tokens(head)
        if not it or not ut:
            return 5.0

        head_hit = len(it & ht) / max(1, len(ht))
        cover = len(it & ut) / len(it)
        identity = 0.55 * cover + 0.45 * head_hit  # 0..1

        # Anatomical part comparison
        ip = _parts(ing_main)
        up = _parts(usda)
        part_score = 0.0
        if ip and up:
            shared = set(ip) & set(up)
            if shared:
                part_score += 2.5
                extra = set(up) - set(ip)
                # USDA names an additional distinct part in same family
                if any(up[e] in {ip[s] for s in ip} for e in extra):
                    part_score -= 1.5
            else:
                same_family = set(ip.values()) & set(up.values())
                part_score -= 4.0 if same_family else 3.0
        elif ip and not up:
            # Ingredient specifies a part, USDA generic -> mild concern
            part_score -= 0.5
        elif up and not ip:
            # USDA specifies a part the ingredient didn't ask for
            fams = set(up.values())
            if fams & {"organ", "fruitpart"}:
                part_score -= 3.0
            elif fams & {"poultry", "meat", "egg"}:
                part_score -= 2.0
            else:
                part_score -= 1.0

        # Form: whole vs ground vs processed
        iform = _forms(ing)
        uform = _forms(usda)
        form_score = 0.0
        if "processed" in uform and "processed" not in iform:
            form_score -= 3.5
        if "processed" in iform and "processed" not in uform:
            form_score -= 2.5
        if "ground" in uform and "ground" not in iform:
            form_score -= 1.0
        if "ground" in iform and "ground" not in uform and ("meat" in ip.values() or "poultry" in ip.values()):
            form_score -= 1.0

        score = 4.0 + 4.0 * identity + part_score + form_score
        if identity == 0:
            score -= 2.5
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
