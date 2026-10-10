import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize strings
        ing = ingredient.lower().strip()
        usda = usda_match.lower().strip()

        # Remove gram weights (e.g., "200g", "30g")
        ing = re.sub(r'\b\d+g\b', '', ing)

        # Noise words to remove
        noise = {
            'diced', 'chopped', 'sliced', 'minced', 'shredded', 'grated',
            'crushed', 'ground', 'whole', 'to', 'taste', 'from', 'tube',
            'fresh', 'frozen', 'dried', 'canned', 'raw', 'cooked',
            'the', 'a', 'an', 'of', 'with', 'without', 'and', 'or'
        }

        # State markers (important for matching)
        state_markers = {
            'raw', 'cooked', 'frozen', 'fresh', 'canned', 'dried',
            'thawed', 'drained', 'uncooked', 'roasted', 'baked'
        }

        # Extract tokens from ingredient (before comma, remove parentheticals)
        ing_main = ing.split(',')[0]
        ing_main = re.sub(r'\([^)]*\)', '', ing_main)
        ing_tokens = re.findall(r'\b[a-z]+\b', ing_main)
        ing_tokens = [t for t in ing_tokens if len(t) > 1]

        # Extract state words from ingredient
        ing_states = {t for t in ing_tokens if t in state_markers}

        # Remove noise but keep state markers for now
        ing_core = [t for t in ing_tokens if t not in noise or t in state_markers]

        # Extract tokens from USDA
        usda_tokens = re.findall(r'\b[a-z]+\b', usda)
        usda_tokens = [t for t in usda_tokens if len(t) > 1]

        # Extract state words from USDA
        usda_states = {t for t in usda_tokens if t in state_markers}

        # Remove noise from USDA
        usda_core = [t for t in usda_tokens if t not in noise or t in state_markers]

        if not ing_core or not usda_core:
            return 0.0

        # Convert to sets for overlap calculation
        ing_set = set(ing_core)
        usda_set = set(usda_core)

        # Calculate bidirectional coverage
        overlap = ing_set & usda_set
        ing_coverage = len(overlap) / len(ing_set)
        usda_coverage = len(overlap) / len(usda_set)

        # Base score: harmonic mean of bidirectional coverage
        if ing_coverage + usda_coverage == 0:
            base_score = 0.0
        else:
            base_score = 2 * (ing_coverage * usda_coverage) / (ing_coverage + usda_coverage)

        # Convert to 0-100 scale
        score = base_score * 100

        # Penalty 1: State mismatch
        # If ingredient has state markers that don't match USDA states
        state_penalty = 0
        if ing_states and usda_states:
            # Check for conflicting states
            conflicting_states = [
                ({'raw', 'uncooked'}, {'cooked', 'roasted', 'baked'}),
                ({'frozen'}, {'fresh', 'thawed'}),
                ({'drained'}, {'cooked'})
            ]
            for group1, group2 in conflicting_states:
                if (ing_states & group1) and (usda_states & group2):
                    state_penalty = 30
                    break
                elif (ing_states & group2) and (usda_states & group1):
                    state_penalty = 30
                    break

        # Penalty 2: USDA has extra modifiers not in ingredient
        usda_extra = usda_set - ing_set - state_markers
        extra_penalty = len(usda_extra) * 8

        # Penalty 3: Ingredient has specificity that USDA lacks
        # Check for multi-word phrases in ingredient
        ing_bigrams = []
        for i in range(len(ing_core) - 1):
            ing_bigrams.append(ing_core[i] + ' ' + ing_core[i+1])

        usda_text = ' '.join(usda_core)
        specificity_penalty = 0
        for bigram in ing_bigrams:
            if bigram not in usda_text:
                specificity_penalty += 10

        # Bonus 1: Exact phrase match
        phrase_bonus = 0
        if len(ing_core) >= 2:
            ing_phrase = ' '.join(ing_core[:3])
            if ing_phrase in ' '.join(usda_core):
                phrase_bonus = 20

        # Bonus 2: Token order preservation
        order_bonus = 0
        if len(ing_core) >= 2 and len(usda_core) >= 2:
            # Check if first 2 tokens of ingredient appear in same order in USDA
            ing_first_two = ing_core[:2]
            usda_str = ' '.join(usda_core)
            search_pattern = r'\b' + ing_first_two[0] + r'\b.*\b' + ing_first_two[1] + r'\b'
            if re.search(search_pattern, usda_str):
                order_bonus = 15

        # Calculate final score
        final_score = score - state_penalty - extra_penalty - specificity_penalty + phrase_bonus + order_bonus

        # Clamp to 0-100 range
        final_score = max(0.0, min(100.0, final_score))

        return round(final_score, 2)

    except Exception:
        return 0.0
