import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        if not ingredient or not usda_match:
            return 0.0

        # Remove gram weights from ingredient (e.g., "200g ")
        ingredient_clean = re.sub(r'^\d+g?\s*', '', ingredient)

        # Extract core ingredient (before comma, without parentheticals)
        ing_core = re.sub(r'\([^)]*\)', '', ingredient_clean).split(',')[0].strip()

        # Start with base score
        score = 100.0

        # Extract key state/form/prep keywords
        state_words_ing = extract_state_words(ingredient_clean)
        state_words_usda = extract_state_words(usda_match)

        # Check for cooking state mismatches
        ing_cooking_state = get_cooking_state(state_words_ing)
        usda_cooking_state = get_cooking_state(state_words_usda)

        if ing_cooking_state and usda_cooking_state:
            if ing_cooking_state != usda_cooking_state:
                # Raw vs cooked mismatch is severe
                score -= 60.0

        # Check for form/texture conflicts
        ing_form = get_form_descriptor(state_words_ing)
        usda_form = get_form_descriptor(state_words_usda)

        if ing_form and usda_form:
            if ing_form != usda_form:
                # Different forms affect culinary role
                score -= 40.0
        elif ing_form and not usda_form:
            # Ingredient specifies form but USDA doesn't - potential mismatch
            score -= 20.0

        # Check for preparation level mismatches
        ing_prep = get_prep_level(ingredient_clean)
        usda_prep = get_prep_level(usda_match)

        if ing_prep != usda_prep:
            # Sauce vs raw, paste vs whole, etc.
            score -= 45.0

        # Check for additive conflicts (with oil, with salt, etc.)
        ing_additives = extract_additives(ingredient_clean)
        usda_additives = extract_additives(usda_match)

        # Ingredient says "drained" but USDA has "with oil/liquid"
        if 'drained' in ingredient_clean and usda_additives:
            score -= 50.0

        # USDA has additives not in ingredient
        additive_diff = usda_additives - ing_additives
        if additive_diff:
            score -= 35.0 * len(additive_diff)

        # Check core food similarity
        ing_tokens = set(re.findall(r'\b\w+\b', ing_core))
        usda_tokens = set(re.findall(r'\b\w+\b', usda_match))

        # Remove common non-food words
        stop_words = {'the', 'and', 'or', 'with', 'from', 'a', 'an'}
        ing_tokens -= stop_words
        usda_tokens -= stop_words

        if ing_tokens and usda_tokens:
            overlap = len(ing_tokens & usda_tokens)
            total = len(ing_tokens | usda_tokens)
            similarity = overlap / total if total > 0 else 0.0

            # Boost score for strong core similarity
            if similarity > 0.5:
                score += 20.0 * similarity
            else:
                # Penalize weak similarity
                score -= 30.0 * (1.0 - similarity)

        # Check for storage state consistency
        ing_storage = get_storage_state(ingredient_clean)
        usda_storage = get_storage_state(usda_match)

        if ing_storage and usda_storage and ing_storage != usda_storage:
            # Fresh vs frozen vs canned mismatch
            score -= 25.0

        # Normalize to reasonable range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 30.0


def extract_state_words(text):
    """Extract state/form/prep keywords"""
    keywords = ['raw', 'cooked', 'frozen', 'canned', 'fresh', 'dried', 'drained',
                'whole', 'diced', 'chopped', 'shredded', 'ground', 'sliced',
                'paste', 'sauce', 'puree', 'oil', 'thawed', 'uncooked']
    found = []
    for kw in keywords:
        if kw in text:
            found.append(kw)
    return found


def get_cooking_state(words):
    """Determine if raw, cooked, or unspecified"""
    if 'raw' in words or 'uncooked' in words:
        return 'raw'
    if 'cooked' in words:
        return 'cooked'
    return None


def get_form_descriptor(words):
    """Get the physical form"""
    forms = ['whole', 'diced', 'chopped', 'shredded', 'ground', 'sliced']
    for form in forms:
        if form in words:
            return form
    return None


def get_prep_level(text):
    """Determine preparation level: raw ingredient vs processed"""
    if 'sauce' in text or 'paste' in text:
        return 'processed'
    if 'puree' in text or 'juice' in text:
        return 'processed'
    return 'raw_ingredient'


def extract_additives(text):
    """Find additives mentioned (with oil, with salt, etc.)"""
    additives = set()
    if 'with oil' in text or 'in oil' in text:
        additives.add('oil')
    if 'with salt' in text or 'salted' in text:
        additives.add('salt')
    if 'with liquid' in text or 'in liquid' in text:
        additives.add('liquid')
    return additives


def get_storage_state(text):
    """Get storage state: fresh, frozen, canned"""
    if 'frozen' in text:
        return 'frozen'
    if 'canned' in text:
        return 'canned'
    if 'fresh' in text:
        return 'fresh'
    return None
