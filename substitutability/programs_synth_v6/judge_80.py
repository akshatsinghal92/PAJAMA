import math
import re

# Rule-object pipeline judge. Each rule is a small class with apply(ctx) -> cost (>= 0) or bonus (<= 0).
# The pipeline sums costs (capped per family) and squashes with a logistic. Compound integrity is a rule
# family that only ever adds cost; conjunct lists ("beef and pork") are compared as SETS.


class Ctx(object):
    pass


class Rule(object):
    family = "misc"
    cap = 9.0

    def apply(self, c):
        return 0.0


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
        return w[:-1]
    return w


_ALIAS = dict(x.split("=") for x in (
    "clementine=tangerine mandarin=tangerine satsuma=tangerine filbert=hazelnut linseed=flaxseed crawfish=crayfish prawn=shrimp garbanzo=chickpea scallion=onion cilantro=coriander "
    "aubergine=eggplant courgette=zucchini rocket=arugula maize=corn bison=buffalo pinyon=pine pinon=pine dehydrated=dried uncooked=raw unroasted=raw poultry=chicken yoghurt=yogurt "
    "fava=broadbean para=brazil ox=beef calf=veal innard=giblet cos=romaine granada=pomegranate swede=rutabaga beetroot=beet capsicum=pepper treacle=molasses catsup=ketchup "
    "mutton=lamb golden=yellow wrap=tortilla flat=wing").split())


def tokens(text):
    text = text.replace("dairy-free", "vegan").replace("plant-based", "vegan").replace("variety meats and by-products", "organ").replace("variety meats", "organ")
    return [_ALIAS.get(_stem(w.replace("é", "e")), _stem(w.replace("é", "e"))) for w in re.findall(r"[a-zé]+", text.replace("-", " "))]


def S(txt):
    return frozenset(txt.split())


NOISE = S("thawed chopped diced cubed crushed peeled halved torn rinsed warmed melted softened ripe finely boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety other than not eaten free range farmed mixed species commercial all strong brewed meat by product added moist segment piece wedge cube without salt fat delicious style domesticated new fluid sliced shredded minced atlantic pacific alaska american lunch snack soft buttery crispy ready eat steak chop fillet tail wing breast thigh shank loin roast rib floret strip chunk kernel heart white seed")
QUALW = S("raw cooked boiled baked roasted steamed simmered braised broiled grilled sauteed poached stewed toasted fried dried canned frozen smoked pickled cured ground powdered lowfat nonfat reduced light skim sweetened unsweetened unsalted salted decaffeinated lean")
CATEGORY = S("fish beef pork lamb veal chicken turkey duck nut seed cheese lettuce crustacean fruit vegetable game organ sausage cereal seaweed")
DISHN = S("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf")
DRIED_OK = S("pine brazil hazelnut raisin fig date apricot prune agar seaweed mushroom")
CANNED_OK = S("applesauce olive bean tomato pumpkin corn tuna pineapple tangerine")
BASE_ALT = S("soy almond oat coconut cashew vegan tofu")
MOD_FOODS = S("coconut cocoa peanut almond pecan apple oat rice palm sunflower olive sesame orange tomato lemon plum garlic egg wheat corn soy fish chicken pork beef vanilla chocolate strawberry cherry banana honey hazelnut walnut cashew pistachio pumpkin mushroom bean pea potato onion carrot beet turnip squash")
PRODUCTS = S("milk butter oil juice sauce paste cream cheese yogurt syrup sugar vinegar flour bread cake cookie pie soup jam jelly powder extract starch noodle sausage ham stew wine dressing chip")
CULT = dict(concord="grape", bing="cherry", fuji="apple", gala="apple", bartlett="pear", russet="potato", roma="tomato", navel="orange", hass="avocado", portobello="mushroom", cremini="mushroom")
SIBS = dict(grape=S("concord muscadine thompson american"), squash=S("butternut hubbard acorn spaghetti"), apple=S("fuji gala granny"), potato=S("russet yukon"), orange=S("navel valencia"),
            dressing=S("italian french ranch caesar thousand greek russian"), cheese=S("cheddar swiss mozzarella provolone brie camembert gouda colby parmesan"))
FIXED = [tuple(p.split()) for p in ("sweet potato;sea bass;bell pepper;ice cream;cream cheese;sour cream;cottage cheese;green tea;black tea;pine nut;brazil nut;water chestnut;butter bean;lima bean;kidney bean;snow pea;"
                                    "corn syrup;maple syrup;hot dog;black pepper;soy sauce;fish sauce;brown sugar;coconut sugar;cocoa butter;peanut butter;almond butter;pecan butter;apple butter;coconut milk;almond milk;"
                                    "soy milk;oat milk;rice milk;coconut cream;coconut oil;olive oil;sesame oil;palm oil;sunflower oil;peanut oil;apple juice;orange juice;tomato juice;lemon juice;plum sauce;apple sauce;"
                                    "tomato sauce;tomato paste;garlic paste;egg white;egg yolk;whole wheat;sweet corn;green onion;spring onion;red wine;white wine;rice vinegar;wine vinegar;cider vinegar;balsamic vinegar;"
                                    "sweet pepper;chicken ham;pork sausage;ground beef;hot sauce;corn bread;pita bread;rye bread;bean sprout;palm kernel;split pea").split(";")]
