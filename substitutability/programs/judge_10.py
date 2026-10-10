import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ing_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Remove gram weights like "300g", "40g "
        ing_clean = re.sub(r'^\d+g\s*', '', ing_lower).strip()

        # Extract parentheticals and post-comma context
        ing_main = re.sub(r'\([^)]*\)', '', ing_clean)
        ing_parts = [p.strip() for p in ing_main.split(',')]

        usda_parts = [p.strip() for p in usda_lower.split(',')]

        # Preparation states
        trivial_prep = {
            'chopped', 'diced', 'minced', 'sliced', 'shredded', 'grated',
            'cubed', 'julienned', 'thawed', 'peeled', 'trimmed', 'halved',
            'quartered', 'crushed', 'whole', 'cut'
        }

        significant_cooking = {
            'cooked', 'fried', 'baked', 'roasted', 'grilled', 'boiled',
            'steamed', 'sauteed', 'braised', 'stewed', 'toasted', 'pan-fried'
        }

        raw_state = {'raw', 'fresh', 'uncooked'}

        additions = {
            'with oil', 'with salt', 'with butter', 'seasoned', 'marinated',
            'in sauce', 'in brine', 'in syrup', 'sweetened', 'salted',
            'unsalted', 'flavored'
        }

        storage_forms = {'canned', 'frozen', 'dried', 'pickled', 'jarred'}

        # Extract words from both
        ing_words = set(re.findall(r'\b\w+\b', ing_clean))
        usda_words = set(re.findall(r'\b\w+\b', usda_lower))

        # Check for multi-word additions
        def has_addition(text, additions_set):
            for addition in additions_set:
                if addition in text:
                    return True
            return False

        ing_has_addition = has_addition(ing_clean, additions)
        usda_has_addition = has_addition(usda_lower, additions)

        # Classify states
        ing_trivial = ing_words & trivial_prep
        ing_cooked = ing_words & significant_cooking
        ing_raw = ing_words & raw_state
        ing_storage = ing_words & storage_forms

        usda_trivial = usda_words & trivial_prep
        usda_cooked = usda_words & significant_cooking
        usda_raw = usda_words & raw_state
        usda_storage = usda_words & storage_forms

        # Base food overlap (non-state words)
        all_state_words = trivial_prep | significant_cooking | raw_state | storage_forms
        ing_content = ing_words - all_state_words - {'g', 'ml', 'kg', 'oz', 'lb'}
        usda_content = usda_words - all_state_words - {'g', 'ml', 'kg', 'oz', 'lb'}

        # Common food words
        common_content = ing_content & usda_content
        content_overlap_ratio = len(common_content) / max(len(ing_content), 1)

        # Start with base score from content overlap
        score = content_overlap_ratio * 50

        # MAIN EVALUATION: Preparation-state equivalence

        # Case 1: Both are raw or both have trivial prep only
        ing_is_raw_or_trivial = (ing_raw or ing_trivial) and not ing_cooked
        usda_is_raw_or_trivial = (usda_raw or usda_trivial) and not usda_cooked

        if ing_is_raw_or_trivial and usda_is_raw_or_trivial:
            # Good match - trivial prep differences are OK
            score += 40

        # Case 2: Cooking state mismatch (critical penalty)
        cooking_mismatch = (ing_cooked and not usda_cooked) or (not ing_cooked and usda_cooked)

        if cooking_mismatch:
            # One is cooked, other is not - major penalty
            score -= 45

        # Case 3: Both cooked - need same cooking method roughly
        if ing_cooked and usda_cooked:
            # Check if cooking methods align
            if ing_cooked & usda_cooked:
                score += 30  # Same cooking method
            else:
                score += 10  # Different cooking but both cooked

        # Case 4: Addition mismatch (e.g., "with oil", "drained")
        if ing_has_addition != usda_has_addition:
            score -= 35

        # Case 5: Storage form must match if specified in ingredient
        if ing_storage and usda_storage:
            if ing_storage & usda_storage:
                score += 15  # Same storage form
            else:
                score -= 25  # Different storage forms
        elif ing_storage and not usda_storage:
            score -= 20
        elif not ing_storage and usda_storage:
            score -= 15

        # Case 6: Check for form mismatches (sauce vs base, paste vs whole)
        form_words = {'sauce', 'paste', 'powder', 'juice', 'oil', 'puree', 'concentrate'}
        ing_form = ing_words & form_words
        usda_form = usda_words & form_words

        if ing_form != usda_form:
            score -= 30  # Form mismatch is significant

        # Case 7: "drained" handling - critical for canned goods
        if 'drained' in ing_words and 'drained' not in usda_words:
            # Ingredient is drained but USDA might have liquid/oil
            if usda_has_addition:
                score -= 40  # Bad: drained ingredient vs with-additions USDA

        # Case 8: Bonus for exact trivial prep match
        if ing_trivial and usda_trivial and ing_trivial == usda_trivial:
            score += 10

        # Normalize to 0-100 range
        score = max(0, min(100, score))

        return float(score)

    except Exception:
        return 5.0
