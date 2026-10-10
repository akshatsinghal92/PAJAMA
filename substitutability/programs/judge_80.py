import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        # Clean and normalize inputs
        ing_clean = re.sub(r'^\d+g?\s*', '', str(ingredient).lower().strip())
        usda_clean = str(usda_match).lower().strip()

        # Define qualifier categories with keywords
        qualifiers = {
            'color': ['red', 'green', 'yellow', 'white', 'black', 'brown', 'orange', 'purple', 'pink', 'golden', 'dark', 'light'],
            'cut': ['diced', 'chopped', 'sliced', 'shredded', 'minced', 'whole', 'crushed', 'ground', 'cubed', 'julienned', 'quartered', 'halved'],
            'state': ['raw', 'cooked', 'frozen', 'fresh', 'dried', 'canned', 'thawed', 'roasted', 'baked', 'fried', 'steamed', 'boiled', 'grilled'],
            'fat_level': ['skim', 'low-fat', 'reduced-fat', 'whole', 'full-fat', 'fat-free', 'lean', 'extra-lean'],
            'part': ['breast', 'thigh', 'leg', 'wing', 'drumstick', 'fillet', 'steak', 'chop', 'rib', 'loin', 'shoulder', 'neck', 'tail'],
            'variety': ['cherry', 'grape', 'roma', 'plum', 'bell', 'jalapeño', 'sweet', 'hot', 'spicy', 'mild'],
            'form': ['paste', 'sauce', 'oil', 'powder', 'puree', 'concentrate', 'juice', 'cream', 'butter', 'spread'],
            'prep_detail': ['drained', 'rinsed', 'peeled', 'seeded', 'with oil', 'in water', 'in juice', 'skinless', 'boneless', 'with skin', 'with bone']
        }

        # Extract qualifiers from both strings
        ing_qualifiers = defaultdict(set)
        usda_qualifiers = defaultdict(set)

        for category, keywords in qualifiers.items():
            for keyword in keywords:
                # Check for whole word matches
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, ing_clean):
                    ing_qualifiers[category].add(keyword)
                if re.search(pattern, usda_clean):
                    usda_qualifiers[category].add(keyword)

        # Start with a base score
        score = 100.0

        # Penalty weights for different categories (more discriminating = higher penalty)
        penalties = {
            'color': 25.0,
            'variety': 25.0,
            'cut': 20.0,
            'fat_level': 20.0,
            'part': 25.0,
            'state': 30.0,
            'form': 30.0,
            'prep_detail': 25.0
        }

        # Check each category for conflicts
        for category in qualifiers.keys():
            ing_set = ing_qualifiers[category]
            usda_set = usda_qualifiers[category]

            if not ing_set and not usda_set:
                # Neither specifies this qualifier - neutral
                continue
            elif not ing_set and usda_set:
                # Ingredient unspecified, USDA specified - minor bonus for specificity
                score += 2.0
            elif ing_set and not usda_set:
                # Ingredient specified, USDA unspecified - generally OK (USDA might be generic)
                score += 1.0
            elif ing_set and usda_set:
                # Both specified - check for matches
                intersection = ing_set & usda_set
                if intersection:
                    # Perfect match on this qualifier
                    score += 10.0
                else:
                    # Contradiction - apply penalty
                    score -= penalties.get(category, 20.0)

        # Bonus for exact substring containment (strong signal of match)
        core_ing = re.sub(r'\s*\(.*?\)\s*', '', ing_clean)  # Remove parentheticals
        core_ing = re.sub(r',.*', '', core_ing).strip()  # Remove post-comma
        core_usda = re.sub(r',.*', '', usda_clean).strip()  # Get primary food from USDA

        # Extract main ingredient word (longest word or last word before comma)
        ing_words = core_ing.split()
        usda_words = core_usda.split()

        if ing_words and usda_words:
            # Check if core words overlap
            ing_core_words = set([w for w in ing_words if len(w) > 3])
            usda_core_words = set([w for w in usda_words if len(w) > 3])
            overlap = ing_core_words & usda_core_words
            if overlap:
                score += 15.0 * len(overlap)

        # Penalize state mismatches specifically (very important)
        state_conflicts = [
            (['raw'], ['cooked', 'baked', 'fried', 'roasted']),
            (['frozen'], ['fresh', 'thawed']),
            (['dried'], ['fresh', 'canned']),
            (['canned'], ['fresh', 'dried'])
        ]

        for ing_states, usda_states in state_conflicts:
            if any(s in ing_qualifiers['state'] for s in ing_states):
                if any(s in usda_qualifiers['state'] for s in usda_states):
                    score -= 35.0

        # Normalize score to reasonable range
        score = max(0.0, min(150.0, score))

        return score

    except Exception:
        return 50.0
