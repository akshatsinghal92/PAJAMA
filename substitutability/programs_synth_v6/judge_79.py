import math
import re

# Noisy-AND judge with a compound gate, written as a small interpreter over text tables ("DSL").
# Tables are strings parsed once at import time, so the scoring code stays short and the knowledge
# (compounds, qualifier rules, cost rules) reads like data.

COMPOUND_TABLE = """
sweet potato; sea bass; bell pepper; ice cream; cream cheese; sour cream; cottage cheese; green tea; black tea; pine nut; brazil nut
water chestnut; butter bean; lima bean; kidney bean; snow pea; corn syrup; maple syrup; hot dog; black pepper; soy sauce; fish sauce
brown sugar; coconut sugar; cocoa butter; peanut butter; almond butter; pecan butter; apple butter; coconut milk; almond milk; soy milk
oat milk; rice milk; coconut cream; coconut oil; olive oil; sesame oil; palm oil; sunflower oil; peanut oil; apple juice; orange juice
tomato juice; lemon juice; plum sauce; apple sauce; tomato sauce; tomato paste; garlic paste; egg white; egg yolk; whole wheat; sweet corn
green onion; spring onion; red wine; white wine; rice vinegar; wine vinegar; cider vinegar; balsamic vinegar; sweet pepper; chicken ham
pork sausage; ground beef; hot sauce; corn bread; pita bread; rye bread; bean sprout; palm kernel; split pea
"""
KNOWN_PAIRS = set(tuple(p.split()) for p in re.split(r"[;\n]", COMPOUND_TABLE) if len(p.split()) == 2)

# qualifier table: label | usda regex | licence regex (ingredient side) | weight
QUAL_TABLE = r"""
sodium | low ?sodium|reduced sodium|no salt added|sodium free | sodium | 2.0
fat | fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat | fat|light|lite|skim|lean|diet | 1.9
sugar | sugar ?free|unsweetened|sweetened | sweet|sugar | 1.6
diet | decaf|lactose|\bdiet\b|low calorie|reduced calorie | decaf|lactose|diet|calorie | 1.8
mixin | \bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b | \bwith\b|\band\b | 2.0
recipe | made (with|from)|prepared (with|from)|from mix|dry mix | made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread | 1.2
origin | new zealand|northern plains|hawaii|beaked|native|shoshone | new zealand|hawaii | 1.3
deli | \bdeli\b|luncheon|prepackaged|shelf stable|ready[- ]to[- ]bake | deli|lunch|sliced | 1.1
ratio | \d+% lean|\d+% fat | \d+% | 1.5
coating | breaded|battered|coated|glazed|candied | bread|batter|coated|glazed|candied|crispy | 1.0
fatadded | fat added|added fat | saut|fried|butter|oil|fat | 1.2
kernel | \bkernel\b | kernel | 1.5
flavour | \b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b | strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint | 1.1
"""
QUAL_ROWS = []
for _line in QUAL_TABLE.strip().split("\n"):
    _lab, _ru, _ri, _w = [x.strip() for x in _line.split(" | ")]
    QUAL_ROWS.append((_lab, re.compile(_ru), re.compile(_ri), float(_w)))