FIXED_SET = set(FIXED)


def rx(p, s):
    return re.search(p, s) is not None


def build(ingredient, usda):
    c = Ctx()
    text = " ".join(str(usda or "").split())
    keep = [t for t in text.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper() and re.sub(r"[^A-Za-z]", "", t).lower() not in ("nfs", "usda"))]
    text = " ".join(keep)
    c.par_u = set(tokens(" ".join(re.findall(r"\(([^)]*)\)", text)).lower()))
    c.u = re.sub(r"\([^)]*\)", " ", text).lower()
    raw_i = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", str(ingredient or "").lower())
    c.par_i = set(tokens(" ".join(re.findall(r"\(([^)]*)\)", raw_i))))
    c.i = re.sub(r"\([^)]*\)", " ", raw_i)
    c.main = tokens(c.i.split(",")[0])
    c.segs = [tokens(s) for s in c.u.split(",") if s.strip()]
    c.ok = bool(c.main and c.segs)
    if not c.ok:
        return c
    c.full_i = c.i + " " + " ".join(c.par_i)
    c.iset = set(tokens(c.i)) | c.par_i
    c.uset = set(w for s in c.segs for w in s) | c.par_u
    c.ub = c.uset | set(CULT.get(w, w) for w in c.uset)
    c.core = [w for w in c.main if w not in NOISE and w not in QUALW] or [w for w in c.main if w not in QUALW] or c.main
    c.head = c.core[-1]
    marks = [1.0 if (w in c.ub or CULT.get(w, w) in c.ub) else (0.8 if w in c.par_u else 0.0) for w in c.core]
    c.marks = marks
    c.cov = sum(marks) / float(len(c.core))
    c.soft_dairy = rx(r"\b(yogurt|kefir|milk)\b", c.u) and "cheese" not in c.u
    c.organ = "organ" in c.uset or bool(set(c.core) & S("liver kidney tongue heart giblet tripe brain gizzard"))
    return c


class HeadMissing(Rule):
    family = "identity"

    def apply(self, c):
        return 0.0 if c.marks[-1] > 0 else 3.4


class ModifiersMissing(Rule):
    family = "identity"

    def apply(self, c):
        miss = sum(1 for m in c.marks[:-1] if m == 0)
        return 1.7 * miss


class ExtraFirstSegment(Rule):
    family = "identity"

    def apply(self, c):
        spare = [w for w in c.segs[0] if w not in c.core and w not in c.iset and w not in NOISE and w not in QUALW and w not in CATEGORY]
        return 0.6 * min(len(spare), 3)


class SiblingConflict(Rule):
    family = "identity"

    def apply(self, c):
        for base, vs in SIBS.items():
            named = vs & c.iset
            if named and (base in c.uset or base in ("dressing", "cheese")) and not (named & c.uset) and (vs & c.uset):
                return 2.3
        return 0.0


class BaseAlternative(Rule):
    family = "identity"

    def apply(self, c):
        ia, ua = BASE_ALT & c.iset, BASE_ALT & c.uset
        return 1.7 if ((ua - ia) or ((ia - ua) and not ({"vegan", "tofu"} & ua))) else 0.0


class ConjunctSets(Rule):
    family = "identity"

    def apply(self, c):
        head_part = c.i.split(",")[0]
        if not rx(r"\band\b", head_part) or len(c.core) < 2:
            return 0.0
        i_conj = set(w for w in c.core if w not in ("and",))
        u_conj = set(w for s in c.segs[:1] for w in s if w not in NOISE)
        missing = [w for w in i_conj if w not in c.ub and w not in c.par_u]
        return 1.4 * min(len(missing), 2) if (not rx(r"\band\b", c.u) and missing) else (0.8 * min(len(missing), 2))


class CompoundBroken(Rule):
    family = "compound"
    cap = 6.0

    def apply(self, c):
        pairs_u = set()
        for s in c.segs:
            for a, b in zip(s, s[1:]):
                pairs_u.add((a, b))
                pairs_u.add((b, a))
        if len(c.segs) > 1:
            for a in c.segs[0]:
                for b in c.segs[1]:
                    pairs_u.add((a, b))
                    pairs_u.add((b, a))
        pairs_i = set(zip(c.core, c.core[1:])) | set(p for p in FIXED if p[0] in c.core and p[1] in c.core)
        broken = sum(1 for (a, b) in pairs_i if ((a, b) in FIXED_SET or (a in MOD_FOODS and b in PRODUCTS)) and (a, b) not in pairs_u)
        added = 0
        for a, b in FIXED:
            if a in c.uset and b in c.uset and (a, b) in pairs_u and not (a in c.iset and b in c.iset):
                # a plant-base ingredient (coconut yogurt) legitimately meets coconut milk entries
                if (a in BASE_ALT and a in c.iset) or (b in BASE_ALT and b in c.iset):
                    continue
                added += 1
        for seg in c.segs[:2]:
            for a, b in zip(seg, seg[1:]):
                if a in MOD_FOODS and b in PRODUCTS and a not in c.iset and b in c.iset:
                    added += 1
        return 3.0 * min(broken, 2) + 2.3 * min(added, 2)


