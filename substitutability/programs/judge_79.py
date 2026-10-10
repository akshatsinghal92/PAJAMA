import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 5.0

        # Normalize inputs
        ing = ingredient.lower().strip()
        usda = usda_match.lower().strip()

        # Remove gram weights like "200g", "30g"
        ing = re.sub(r'^\d+g?\s*', '', ing)
        usda = re.sub(r'^\d+g?\s*', '', usda)

        # Define discriminating qualifier categories
        qualifiers = {
            'color': ['red', 'green', 'yellow', 'white', 'black', 'brown', 'orange', 'purple', 'pink'],
            'cut_form': ['whole', 'diced', 'sliced', 'shredded', 'ground', 'minced', 'chopped',
                         'crushed', 'cubed', 'julienned', 'grated', 'halved', 'quartered'],
            'fat_level': ['skim', 'low-fat', 'whole', 'full-fat', 'lean', 'extra-lean', 'fat-free',
                          'reduced-fat', '2%', '1%', 'nonfat'],
            'prep_state': ['raw', 'cooked', 'frozen', 'canned', 'fresh', 'dried', 'roasted',
                           'boiled', 'fried', 'baked', 'steamed', 'grilled', 'thawed', 'uncooked'],
            'animal_part': ['breast', 'thigh', 'leg', 'drumstick', 'wing', 'fillet', 'loin',
                            'shoulder', 'rib', 'tenderloin', 'cutlet'],
            'variety': ['cherry', 'roma', 'beefsteak', 'grape', 'plum', 'bell', 'jalapeño',
                        'serrano', 'poblano', 'russet', 'yukon', 'sweet', 'red delicious',
                        'granny smith'],
            'sweetness': ['sweet', 'unsweetened', 'sugar-free', 'sweetened', 'no-sugar-added'],
            'texture_form': ['sauce', 'paste', 'oil', 'juice', 'puree', 'concentrate', 'liquid',
                             'solid', 'powder', 'flakes', 'chunks'],
            'container_prep': ['drained', 'with oil', 'in water', 'in syrup', 'in juice',
                               'with liquid', 'packed in']
        }

        # Extract qualifiers from both strings
        ing_qualifiers = defaultdict(set)
        usda_qualifiers = defaultdict(set)

        for category, terms in qualifiers.items():
            for term in terms:
                if term in ing:
                    ing_qualifiers[category].add(term)
                if term in usda:
                    usda_qualifiers[category].add(term)

        # Calculate scores for each category
        base_score = 5.0
        total_score = base_score

        all_categories = set(ing_qualifiers.keys()) | set(usda_qualifiers.keys())

        for category in all_categories:
            ing_set = ing_qualifiers.get(category, set())
            usda_set = usda_qualifiers.get(category, set())

            if not ing_set and not usda_set:
                # No qualifiers in this category for either
                continue
            elif not ing_set or not usda_set:
                # One has qualifiers, other doesn't - unspecified (neutral)
                continue
            else:
                # Both have qualifiers - check for matches and contradictions
                intersection = ing_set & usda_set
                ing_only = ing_set - usda_set
                usda_only = usda_set - ing_set

                if intersection:
                    # Matched qualifiers - positive signal
                    total_score += 2.0 * len(intersection)

                if ing_only and usda_only:
                    # Both have different qualifiers in same category - contradiction
                    # This is a strong signal of non-substitutability
                    total_score -= 4.0 * max(len(ing_only), len(usda_only))

        # Additional heuristic: check for key contradictory pairs
        contradictions = [
            ('raw', 'cooked'),
            ('frozen', 'fresh'),
            ('canned', 'fresh'),
            ('sauce', 'paste'),
            ('drained', 'with oil'),
            ('drained', 'in syrup'),
            ('whole', 'ground'),
            ('whole', 'diced'),
            ('breast', 'thigh'),
            ('skim', 'whole'),
            ('sweet', 'unsweetened')
        ]

        for term1, term2 in contradictions:
            if (term1 in ing and term2 in usda) or (term2 in ing and term1 in usda):
                total_score -= 2.5

        # Bonus: if main food terms match closely
        ing_words = set(re.findall(r'\b[a-z]{3,}\b', ing))
        usda_words = set(re.findall(r'\b[a-z]{3,}\b', usda))

        # Common words to ignore
        stopwords = {'with', 'and', 'the', 'from', 'for', 'tube'}
        ing_words -= stopwords
        usda_words -= stopwords

        if ing_words and usda_words:
            overlap = len(ing_words & usda_words)
            if overlap >= 2:
                total_score += 1.0

        # Clamp score to 0-10 range
        return max(0.0, min(10.0, total_score))

    except Exception:
        return 5.0