WORDLISTS = {
    "noise": "thawed chopped diced cubed crushed peeled halved torn rinsed warmed melted softened ripe finely boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety other than not eaten free range farmed mixed species commercial all strong brewed meat by product added moist segment piece wedge cube without salt fat delicious style domesticated new fluid sliced shredded minced atlantic pacific alaska american lunch snack soft buttery crispy ready eat steak chop fillet tail wing breast thigh shank loin roast rib floret strip chunk kernel heart white seed",
    "qual": "raw cooked boiled baked roasted steamed simmered braised broiled grilled sauteed poached stewed toasted fried dried canned frozen smoked pickled cured ground powdered lowfat nonfat reduced light skim sweetened unsweetened unsalted salted decaffeinated lean",
    "category": "fish beef pork lamb veal chicken turkey duck nut seed cheese lettuce crustacean fruit vegetable game organ sausage cereal seaweed",
    "dish": "oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf",
    "dried_ok": "pine brazil hazelnut raisin fig date apricot prune agar seaweed mushroom",
    "canned_ok": "applesauce olive bean tomato pumpkin corn tuna pineapple tangerine",
    "base_alt": "soy almond oat coconut cashew vegan tofu",
    "modifier_food": "coconut cocoa peanut almond pecan apple oat rice palm sunflower olive sesame orange tomato lemon plum garlic egg wheat corn soy fish chicken pork beef vanilla chocolate strawberry cherry banana honey hazelnut walnut cashew pistachio pumpkin mushroom bean pea potato onion carrot beet turnip squash",
    "product": "milk butter oil juice sauce paste cream cheese yogurt syrup sugar vinegar flour bread cake cookie pie soup jam jelly powder extract starch noodle sausage ham stew wine dressing chip",
}
W = {k: frozenset(v.split()) for k, v in WORDLISTS.items()}
ALIAS_TEXT = ("clementine=tangerine mandarin=tangerine satsuma=tangerine filbert=hazelnut linseed=flaxseed crawfish=crayfish prawn=shrimp garbanzo=chickpea scallion=onion cilantro=coriander "
              "aubergine=eggplant courgette=zucchini rocket=arugula maize=corn bison=buffalo pinyon=pine pinon=pine dehydrated=dried uncooked=raw unroasted=raw poultry=chicken yoghurt=yogurt "
              "fava=broadbean para=brazil ox=beef calf=veal innard=giblet cos=romaine granada=pomegranate swede=rutabaga beetroot=beet capsicum=pepper treacle=molasses catsup=ketchup "
              "mutton=lamb golden=yellow wrap=tortilla flat=wing")
ALIAS = dict(x.split("=") for x in ALIAS_TEXT.split())
CULTIVARS = {"concord": "grape", "bing": "cherry", "fuji": "apple", "gala": "apple", "bartlett": "pear", "russet": "potato", "roma": "tomato", "navel": "orange", "hass": "avocado", "portobello": "mushroom", "cremini": "mushroom"}
SIBLINGS = {"grape": "concord muscadine thompson american", "squash": "butternut hubbard acorn spaghetti", "apple": "fuji gala granny", "potato": "russet yukon", "orange": "navel valencia",
            "dressing": "italian french ranch caesar thousand greek russian", "cheese": "cheddar swiss mozzarella provolone brie camembert gouda colby parmesan"}
SIB = {k: frozenset(v.split()) for k, v in SIBLINGS.items()}
STATE_PREFIX = ("frozen", "dried", "canned", "smoked")


