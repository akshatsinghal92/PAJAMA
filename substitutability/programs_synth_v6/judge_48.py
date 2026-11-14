import re


class Parsed(object):
    """Parsed view of a food string: head noun, modifiers, state flags, trailing descriptors."""

    TRANSFORMS = ("milk", "juice", "oil", "sauce", "soup", "pie", "cake", "cookie", "candy", "syrup", "pudding",
                  "jam", "jelly", "muffin", "chip", "flour", "salad", "dressing", "sandwich", "taco", "entree",
                  "stew", "loaf", "drink", "beverage", "extract", "vinegar", "seasoning", "nectar", "pretzel",
                  "bar", "snack", "frankfurter", "gravy", "dip", "spread", "paste", "powder")
    ANIMALS = ("beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "goose", "buffalo", "bison", "rabbit", "goat")
    SKIP = frozenset("""thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled
        rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in
        for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not
        eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak
        chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel
        without salt fat fresh raw whole heart seed delicious style lean domesticated imported new fluid white sliced""".split())
    SYN = {"aubergine": "eggplant", "courgette": "zucchini", "garbanzo": "chickpea", "scallion": "onion",
           "cilantro": "coriander", "rocket": "arugula", "capsicum": "pepper", "swede": "rutabaga", "beetroot": "beet",
           "maize": "corn", "prawn": "shrimp", "crawfish": "crayfish", "filbert": "hazelnut", "linseed": "flaxseed",
           "clementine": "tangerine", "mandarin": "tangerine", "yoghurt": "yogurt", "bison": "buffalo",
           "pinyon": "pine", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "battered": "batter",
           "buttered": "butter", "cos": "romaine", "ox": "beef", "calf": "veal", "fava": "broadbean",
           "innard": "giblet", "para": "brazil", "concord": "grape", "bing": "cherry", "navel": "orange",
           "gala": "apple", "fuji": "apple", "russet": "potato", "roma": "tomato", "portobello": "mushroom"}

    def __init__(self, text, is_usda):
        t = text
        if is_usda:
            t = " ".join(w for w in t.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper()))
        self.parens = self._tok(" ".join(re.findall(r"\(([^)]*)\)", t)))
        t = re.sub(r"\([^)]*\)", " ", t).lower()
        if not is_usda:
            t = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", t)
        self.raw = t
        self.segs = [self._tok(s) for s in t.split(",") if s.strip()]
        self.flat = [w for s in self.segs for w in s]
        self.set = set(self.flat) | set(self.parens)

    @staticmethod
    def _tok(s):
        s = s.replace("-", " ")
        s = re.sub(r"\bapple ?sauce\b", "applesauce", s)
        out = []
        for w in re.findall(r"[a-z]+", s):
            if len(w) > 4 and w.endswith("ies"):
                w = w[:-3] + "y"
            elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
                w = w[:-1]
            out.append(Parsed.SYN.get(w, w))
        return out

    def core(self):
        seg = self.segs[0] if self.segs else []
        words = [w for w in seg if w not in self.SKIP and not self.flag_word(w)]
        return words or [w for w in seg if w not in self.SKIP] or seg

    @staticmethod
    def flag_word(w):
        return bool(re.match(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet)$", w))

    def has(self, *words):
        return any(w in self.set for w in words)


def _position_of(parsed, head):
    for i, seg in enumerate(parsed.segs):
        if head in seg:
            return i, seg.index(head), seg
    return None


def judging_function(ingredient, usda_match):
    try:
        ing = Parsed(str(ingredient or ""), False)
        # for the ingredient only the pre-comma phrase defines the food; post-comma words are state hints
        first_phrase = ing.raw.split(",")[0]
        ing_main = Parsed(first_phrase, False)
        usda = Parsed(str(usda_match or ""), True)
        if not ing_main.segs or not usda.segs:
            return 0.0
        core = ing_main.core()
        head, mods = core[-1], core[:-1]
        pos = _position_of(usda, head)
        total = 0.0
        if pos is None:
            total = 1.0 + 4.0 * (sum(1 for w in core if w in usda.set) / float(len(core)))
            if head in usda.parens:
                total += 3.0
        else:
            si, k, seg = pos
            led_by_transform = bool(usda.segs[0]) and usda.segs[0][0] in Parsed.TRANSFORMS and usda.segs[0][0] not in ing.set
            trailed_by_transform = any(w in Parsed.TRANSFORMS and w not in ing.set for w in seg[k + 1:])
            if trailed_by_transform or (si > 0 and led_by_transform) or (si == 0 and k > 0 and led_by_transform):
                total = 1.5 + len([w for w in mods if w in usda.set])
            else:
                animals_i = set(w for w in core if w in Parsed.ANIMALS)
                animals_u = set(w for w in usda.flat if w in Parsed.ANIMALS)
                if animals_i and animals_u and not (animals_i & animals_u):
                    total = 2.0
                else:
                    miss = sum(1 for w in mods if w not in usda.set)
                    total = 8.0 - 3.0 * min(miss, 2) - 0.8 * si
        # state and descriptor adjustments expressed through regexes on the raw strings
        i_raw = " " + ing.raw + " "
        u_raw = " " + usda.raw + " "
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        i_cook, u_cook = bool(re.search(cook, i_raw)), bool(re.search(cook, u_raw))
        if u_cook and not i_cook and not re.search(r"\braw\b", u_raw):
            total -= 2.3
        if i_cook and not u_cook:
            total -= 1.3
        i_dry = bool(re.search(r"\b(dried|dehydrated)\b", i_raw)) and not i_cook
        u_dry = bool(re.search(r"\b(dried|dehydrated)\b", u_raw)) and "from dried" not in u_raw
        if i_dry != u_dry:
            total -= 2.5
        for w in ("pickled", "smoked"):
            if (w in i_raw) != (w in u_raw):
                total -= 2.5
        if (" canned" in i_raw) != (" canned" in u_raw) and not (" canned" in u_raw and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple"}):
            total -= 1.8
        if bool(re.search(r"\b(ground|powdered|powder)\b", i_raw)) != bool(re.search(r"\b(ground|powdered|powder)\b", u_raw)):
            total -= 1.3
        parts = r"\b(leaf|leaves|bone|peel|stem|shell)\b"
        if set(re.findall(parts, i_raw)) != set(re.findall(parts, u_raw)):
            total -= 2.7
        if re.match(r"^\s*(frozen|dried|canned|smoked)\b", usda.raw) and not re.search(r"\b(frozen|dried|canned|smoked)\b", i_raw):
            total -= 2.6
        diet = r"\b(low ?fat|non ?fat|reduced|light|lite|skim|lactose|sodium|decaffeinated|diet|sweetened|unsweetened|flavored|fortified|hydrogenated)\b"
        d_u = set(re.findall(diet, u_raw))
        d_i = set(re.findall(diet, i_raw))
        total -= 0.9 * min(len(d_u - d_i) + 0.5 * len(d_i - d_u), 3.0)
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_raw):
            total -= 3.5
        extra = [w for w in usda.segs[0] if w not in ing.set and w not in Parsed.SKIP and not Parsed.flag_word(w) and w not in core and w not in Parsed.ANIMALS and w not in ("fish", "nut", "seed", "cheese", "cream", "lettuce", "crustacean", "fruit", "vegetable", "game", "mollusk", "organ", "sausage", "tea", "cereal", "bread", "pasta", "noodle", "rice", "bean", "yogurt")]
        total -= 0.7 * min(len(extra), 3)
        total -= 0.03 * max(0, len(usda.segs) - 3)
        return float(total)
    except Exception:
        return 0.0
