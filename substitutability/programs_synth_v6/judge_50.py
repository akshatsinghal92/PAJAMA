import re
import unicodedata

_CANON_SUBS = [
    (r"\bapple ?(sauce|puree)\b", "applesauce"), (r"\bpine ?nuts?\b|\bpinyon\b|\bpinon\b|\bpignoli\b", "pinenut"),
    (r"\bbrazil nuts?\b|\bpara nuts?\b", "brazilnut"), (r"\bsweet potato(es)?\b", "sweetpotato"),
    (r"\bgreen onions?\b|\bspring onions?\b|\bscallions?\b", "onion"), (r"\bgarbanzo( beans?)?\b|\bchick ?peas?\b", "chickpea"),
    (r"\bfava( beans?)?\b|\bfaba beans?\b|\bbroad beans?\b|\bbroadbeans?\b", "broadbean"), (r"\bclementines?\b|\bmandarin( oranges?)?\b|\bsatsumas?\b|\btangerines?\b", "tangerine"),
    (r"\bfilberts?\b|\bhazelnuts?\b", "hazelnut"), (r"\blinseeds?\b|\bflax ?seeds?\b", "flaxseed"), (r"\bcrawfish\b|\bcrayfish\b|\bcrawdads?\b", "crayfish"),
    (r"\bprawns?\b|\bshrimps?\b", "shrimp"), (r"\bbison\b|\bbuffalo\b", "buffalo"), (r"\baubergines?\b|\beggplants?\b", "eggplant"),
    (r"\bcourgettes?\b|\bzucchinis?\b", "zucchini"), (r"\bcilantro\b|\bcoriander leaves?\b", "coriander"), (r"\brocket\b|\barugula\b", "arugula"),
    (r"\bmaize\b", "corn"), (r"\byogh?urts?\b", "yogurt"), (r"\bcatsup\b", "ketchup"), (r"\bhalf[- ]and[- ]half\b|\bequal parts milk and cream\b", "halfandhalf"),
    (r"\bglass noodles?\b|\bcellophane noodles?\b|\bbean threads?\b|\blong rice\b", "cellophanenoodle"), (r"\bhot dogs?\b|\bwieners?\b|\bfrankfurters?\b", "frankfurter"),
    (r"\bplant[- ]based\b|\bdairy[- ]free\b|\bnon[- ]dairy\b|\bvegan\b", "vegan"), (r"\bgolden delicious\b", "yellowapple"),
    (r"\bvariety meats?( and by-?products?)?\b|\borgan meats?\b|\bgiblets?\b|\binnards?\b", "organmeat"), (r"\bpoultry\b", "chicken"), (r"\bcalf\b", "veal"), (r"\box\b", "beef"),
]
_COMPILED = [(re.compile(p), r) for p, r in _CANON_SUBS]

_VARIETY_BASE = {"concord": "grape", "thompson": "grape", "bing": "cherry", "rainier": "cherry", "fuji": "apple", "gala": "apple", "granny": "apple", "mcintosh": "apple",
                 "bartlett": "pear", "anjou": "pear", "russet": "potato", "yukon": "potato", "roma": "tomato", "navel": "orange", "valencia": "orange", "hass": "avocado",
                 "butternut": "squash", "acorn": "squash", "portobello": "mushroom", "cremini": "mushroom", "shiitake": "mushroom", "basmati": "rice", "jasmine": "rice"}

