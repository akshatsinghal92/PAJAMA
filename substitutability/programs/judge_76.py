import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ing = ingredient.lower().strip()
        usda = usda_match.lower().strip()

        # Remove gram weights from ingredient (e.g., "300g ")
        ing = re.sub(r'^\d+g?\s+', '', ing)

        # Define discriminating qualifier categories
        qualifier_patterns = {
            'color': ['red', 'green', 'yellow', 'white', 'black', 'brown', 'orange', 'purple', 'pink', 'golden'],
            'fat_level': ['whole', 'skim', 'low-fat', 'fat-free', 'reduced-fat', 'nonfat', '2%', '1%', 'full-fat', 'lean'],
            'cut_form': ['diced', 'sliced', 'chopped', 'minced', 'shredded', 'whole', 'halved', 'quartered',
                         'crushed', 'ground', 'cubed', 'julienned', 'grated'],
            'variety': ['cherry', 'roma', 'beefsteak', 'plum', 'grape', 'heirloom', 'bell', 'sweet', 'hot',
                       'spicy', 'mild', 'penne', 'spaghetti', 'fusilli', 'farfalle'],
            'animal_part': ['breast', 'thigh', 'wing', 'leg', 'drumstick', 'tender', 'fillet', 'steak',
                           'roast', 'chop', 'loin', 'shoulder', 'rib'],
            'preparation_state': ['raw', 'cooked', 'frozen', 'fresh', 'canned', 'dried', 'roasted',
                                 'boiled', 'fried', 'baked', 'grilled', 'steamed'],
            'liquid_modifier': ['drained', 'rinsed', 'with oil', 'in water', 'in juice', 'in syrup',
                               'in brine', 'with liquid'],
            'product_form': ['sauce', 'paste', 'powder', 'flakes', 'liquid', 'puree', 'juice', 'extract', 'oil'],
            'sweetness': ['sweetened', 'unsweetened', 'sweet', 'bitter', 'sour', 'tart'],
            'salt_level': ['salted', 'unsalted', 'low-sodium', 'no-salt', 'sea salt', 'table']
        }

        # Extract qualifiers from both strings
        ing_quals = defaultdict(set)
        usda_quals = defaultdict(set)

        for category, keywords in qualifier_patterns.items():
            for keyword in keywords:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, ing):
                    ing_quals[category].add(keyword)
                if re.search(pattern, usda):
                    usda_quals[category].add(keyword)

        # Compute match/conflict/unspecified counts
        matches = 0
        conflicts = 0
        ing_unspecified = 0
        usda_unspecified = 0

        all_categories = set(qualifier_patterns.keys())

        for category in all_categories:
            ing_set = ing_quals[category]
            usda_set = usda_quals[category]

            if ing_set and usda_set:
                # Both have qualifiers in this category
                if ing_set & usda_set:  # They match
                    matches += len(ing_set & usda_set)
                else:  # They conflict
                    conflicts += 1
            elif ing_set and not usda_set:
                # Ingredient specifies, USDA doesn't
                ing_unspecified += 1
            elif usda_set and not ing_set:
                # USDA specifies, ingredient doesn't
                usda_unspecified += 1

        # Variant 4/8: Ratio-based scoring with weighted penalties
        # Base score from match ratio
        total_specified = matches + conflicts + ing_unspecified

        if total_specified == 0:
            # No qualifiers found - assume neutral match
            base_score = 60.0
        else:
            # Match ratio component
            match_ratio = matches / total_specified if total_specified > 0 else 0
            base_score = match_ratio * 80.0

        # Heavy penalty for conflicts (these are deal-breakers for substitutability)
        conflict_penalty = conflicts * 30.0

        # Light penalty for ingredient-specified qualifiers missing in USDA
        ing_unspec_penalty = ing_unspecified * 3.0

        # Slight bonus for USDA having extra qualifiers (more specific is ok)
        usda_bonus = usda_unspecified * 1.0

        # Final score calculation
        score = base_score - conflict_penalty - ing_unspec_penalty + usda_bonus

        # Bonus if core food words match
        ing_words = set(re.findall(r'\b\w{4,}\b', ing))
        usda_words = set(re.findall(r'\b\w{4,}\b', usda))
        common_words = ing_words & usda_words
        if common_words:
            score += len(common_words) * 2.0

        # Clamp to 0-100 range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 25.0
