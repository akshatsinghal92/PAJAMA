import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ing = ingredient.strip().lower()
        usda = usda_match.strip().lower()

        # Remove gram weight prefix
        ing = re.sub(r'^\d+g\s+', '', ing)

        # Remove parentheticals from ingredient
        ing = re.sub(r'\([^)]*\)', '', ing).strip()

        # Extract tokens as features
        def tokenize(text):
            # Split on common delimiters and filter
            tokens = re.findall(r'\b[a-z]+\b', text)
            return [t for t in tokens if len(t) > 1]

        ing_tokens = set(tokenize(ing))
        usda_tokens = set(tokenize(usda))

        # Identify critical qualifier categories
        state_markers = {'raw', 'cooked', 'frozen', 'canned', 'fresh', 'dried', 'thawed'}
        form_markers = {'diced', 'whole', 'shredded', 'ground', 'sliced', 'chopped', 'paste', 'sauce', 'crushed'}
        prep_markers = {'drained', 'oil', 'salted', 'unsalted', 'with', 'without'}

        ing_states = ing_tokens & state_markers
        usda_states = usda_tokens & state_markers

        ing_forms = ing_tokens & form_markers
        usda_forms = usda_tokens & form_markers

        ing_preps = ing_tokens & prep_markers
        usda_preps = usda_tokens & prep_markers

        # Base score starts at 60
        score = 60.0

        # Core ingredient overlap (main food item)
        core_overlap = len(ing_tokens & usda_tokens)
        if core_overlap == 0:
            return 0.0
        score += core_overlap * 3.0

        # Count total qualifiers in each
        ing_qualifier_count = len(ing_states) + len(ing_forms) + len(ing_preps)
        usda_qualifier_count = len(usda_states) + len(usda_forms) + len(usda_preps)

        # SPECIFICITY ALIGNMENT LOGIC
        if ing_qualifier_count == 0:
            # Ingredient is unqualified/generic
            if usda_qualifier_count == 0:
                # Both generic - perfect alignment
                score += 25.0
            elif usda_qualifier_count == 1:
                # USDA adds one common qualifier (e.g., "table" for salt) - acceptable
                score += 10.0
            else:
                # USDA is too specific for generic ingredient
                score -= usda_qualifier_count * 8.0
        else:
            # Ingredient has qualifiers - must check alignment

            # State alignment
            if ing_states:
                if usda_states == ing_states:
                    score += 20.0
                elif usda_states and not (usda_states & ing_states):
                    # Conflicting states (e.g., raw vs cooked)
                    score -= 45.0
                elif not usda_states:
                    # Ingredient specifies state, USDA doesn't
                    score -= 15.0
            else:
                if usda_states:
                    # USDA adds state ingredient didn't mention
                    score -= 20.0

            # Form alignment
            if ing_forms:
                if usda_forms == ing_forms:
                    score += 15.0
                elif usda_forms and not (usda_forms & ing_forms):
                    # Conflicting forms (e.g., sauce vs paste)
                    score -= 35.0
                elif not usda_forms:
                    # Ingredient specifies form, USDA is missing it
                    score -= 20.0
            else:
                if usda_forms:
                    # USDA adds form ingredient didn't specify
                    score -= 12.0

            # Preparation alignment
            if ing_preps:
                if 'drained' in ing_tokens and 'oil' in usda_tokens:
                    # Critical mismatch: drained but USDA has oil
                    score -= 40.0
                elif usda_preps & ing_preps:
                    score += 10.0
                elif usda_preps - ing_preps:
                    # USDA adds prep details not in ingredient
                    score -= 15.0 * len(usda_preps - ing_preps)
            else:
                if usda_preps:
                    # USDA adds prep qualifiers
                    score -= 10.0

        # Penalize if USDA has many more tokens (over-specified)
        token_diff = len(usda_tokens) - len(ing_tokens)
        if token_diff > 2:
            score -= (token_diff - 2) * 5.0

        # Normalize to 0-100
        return max(0.0, min(100.0, score))

    except Exception:
        return 20.0