# qualifier classes: name -> (regex, weight)
_QUAL = {
    "sodium": (r"\blow ?sodium\b|\breduced sodium\b|\bno salt added\b|\bsodium free\b", 2.0),
    "fat": (r"\bfat ?free\b|\bnon ?fat\b|\bskim\b|\blow ?fat\b|\breduced fat\b|\blite\b|\blight\b|\bmilkfat\b", 1.9),
    "sugar": (r"\bsugar ?free\b|\bunsweetened\b|\bsweetened\b|\bwith sugar\b", 1.6),
    "salt": (r"\bwith salt\b|\bsalted\b|\bsalt added\b", 1.2),
    "addedfat": (r"\bfat added\b|\badded fat\b|\bmade with oil\b", 1.2),
    "lactose": (r"\blactose[- ]reduced\b|\blactose free\b", 1.8),
    "caffeine": (r"\bdecaffeinated\b|\bdecaf\b", 1.8),
    "diet": (r"\bdiet\b|\blow calorie\b", 1.8),
    "mixin": (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", 2.0),
    "recipe": (r"\bmade (with|from)\b|\bprepared (with|from)\b|\bfrom mix\b|\bdry mix\b", 1.3),
    "origin": (r"\bnew zealand\b|\bnorthern plains\b|\bhawaii\b|\bbeaked\b|\bnative\b", 1.4),
    "imported": (r"\bimported\b", 0.7),
    "deli": (r"\bdeli\b|\bluncheon\b|\bprepackaged\b|\bshelf stable\b|\bready[- ]to[- ](bake|fry|serve)\b", 1.1),
    "coating": (r"\bbreaded\b|\bbattered\b|\bcoated\b|\bglazed\b|\bcandied\b", 1.8),
    "flavour": (r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", 1.2),
}
_STOPW = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious style lean domesticated new fluid white sliced atlantic pacific alaska american".split())
_STATE_RX = r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet)$"


def _fold(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
    return s.replace("-", " ")


def _canon(s):
    s = _fold(s)
    for rx, rep in _COMPILED:
        s = rx.sub(rep, s)
    return s


def _words(s):
    out = []
    for w in re.findall(r"[a-z]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(w)
    return out


def _qual_flags(text):
    return {k for k, (rx, w) in _QUAL.items() if re.search(rx, text)}


def judging_function(ingredient, usda_match):
    try:
        raw_u = " ".join(w for w in str(usda_match or "").split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper()))
        paren_txt = " ".join(re.findall(r"\(([^)]*)\)", raw_u))
        i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
        u_txt = re.sub(r"\([^)]*\)", " ", raw_u.lower())
        ic, uc_ = _canon(i_txt), _canon(u_txt)
        pc = _canon(paren_txt)
        imain = ic.split(",")[0]
        iw = _words(imain)
        usegs = [_words(s) for s in uc_.split(",") if s.strip()]
        if not iw or not usegs:
            return 0.0
        uflat = [w for s in usegs for w in s]
        uset = set(uflat) | set(_words(pc))
        core = [w for w in iw if w not in _STOPW and not re.match(_STATE_RX, w)] or [w for w in iw if w not in _STOPW] or iw
        core = [_VARIETY_BASE.get(w, w) for w in core]
        uset2 = uset | set(_VARIETY_BASE.get(w, w) for w in uset)
        head = core[-1]
        cov = sum(1 for w in core if w in uset2) / float(len(core))
        # asymmetric added-qualifier load by class
        qi, qu = _qual_flags(ic), _qual_flags(uc_)
        added = qu - qi
        # flavour is not "added" when the ingredient names it (checked per word)
        for fw in list(added):
            if fw == "flavour":
                fl = re.findall(_QUAL["flavour"][0], uc_)
                if all(re.search(r"\b" + re.escape(f), ic) for f in fl):
                    added.discard(fw)
        soft_dairy = bool(re.search(r"\b(yogurt|kefir|milk)\b", uc_)) and "cheese" not in uc_
        meat_hier = "organmeat" in uc_ or bool(re.search(r"\b(beef|pork|lamb|veal|chicken|turkey|buffalo)\b", uc_))
        load = 0.0
        for k in added:
            w = _QUAL[k][1]
            if k == "fat" and soft_dairy:
                w *= 0.35
            if k == "imported" and meat_hier:
                w *= 0.4
            if k == "origin" and meat_hier:
                w *= 0.6
            if k == "addedfat" and re.search(r"\b(sauteed|fried|buttered|butter|oil)\b", ic):
                w = 0.0
            load += w
        dropped = sum(0.45 * _QUAL[k][1] for k in (qi - qu))
        score = 5.0 * cov + (1.6 if head in uset2 else -1.4) - 0.95 * min(load, 6.0) - min(dropped, 2.0)
        # states (regex)
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        i_cook, u_cook = bool(re.search(cook, ic)), bool(re.search(cook, uc_))
        if u_cook and not i_cook and not re.search(r"\braw\b", uc_):
            score -= 2.2
        if i_cook and not u_cook:
            score -= 1.3
        d_i = bool(re.search(r"\b(dried|dehydrated)\b", ic)) and not i_cook
        d_u = bool(re.search(r"\b(dried|dehydrated)\b", uc_)) and "from dried" not in uc_
        if d_i != d_u and not (d_u and set(core) & {"pinenut", "brazilnut", "hazelnut", "raisin", "fig", "date", "apricot", "prune"}):
            score -= 2.4
        for w in ("pickled", "smoked"):
            if (w in ic) != (w in uc_):
                score -= 2.4
        cn = re.search(r"\bcanned\b", uc_)
        if bool(re.search(r"\bcanned\b", ic)) != bool(cn) and not (cn and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple"}):
            score -= 1.7
        if bool(re.search(r"\b(ground|powdered|powder)\b", ic)) != bool(re.search(r"\b(ground|powdered|powder)\b", uc_)):
            score -= 1.2
        if set(re.findall(r"\b(leaf|leaves|bone|peel|stem|shell)\b", ic)) != set(re.findall(r"\b(leaf|leaves|bone|peel|stem|shell)\b", uc_)):
            score -= 2.6
        first = usegs[0]
        forms = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
        if (set(first) & forms) - set(_words(ic)) and not (set(first) & forms) <= set(core):
            score -= 3.2
        if first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in ic:
            score -= 2.5
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", uc_):
            score -= 3.5
        return float(score + 2.0)
    except Exception:
        return 0.0
