import re

# Concept families: each family is a qualifier "concept" with a set of trigger
# phrases and a noticeability (0..1) -- probability a diner would notice it.
_FAMILIES = {
    "sodium": (0.55, ["low sodium", "reduced sodium", "no salt added", "sodium free",
                      "lower sodium", "unsalted", "without salt", "salt free", "no salt"]),
    "salted": (0.45, ["with salt", "salted", "salt added", "added salt"]),
    "fatless": (0.6, ["fat free", "nonfat", "non fat", "fat-free", "skim", "0% fat"]),
    "lowfat": (0.45, ["low fat", "lowfat", "reduced fat", "lite", "light", "lean",
                      "less fat", "part skim", "2%", "1%"]),
    "fatadded": (0.5, ["fat added", "with butter", "with oil", "butter added",
                       "oil added", "with margarine", "fried"]),
    "sweet": (0.55, ["sweetened", "with sugar", "sugar added", "added sugar",
                     "heavy syrup", "light syrup", "in syrup", "honey"]),
    "nosugar": (0.5, ["sugar free", "unsweetened", "no sugar added", "sugar-free",
                      "diet", "artificially sweetened", "low calorie", "reduced calorie",
                      "reduced sugar"]),
    "flavored": (0.6, ["flavored", "flavoured", "seasoned", "spiced", "with spices",
                       "with herbs", "barbecue", "bbq", "teriyaki", "honey roasted",
                       "smoked", "pickled", "cured", "marinated", "breaded", "batter"]),
    "fortified": (0.2, ["enriched", "fortified", "with added vitamin", "vitamin a added",
                        "vitamin d added", "with added calcium", "calcium fortified",
                        "with added", "iron fortified"]),
    "decaf": (0.35, ["decaffeinated", "decaf", "caffeine free"]),
    "glutenfree": (0.35, ["gluten free", "gluten-free"]),
    "cheese": (0.5, ["with cheese", "cheese added"]),
    "sauce": (0.5, ["with sauce", "in sauce", "with gravy", "in gravy", "tomato sauce"]),
}

# Phrases that never count as an added qualifier.
_NEUTRAL = {"raw", "plain", "regular", "fresh", "nfs", "ns as to form", "uncooked",
            "cooked", "boiled", "drained", "canned", "frozen", "dried", "whole",
            "commercially prepared", "prepared", "all varieties", "unprepared",
            "100%", "ready-to-eat", "ready to eat", "includes", "mature seeds"}


def _clean_ingredient(txt):
    t = txt.lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b\.?", " ", t)
    t = re.sub(r"[()\[\]]", " ", t)
    t = t.replace("-", " ")
    return " " + re.sub(r"\s+", " ", t).strip() + " "


def _segments(usda):
    parts = [p.strip().lower().replace("-", " ") for p in re.split(r"[,;(]|\)", usda)]
    return [re.sub(r"\s+", " ", p) for p in parts if p.strip()]


