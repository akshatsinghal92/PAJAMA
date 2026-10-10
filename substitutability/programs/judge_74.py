import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        ing_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Remove gram weights
        ing_lower = re.sub(r'^\d+g?\s*', '', ing_lower)

        # Define qualifier categories that matter for substitutability
        qualifier_groups = {
            'preparation_state': [
                'raw', 'cooked', 'boiled', 'fried', 'baked', 'grilled', 'roasted',
                'steamed', 'sauteed', 'blanched', 'frozen', 'fresh', 'canned',
                'dried', 'dehydrated', 'smoked', 'pickled', 'fermented', 'thawed'
            ],
            'form_cut': [
                'diced', 'chopped', 'minced', 'sliced', 'shredded', 'grated',
                'whole', 'halved', 'quartered', 'crushed', 'ground', 'cubed',
                'julienned', 'pureed', 'mashed', 'crumbled', 'flaked', 'chunks'
            ],
            'color_variety': [
                'red', 'green', 'yellow', 'white', 'black', 'brown', 'orange',
                'purple', 'pink', 'blue', 'golden'
            ],
            'fat_content': [
                'whole', 'skim', 'low-fat', 'non-fat', 'reduced-fat', 'fat-free',
                '2%', '1%', 'full-fat', 'lean', 'extra-lean'
            ],
            'part': [
                'breast', 'thigh', 'leg', 'wing', 'drumstick', 'tenderloin',
                'loin', 'rib', 'shoulder', 'chuck', 'round', 'flank',
                'leaf', 'stem', 'root', 'bulb', 'seed', 'peel', 'skin',
                'fillet', 'steak', 'chop'
            ],
            'size': [
                'large', 'small', 'medium', 'baby', 'jumbo', 'mini', 'giant'
            ],
            'liquid_state': [
                'drained', 'with liquid', 'in water', 'in oil', 'in juice',
                'in syrup', 'with brine', 'sauce'
            ],
            'sweetness': [
                'sweet', 'unsweetened', 'sweetened', 'sugar-free', 'no sugar added'
            ],
            'salt': [
                'salted', 'unsalted', 'low-sodium', 'no salt added', 'salt-free'
            ]
        }

        # Extract qualifiers from both strings
        def extract_qualifiers(text):
            found = defaultdict(set)
            for category, qualifiers in qualifier_groups.items():
                for q in qualifiers:
                    # Use word boundaries to avoid partial matches
                    pattern = r'\b' + re.escape(q) + r'\b'
                    if re.search(pattern, text):
                        found[category].add(q)
            return found

        ing_quals = extract_qualifiers(ing_lower)
        usda_quals = extract_qualifiers(usda_lower)

        # Start with a base score
        score = 75.0

        # Check each category for conflicts
        conflict_penalties = {
            'preparation_state': 30,
            'form_cut': 20,
            'liquid_state': 25,
            'part': 25,
            'color_variety': 20,
            'fat_content': 20,
            'size': 10,
            'sweetness': 15,
            'salt': 15
        }

        # Bonus for matching qualifiers
        match_bonus = {
            'preparation_state': 5,
            'form_cut': 3,
            'liquid_state': 5,
            'part': 4,
            'color_variety': 4,
            'fat_content': 4,
            'size': 2,
            'sweetness': 3,
            'salt': 3
        }

        for category in qualifier_groups.keys():
            ing_set = ing_quals.get(category, set())
            usda_set = usda_quals.get(category, set())

            if ing_set and usda_set:
                # Both have qualifiers in this category
                if ing_set & usda_set:
                    # They overlap - good!
                    score += match_bonus.get(category, 2)
                else:
                    # They conflict - bad!
                    score -= conflict_penalties.get(category, 15)
            elif ing_set and not usda_set:
                # Ingredient specifies but USDA doesn't - mild penalty
                score -= conflict_penalties.get(category, 15) * 0.3
            elif usda_set and not ing_set:
                # USDA specifies but ingredient doesn't - neutral to slight bonus
                score += 2

        # Special case: check for contradictory preparation methods
        prep_conflicts = [
            (['raw', 'fresh', 'uncooked'], ['cooked', 'baked', 'fried', 'boiled', 'grilled']),
            (['drained'], ['with liquid', 'in water', 'in oil', 'in juice']),
            (['frozen'], ['fresh', 'thawed']),
            (['whole'], ['diced', 'chopped', 'minced', 'sliced', 'shredded'])
        ]

        for group1, group2 in prep_conflicts:
            has_g1_ing = any(q in ing_lower for q in group1)
            has_g2_ing = any(q in ing_lower for q in group2)
            has_g1_usda = any(q in usda_lower for q in group1)
            has_g2_usda = any(q in usda_lower for q in group2)

            if (has_g1_ing and has_g2_usda) or (has_g2_ing and has_g1_usda):
                score -= 25

        # Normalize score to 0-100 range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 50.0
