import re

PARTS = {
    'breast': {'breast', 'breasts'}, 'thigh': {'thigh', 'thighs'}, 'wing': {'wing', 'wings'},
    'drumstick': {'drumstick', 'drumsticks', 'leg', 'legs'}, 'loin': {'loin', 'tenderloin'},
    'shoulder': {'shoulder', 'chuck'}, 'sirloin': {'sirloin'}, 'rib': {'rib', 'ribs'},
    'belly': {'belly', 'bacon'}, 'skin': {'skin'}, 'liver': {'liver'}, 'heart': {'heart'},
    'yolk': {'yolk', 'yolks'}, 'white': {'white', 'whites'}, 'zest': {'zest', 'peel', 'rind'},
    'juice': {'juice'}, 'leaves': {'leaves', 'leaf', 'greens'}, 'root': {'root', 'roots'},
    'stem': {'stem', 'stems', 'stalk', 'stalks'}, 'seed': {'seed', 'seeds', 'kernel', 'kernels'},
    'flower': {'flower', 'flowers', 'blossom', 'florets'}, 'bran': {'bran'}, 'germ': {'germ'},
    'fillet': {'fillet', 'fillets'}, 'ground': {'ground', 'mince', 'minced'},
    'shank': {'shank'}, 'tail': {'tail', 'oxtail'}, 'tongue': {'tongue'}, 'neck': {'neck'},
    'back': {'back'}, 'bone': {'bone', 'bones', 'bone-in'}, 'fat': {'fat', 'lard', 'tallow'},
    'flank': {'flank'}, 'brisket': {'brisket'}, 'round': {'round'}, 'tip': {'tip', 'tri-tip'},
}
STOP = {'the', 'and', 'of', 'with', 'in', 'a', 'raw', 'fresh', 'frozen', 'cooked', 'for', 'or',
        'to', 'from', 'made', 'ns', 'as', 'type', 'regular', 'style', 'g', 'without', 'added',
        'salt', 'drained', 'boiled', 'dry', 'heat', 'canned', 'dried'}

def _toks(s):
    s = re.sub(r'\([^)]*\)', ' ', s.lower())
    s = re.sub(r'\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb|lbs)?\b', ' ', s)
    return re.findall(r"[a-z][a-z'-]*", s)

def _stem(w):
    for suf in ('ies', 'es', 's'):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w

def _parts(tokens):
    found = set()
    for t in tokens:
        for k, v in PARTS.items():
            if t in v:
                found.add(k)
    return found

def judging_function(ingredient, usda_match):
    try:
        ing = _toks(str(ingredient or ''))
        usda = _toks(str(usda_match or ''))
        if not ing or not usda:
            return 0.0
        ing_c = [_stem(t) for t in ing if t not in STOP]
        # primary food: first comma segment of usda
        first = re.sub(r'\([^)]*\)', ' ', str(usda_match).lower()).split(',')[0]
        prim = [_stem(t) for t in _toks(first) if t not in STOP]
        usda_c = [_stem(t) for t in usda if t not in STOP]
        if not ing_c or not usda_c:
            return 0.0
        # core food overlap: weighted by token rarity-ish (length)
        def w(t):
            return 1.0 + min(len(t), 10) / 10.0
        iset, uset, pset = set(ing_c), set(usda_c), set(prim)
        shared = iset & uset
        cov_i = sum(w(t) for t in shared) / sum(w(t) for t in iset)
        cov_u = sum(w(t) for t in (iset & pset)) / max(1e-9, sum(w(t) for t in pset)) if pset else 0
        # head noun of ingredient (last token) present in usda
        head = ing_c[-1]
        head_hit = 1.0 if head in uset else 0.0
        # partial char-prefix matches for variants
        fuzzy = 0
        for t in iset - shared:
            for u in uset - shared:
                if len(t) >= 4 and len(u) >= 4 and (t[:4] == u[:4]):
                    fuzzy += 0.5
                    break
        fuzzy = min(1.0, fuzzy / max(1, len(iset)))
        base = 5.0 * cov_i + 2.0 * cov_u + 1.5 * head_hit + 1.5 * fuzzy
        # anatomical part agreement
        ip, up = _parts(ing), _parts(usda)
        if ip and up:
            if ip & up:
                base += 2.5
            else:
                base -= 4.0
        elif ip and not up:
            base -= 1.0
        elif up and not ip:
            # usda names a specific part, ingredient doesn't
            if up & {'skin', 'seed', 'bran', 'germ', 'liver', 'heart', 'tongue', 'tail', 'bone', 'zest', 'juice', 'fat', 'white', 'yolk'}:
                base -= 2.0
            else:
                base -= 0.3
        # form changes: ground / whole
        if ('ground' in ip) != ('ground' in up) and (ip or up):
            base -= 1.0
        return max(0.0, min(10.0, base))
    except Exception:
        return 0.0