class Qualifiers(Rule):
    family = "qualifier"
    cap = 8.0
    ROWS = [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0, ""), (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9, "fat"),
            (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6, ""), (r"decaf|lactose|\bdiet\b|low calorie|reduced calorie", r"decaf|lactose|diet|calorie", 1.8, ""),
            (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0, ""),
            (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2, ""),
            (r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 1.3, "origin"), (r"\bdeli\b|luncheon|prepackaged|shelf stable|ready[- ]to[- ]bake", r"deli|lunch|sliced", 1.1, ""),
            (r"\d+% lean|\d+% fat", r"\d+%", 1.5, ""), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0, ""), (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2, ""),
            (r"\bkernel\b", r"kernel", 1.5, ""), (r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", r"strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint", 1.1, "")]

    def apply(self, c):
        total = 0.0
        for ru, ri, w, tag in self.ROWS:
            if rx(ru, c.u) and not rx(ri, c.full_i):
                if tag == "fat" and c.soft_dairy:
                    w *= 0.3
                if tag == "origin" and c.organ:
                    w *= 0.3
                total += w
        return total


class StateMismatch(Rule):
    family = "state"
    cap = 8.0

    def apply(self, c):
        u, f = c.u, c.full_i
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = rx(cook, f), rx(cook, u)
        cost = 0.0
        cost += 2.0 if (uc and not ic and not rx(r"\braw\b", u)) else 0.0
        cost += (1.8 if rx(r"toasted|roasted|grilled|fried", f) else 1.0) if (ic and not uc) else 0.0
        cost += 1.0 if (rx(r"\bcanned\b", f) and rx(r"\braw\b", u)) else 0.0
        di = rx(r"\b(dried|dehydrated)\b", f) and not ic
        du = rx(r"\b(dried|dehydrated)\b", u) and "from dried" not in u
        cost += 2.2 if (di != du and not (du and set(c.core) & DRIED_OK)) else 0.0
        cost += 2.2 * sum(1 for w in ("pickled", "smoked") if (w in f) != (w in u))
        cn = rx(r"\bcanned\b", u)
        cost += 1.5 if (rx(r"\bcanned\b", f) != cn and not (cn and set(c.core) & CANNED_OK)) else 0.0
        cost += 1.7 if (rx(r"\b(ground|powdered|powder)\b", f) != rx(r"\b(ground|powdered|powder)\b", u)) else 0.0
        cost += 2.2 if (c.segs[0][:1] and c.segs[0][0] in ("frozen", "dried", "canned", "smoked") and c.segs[0][0] not in c.iset) else 0.0
        return cost


class ShapeForm(Rule):
    family = "shape"
    cap = 8.0

    def apply(self, c):
        u, f = c.u, c.full_i
        cost = 0.0
        cost += 2.4 if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", f)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u)) else 0.0
        cost += 2.8 if ((set(c.segs[0]) & DISHN) - c.iset - set(c.core)) else 0.0
        cost += 2.8 if (rx(r"\bstew (meat|beef|lamb|pork)\b", f) and "stew" in c.segs[0]) else 0.0
        cost += 1.0 if (rx(r"\bbone[- ]in\b", f) and not rx(r"\bbone\b", u)) else 0.0
        cost += 3.0 if rx(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u) else 0.0
        return cost


PIPELINE = [HeadMissing(), ModifiersMissing(), ExtraFirstSegment(), SiblingConflict(), BaseAlternative(), ConjunctSets(), CompoundBroken(), Qualifiers(), StateMismatch(), ShapeForm()]
FAMILY_WEIGHT = {"identity": 0.95, "compound": 1.0, "qualifier": 0.9, "state": 0.9, "shape": 0.9}


def judging_function(ingredient, usda_match):
    try:
        c = build(ingredient, usda_match)
        if not c.ok:
            return 0.0
        per_family = {}
        for r in PIPELINE:
            per_family[r.family] = per_family.get(r.family, 0.0) + r.apply(c)
        total = 0.0
        for fam, cost in per_family.items():
            cap = 9.0 if fam == "identity" else (6.0 if fam == "compound" else 8.0)
            total += FAMILY_WEIGHT.get(fam, 0.9) * min(cost, cap)
        z = 4.0 + 5.0 * c.cov - total
        return float(z / 2.0 + 0.3 * c.cov)
    except Exception:
        return 0.0
