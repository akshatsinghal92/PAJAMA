import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        # Normalize strings
        ing_lower = ingredient.lower().strip()
        usda_lower = usda_match.lower().strip()

        # Remove gram weights
        ing_lower = re.sub(r'^\d+g\s+', '', ing_lower)

        # Tokenize into words
        ing_tokens = set(re.findall(r'\b[a-z]+\b', ing_lower))
        usda_tokens = set(re.findall(r'\b[a-z]+\b', usda_lower))

        # Define mutually exclusive qualifier groups with penalty weights
        qualifier_groups = [
            # Preparation state (high impact)
            ({'raw', 'uncooked', 'fresh'}, {'cooked', 'baked', 'fried', 'roasted', 'grilled', 'boiled'}, 30),

            # Processing state (high impact)
            ({'drained'}, {'with', 'in', 'packed'}, 25),

            # Fat content (medium-high impact)
            ({'whole', 'full'}, {'skim', 'nonfat', 'lowfat', 'reduced'}, 20),
            ({'lean'}, {'fatty', 'regular'}, 18),

            # Texture/form (medium-high impact)
            ({'diced', 'chopped', 'minced', 'sliced', 'shredded', 'grated'}, {'whole', 'halved', 'quartered'}, 22),

            # Sweetness (medium impact)
            ({'sweet', 'sweetened'}, {'unsweetened', 'plain'}, 15),

            # Color/variety (medium impact)
            ({'red', 'green', 'yellow', 'white', 'black', 'brown'}, {'red', 'green', 'yellow', 'white', 'black', 'brown'}, 15),

            # Animal parts (medium impact)
            ({'breast', 'thigh', 'wing', 'leg', 'drumstick'}, {'breast', 'thigh', 'wing', 'leg', 'drumstick'}, 18),

            # Storage state (medium impact)
            ({'frozen', 'refrigerated'}, {'canned', 'jarred', 'bottled'}, 15),
            ({'frozen'}, {'thawed', 'fresh'}, 12),

            # Concentration (lower impact)
            ({'paste', 'sauce', 'puree'}, {'whole', 'chunk', 'piece'}, 20),

            # Plant parts (lower impact)
            ({'leaf', 'leaves', 'stem', 'root', 'seed', 'fruit'}, {'leaf', 'leaves', 'stem', 'root', 'seed', 'fruit'}, 12),
        ]

        base_score = 100.0
        total_penalty = 0.0

        # Check each qualifier group for contradictions
        for group_a, group_b, penalty_weight in qualifier_groups:
            ing_has_a = bool(ing_tokens & group_a)
            ing_has_b = bool(ing_tokens & group_b)
            usda_has_a = bool(usda_tokens & group_a)
            usda_has_b = bool(usda_tokens & group_b)

            # Contradiction: ingredient has qualifier from one set, USDA has from opposite set
            if (ing_has_a and usda_has_b) or (ing_has_b and usda_has_a):
                total_penalty += penalty_weight

            # Special check: same color group needs exact match
            if group_a == group_b:  # color group
                ing_colors = ing_tokens & group_a
                usda_colors = usda_tokens & group_a
                if ing_colors and usda_colors and ing_colors != usda_colors:
                    total_penalty += penalty_weight

        # Bonus for matching discriminating qualifiers
        discriminating_qualifiers = {
            'organic', 'wild', 'grass', 'fed', 'bone', 'skin', 'seedless',
            'pitted', 'peeled', 'trimmed', 'boneless', 'skinless'
        }

        ing_disc = ing_tokens & discriminating_qualifiers
        usda_disc = usda_tokens & discriminating_qualifiers

        if ing_disc and usda_disc:
            matches = ing_disc & usda_disc
            bonus = len(matches) * 5.0
            base_score += bonus

        # Apply penalties
        final_score = base_score - total_penalty

        # Clamp to 0-100 range
        final_score = max(0.0, min(100.0, final_score))

        return final_score

    except Exception:
        return 50.0