def _phrase_in(phrase, text):
    p = phrase.replace("-", " ")
    return re.search(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", text) is not None


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _clean_ingredient(str(ingredient))
        segs = _segments(str(usda_match))
        if not segs:
            return 0.0

        # Families the ingredient itself already states.
        stated = set()
        for fam, (_, phrases) in _FAMILIES.items():
            if any(_phrase_in(ph, ing) for ph in phrases):
                stated.add(fam)

        # Walk USDA segments; collect unstated families with segment position weight.
        survival = 1.0
        hits = []
        seen = set()
        usda_full = " " + " ".join(segs) + " "
        for idx, seg in enumerate(segs):
            if seg in _NEUTRAL:
                continue
            segtxt = " " + seg + " "
            for fam, (notice, phrases) in _FAMILIES.items():
                if fam in seen:
                    continue
                matched = [ph for ph in phrases if _phrase_in(ph, segtxt)]
                if not matched:
                    continue
                # Avoid "light" matching "light syrup" being double-counted etc.
                if fam == "lowfat" and any(_phrase_in(x, segtxt) for x in ("light syrup", "light meat", "light brown")):
                    continue
                seen.add(fam)
                if fam in stated:
                    continue
                # The literal qualifier word appearing in the ingredient also counts as stated.
                if any(_phrase_in(ph, ing) for ph in matched):
                    continue
                # Descriptors appearing early in the USDA name (primary noun area)
                # are slightly less likely to be purely added qualifiers.
                pos_factor = 0.8 if idx == 0 else 1.0
                hits.append(fam)
                survival *= (1.0 - notice * pos_factor)

        # Opposing-family conflicts (ingredient says one, USDA says opposite) are worse.
        opposites = [("sodium", "salted"), ("fatless", "fatadded"), ("lowfat", "fatadded"),
                     ("sweet", "nosugar")]
        for a, b in opposites:
            if (a in stated and b in hits) or (b in stated and a in hits):
                survival *= 0.5

        # Percent-lean style compositional numbers not stated by ingredient.
        nums_usda = set(re.findall(r"\d+%", usda_full))
        nums_ing = set(re.findall(r"\d+%", ing))
        extra_nums = nums_usda - nums_ing - {"100%"}
        if extra_nums:
            survival *= 0.75 ** min(len(extra_nums), 2)

        # Core anchoring, two-sided:
        #  (a) how many of the ingredient's content words the USDA entry covers;
        #  (b) whether a multi-word USDA head phrase introduces an unmentioned noun.
        _generic = {"and", "with", "the", "nfs", "raw", "meat", "only", "broilers",
                    "fryers", "broiler", "fryer", "all", "types", "varieties", "type",
                    "includes", "from", "made", "style", "for", "not", "other"}
        _prep = {"fresh", "frozen", "thawed", "chopped", "diced", "sliced", "minced",
                 "drained", "cooked", "toasted", "segmented", "garnish", "tube",
                 "peeled", "grated", "shredded", "finely", "roughly", "large", "small",
                 "medium", "rinsed", "trimmed", "softened", "melted", "optional",
                 "taste", "for", "and", "the", "with", "from", "into", "cut", "pieces"}
        ing_words = {_stem(w) for w in re.findall(r"[a-z]+", ing) if len(w) > 2}
        usda_words = {_stem(w) for w in re.findall(r"[a-z]+", usda_full) if len(w) > 2}

        def _match(w, pool):
            return w in pool or any(len(w) > 4 and len(p) > 4 and (w in p or p in w)
                                    for p in pool)

        def _covered(w):
            return _match(w, ing_words)

        ing_content = [w for w in ing_words if w not in _prep]
        if ing_content:
            cover = sum(1 for w in ing_content if _match(w, usda_words)) / float(len(ing_content))
        else:
            cover = 0.0
        head = [_stem(w) for w in re.findall(r"[a-z]+", segs[0]) if len(w) > 2]
        head = [w for w in head if w not in _generic]
        head_pen = 1.0
        if len(head) > 1:
            missing = sum(1 for w in head if not _covered(w))
            head_pen = 1.0 - 0.5 * (missing / float(len(head)))
        anchor = cover * head_pen
        anchor_factor = 0.3 + 0.7 * anchor

        # Neutral-only bonus: an extra segment is neutral if listed, or every content
        # word is generic or already mentioned by the ingredient.
        def _seg_neutral(s):
            if s in _NEUTRAL:
                return True
            ws = [_stem(w) for w in re.findall(r"[a-z]+", s) if len(w) > 2]
            ws = [w for w in ws if w not in _generic and w not in _NEUTRAL]
            return all(_covered(w) for w in ws)

        rest = segs[1:]
        if rest:
            neutral_ratio = sum(1 for s in rest if _seg_neutral(s)) / float(len(rest))
        else:
            neutral_ratio = 1.0

        score = 100.0 * survival * anchor_factor * (0.85 + 0.15 * neutral_ratio)
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
