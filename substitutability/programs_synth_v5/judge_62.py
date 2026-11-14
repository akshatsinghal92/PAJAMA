import re
import math


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower().strip()
        usda = str(usda_match or "").lower().strip()
        if not ing or not usda:
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing)
        usda = re.sub(r"\([^)]*\)", " ", usda)
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\s+", "", ing)
        ing_main = ing.split(",")[0].strip()
        segs = [s.strip() for s in usda.split(",") if s.strip()]
        if not segs or not ing_main:
            return 0.0

        # Dish-ness evidence on each side, as log-odds-like weights
        w_dish = {
            "salad": 2, "soup": 2.5, "casserole": 3, "sandwich": 3, "mix": 1.5, "blend": 1.5,
            "dinner": 3, "prepared": 2, "stuffed": 2.5, "pizza": 3, "taco": 3, "burrito": 3,
            "stew": 2.5, "pie": 2, "entree": 3, "meal": 2.5, "pasta": 1, "sauce": 1.5,
            "kraut": 1.5, "sauerkraut": 1.5, "gravy": 1.5, "filling": 1.5, "topping": 1,
            "stir": 2, "with": 2, "and": 1.5, "in": 1, "bowl": 2, "roll": 1, "wrap": 2,
        }

        def dish_mass(text):
            words = re.findall(r"[a-z]+", text)
            m = 0.0
            for i, w in enumerate(words):
                if w in w_dish:
                    # decay: later mentions count less
                    m += w_dish[w] * (0.85 ** i)
            return m

        dm_i = dish_mass(ing_main)
        dm_u = dish_mass(" ".join(segs[:2]))
        # tail descriptors (after 2nd segment) with 'with'/'added' hint at mixtures
        tail = " ".join(segs[2:])
        tail_mix = 1.0 * len(re.findall(r"\bwith\b|\badded\b|\bsauce\b|\bcheese\b", tail))

        # Head-noun alignment: last word of ingredient main phrase vs USDA segments
        iw = [_stem(w) for w in re.findall(r"[a-z]+", ing_main)]
        junk = {"fresh", "frozen", "raw", "chopped", "sliced", "ground", "dried", "plain", "large", "small",
                "boneless", "skinless", "fillet", "shredded", "grated", "cubed", "soft", "whole", "of", "the"}
        iw_c = [w for w in iw if w not in junk] or iw
        head = iw_c[-1] if iw_c else ""
        modifiers = iw_c[:-1]

        useg_words = [[_stem(w) for w in re.findall(r"[a-z]+", s)] for s in segs]
        all_u = set(w for sw in useg_words for w in sw)

        # position weight: segment index of head in USDA
        head_pos = None
        for idx, sw in enumerate(useg_words):
            if head in sw:
                head_pos = idx
                break
        score = 5.0
        if head_pos is None:
            score -= 3.0
        else:
            score += 1.5 if head_pos == 0 else (0.5 if head_pos == 1 else -0.5)
        if modifiers:
            hit = sum(1 for m in modifiers if m in all_u)
            score += 2.0 * hit / len(modifiers) - 1.0
        else:
            score += 0.5

        # composite asymmetry via a squashed difference
        diff = dm_i - dm_u
        both = dm_i > 1.5 and dm_u > 1.5
        pen = 1.0 / (1.0 + math.exp(-abs(diff) + 1.5))  # 0..1
        score -= 5.0 * pen * (0.4 if both else 1.0)
        score -= min(tail_mix, 3) * 0.6

        # segment-count penalty: very long USDA descriptions are specific products
        score -= 0.15 * max(0, len(segs) - 3)
        return float(score)
    except Exception:
        return 0.0
