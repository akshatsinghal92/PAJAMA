import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing_clean = ingredient.lower().strip()
        usda_clean = usda_match.lower().strip()

        # Remove gram weights (e.g., "200g", "30g")
        ing_clean = re.sub(r'^\d+g?\s*', '', ing_clean)

        # Remove parentheticals
        ing_clean = re.sub(r'\([^)]*\)', '', ing_clean)
        usda_clean = re.sub(r'\([^)]*\)', '', usda_clean)

        # Extract qualifiers and core words
        def extract_tokens(text):
            # Split on comma and clean
            parts = [p.strip() for p in text.split(',')]
            # Tokenize each part
            tokens = []
            for part in parts:
                tokens.extend(part.split())
            return tokens

        ing_tokens = extract_tokens(ing_clean)
        usda_tokens = extract_tokens(usda_clean)

        if not ing_tokens or not usda_tokens:
            return 0.0

        # Define state-changing qualifiers that signal incompatibility
        state_qualifiers = {
            'raw', 'cooked', 'frozen', 'fresh', 'canned', 'dried',
            'thawed', 'uncooked', 'roasted', 'baked', 'fried', 'boiled'
        }

        # Define form/texture qualifiers that are important
        form_qualifiers = {
            'diced', 'sliced', 'shredded', 'chopped', 'whole', 'ground',
            'crushed', 'minced', 'cubed', 'julienned', 'grated'
        }

        # Define preparation qualifiers
        prep_qualifiers = {
            'sauce', 'paste', 'juice', 'powder', 'flakes', 'extract',
            'puree', 'concentrate', 'oil'
        }

        # Extract qualifiers from ingredient
        ing_states = [t for t in ing_tokens if t in state_qualifiers]
        ing_forms = [t for t in ing_tokens if t in form_qualifiers]
        ing_preps = [t for t in ing_tokens if t in prep_qualifiers]

        # Extract qualifiers from USDA match
        usda_states = [t for t in usda_tokens if t in state_qualifiers]
        usda_forms = [t for t in usda_tokens if t in form_qualifiers]
        usda_preps = [t for t in usda_tokens if t in prep_qualifiers]

        # Core scoring logic
        score = 50.0  # Base score

        # 1. State alignment check (most critical)
        if ing_states and usda_states:
            # Both specify states - they must match
            if set(ing_states) == set(usda_states):
                score += 20
            else:
                # Conflicting states
                score -= 30
        elif ing_states and not usda_states:
            # Ingredient specifies state, USDA is generic - minor penalty
            score -= 10
        elif not ing_states and usda_states:
            # Ingredient is generic, USDA adds state - penalty
            score -= 25
        else:
            # Neither specifies state - neutral
            score += 10

        # 2. Form alignment check
        if ing_forms and usda_forms:
            # Both specify forms
            if set(ing_forms) == set(usda_forms):
                score += 15
            else:
                # Different forms specified
                score -= 20
        elif ing_forms and not usda_forms:
            # Ingredient has form, USDA generic - acceptable for some preps
            score -= 5
        elif not ing_forms and usda_forms:
            # Ingredient generic, USDA adds form - penalty
            score -= 15
        else:
            # Neither specifies form
            score += 5

        # 3. Preparation alignment check
        if ing_preps and usda_preps:
            # Both specify preparation
            if set(ing_preps) == set(usda_preps):
                score += 15
            else:
                # Different preparations
                score -= 25
        elif ing_preps and not usda_preps:
            # Ingredient specifies prep, USDA doesn't - major penalty
            score -= 30
        elif not ing_preps and usda_preps:
            # Ingredient generic, USDA adds prep - penalty
            score -= 15
        else:
            # Neither specifies prep
            score += 5

        # 4. Core word overlap (food item itself)
        ing_core = [t for t in ing_tokens if t not in state_qualifiers
                    and t not in form_qualifiers and t not in prep_qualifiers
                    and len(t) > 2]
        usda_core = [t for t in usda_tokens if t not in state_qualifiers
                     and t not in form_qualifiers and t not in prep_qualifiers
                     and len(t) > 2]

        if ing_core and usda_core:
            # Calculate Jaccard similarity on core words
            ing_set = set(ing_core)
            usda_set = set(usda_core)
            intersection = len(ing_set & usda_set)
            union = len(ing_set | usda_set)
            if union > 0:
                jaccard = intersection / union
                score += jaccard * 20
            else:
                score -= 20

        # 5. Penalize if USDA has significantly more qualifiers
        qualifier_count_ing = len(ing_states) + len(ing_forms) + len(ing_preps)
        qualifier_count_usda = len(usda_states) + len(usda_forms) + len(usda_preps)

        if qualifier_count_usda > qualifier_count_ing + 1:
            # USDA is over-specifying
            score -= 15

        # 6. Bonus for very close matches
        ing_key_words = set(ing_tokens[:3])  # First 3 words
        usda_key_words = set(usda_tokens[:3])
        if ing_key_words == usda_key_words:
            score += 15

        # Clamp score to 0-100 range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 25.0