def words(text):
    text = text.replace("dairy-free", "vegan").replace("plant-based", "vegan").replace("variety meats and by-products", "organ").replace("variety meats", "organ")
    out = []
    for w in re.findall(r"[a-zé]+", text.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(ALIAS.get(w, w))
    return out


def yes(rx, s):
    return re.search(rx, s) is not None


def adjacent_pairs(seg_words):
    out = set()
    for s in seg_words:
        for a, b in zip(s, s[1:]):
            out.add((a, b))
            out.add((b, a))
    if len(seg_words) > 1:
        for a in seg_words[0]:
            for b in seg_words[1]:
                out.add((a, b))
                out.add((b, a))
    return out


def judging_function(ingredient, usda_match):
    try:
        text_u = " ".join(str(usda_match or "").split())
        kept = [t for t in text_u.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper() and re.sub(r"[^A-Za-z]", "", t).lower() not in ("nfs", "usda"))]
        text_u = " ".join(kept)
        par_u = set(words(" ".join(re.findall(r"\(([^)]*)\)", text_u)).lower()))
        u = re.sub(r"\([^)]*\)", " ", text_u).lower()
        raw_i = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", str(ingredient or "").lower())
        par_i = set(words(" ".join(re.findall(r"\(([^)]*)\)", raw_i))))
        i = re.sub(r"\([^)]*\)", " ", raw_i)
        main = words(i.split(",")[0])
        segs = [words(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        iset = set(words(i)) | par_i
        uset = set(w for s in segs for w in s) | par_u
        ub = uset | set(CULTIVARS.get(w, w) for w in uset)
        core = [w for w in main if w not in W["noise"] and w not in W["qual"]] or [w for w in main if w not in W["qual"]] or main
        head = core[-1]
        full_i = i + " " + " ".join(par_i)

        # ---- aspect: food identity
        marks = [1.0 if (w in ub or CULTIVARS.get(w, w) in ub) else (0.8 if w in par_u else 0.0) for w in core]
        cov = sum(marks) / float(len(core))
        a_food = 0.1 + 0.9 * (0.6 * cov + 0.4 * marks[-1])
        spare = [w for w in segs[0] if w not in core and w not in iset and w not in W["noise"] and w not in W["qual"] and w not in W["category"]]
        a_food *= 0.85 ** min(len(spare), 3)
        for base, vs in SIB.items():
            named = vs & iset
            if named and (base in uset or base in ("dressing", "cheese")) and not (named & uset) and (vs & uset):
                a_food *= 0.35
        ia, ua = W["base_alt"] & iset, W["base_alt"] & uset
        if (ua - ia) or ((ia - ua) and not ({"vegan", "tofu"} & ua)):
            a_food *= 0.55

        # ---- aspect: compound integrity (penalty only)
        pairs_u = adjacent_pairs(segs)
        pairs_i = set(zip(core, core[1:]))
        pairs_i |= set(p for p in KNOWN_PAIRS if p[0] in core and p[1] in core)
        broken = sum(1 for (a, b) in pairs_i if ((a, b) in KNOWN_PAIRS or (a in W["modifier_food"] and b in W["product"])) and (a, b) not in pairs_u)
        added = 0
        for a, b in KNOWN_PAIRS:
            if a in uset and b in uset and (a, b) in pairs_u and not (a in iset and b in iset):
                added += 1
        for seg in segs[:2]:
            for a, b in zip(seg, seg[1:]):
                if a in W["modifier_food"] and b in W["product"] and a not in iset and b in iset:
                    added += 1
        a_comp = (0.2 ** min(broken, 2)) * (0.3 ** min(added, 2))

        # ---- aspect: unstated qualifiers
        soft = yes(r"\b(yogurt|kefir|milk)\b", u) and "cheese" not in u
        organ = "organ" in uset or bool(set(core) & {"liver", "kidney", "tongue", "heart", "giblet", "tripe", "brain", "gizzard"})
        cost = 0.0
        for lab, ru, ri, w in QUAL_ROWS:
            if ru.search(u) and not ri.search(full_i):
                if lab == "fat" and soft:
                    w *= 0.3
                if lab == "origin" and organ:
                    w *= 0.3
                cost += w
        a_qual = math.exp(-0.45 * min(cost, 8.0))

        # ---- aspect: state
        st = 0.0
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = yes(cook, full_i), yes(cook, u)
        st += 2.0 if (uc and not ic and not yes(r"\braw\b", u)) else 0.0
        st += (1.8 if yes(r"toasted|roasted|grilled|fried", full_i) else 1.0) if (ic and not uc) else 0.0
        st += 1.0 if (yes(r"\bcanned\b", full_i) and yes(r"\braw\b", u)) else 0.0
        di = yes(r"\b(dried|dehydrated)\b", full_i) and not ic
        du = yes(r"\b(dried|dehydrated)\b", u) and "from dried" not in u
        st += 2.2 if (di != du and not (du and set(core) & W["dried_ok"])) else 0.0
        st += 2.2 * sum(1 for w in ("pickled", "smoked") if (w in full_i) != (w in u))
        cn = yes(r"\bcanned\b", u)
        st += 1.5 if (yes(r"\bcanned\b", full_i) != cn and not (cn and set(core) & W["canned_ok"])) else 0.0
        st += 1.7 if (yes(r"\b(ground|powdered|powder)\b", full_i) != yes(r"\b(ground|powdered|powder)\b", u)) else 0.0
        st += 2.2 if (segs[0][:1] and segs[0][0] in STATE_PREFIX and segs[0][0] not in iset) else 0.0
        a_state = math.exp(-0.5 * min(st, 8.0))

        # ---- aspect: shape / form
        sh = 0.0
        sh += 2.4 if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", full_i)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u)) else 0.0
        sh += 2.8 if ((set(segs[0]) & W["dish"]) - iset - set(core)) else 0.0
        sh += 2.8 if (yes(r"\bstew (meat|beef|lamb|pork)\b", full_i) and "stew" in segs[0]) else 0.0
        sh += 1.0 if (yes(r"\bbone[- ]in\b", full_i) and not yes(r"\bbone\b", u)) else 0.0
        sh += 3.0 if yes(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u) else 0.0
        sh += 1.4 if (len(core) >= 2 and yes(r"\band\b", i.split(",")[0]) and not yes(r"\band\b", u) and cov < 1.0) else 0.0
        a_shape = math.exp(-0.5 * min(sh, 8.0))

        joint = a_food * a_comp * a_qual * a_state * a_shape
        return float(10.0 * math.sqrt(joint + 0.02) + 0.2 * cov)
    except Exception:
        return 0.0
