import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Clean and normalize inputs
        ing_clean = clean_text(ingredient)
        usda_clean = clean_text(usda_match)

        # Extract tokens and qualifiers
        ing_tokens = tokenize(ing_clean)
        usda_tokens = tokenize(usda_clean)

        if not ing_tokens or not usda_tokens:
            return 0.0

        # Identify core food item (first significant token) vs qualifiers
        ing_core = extract_core_food(ing_tokens)
        usda_core = extract_core_food(usda_tokens)

        ing_qualifiers = extract_qualifiers(ing_tokens, ing_core)
        usda_qualifiers = extract_qualifiers(usda_tokens, usda_core)

        # Base score from core food match
        core_score = compute_core_match(ing_core, usda_core, ing_tokens, usda_tokens)

        # Specificity alignment score
        specificity_score = evaluate_specificity_alignment(
            ing_qualifiers, usda_qualifiers, ing_core, usda_core
        )

        # Penalty for problematic qualifier mismatches
        mismatch_penalty = compute_mismatch_penalty(
            ing_qualifiers, usda_qualifiers, ing_clean, usda_clean
        )

        # Combine scores with weights (variant 7 specific formula)
        final_score = (core_score * 0.3) + (specificity_score * 0.5) - (mismatch_penalty * 0.8)

        # Normalize to 0-100 range with sigmoid-like transformation
        normalized = 50 + (final_score * 5)
        return max(0.0, min(100.0, normalized))

    except Exception:
        return 25.0


def clean_text(text):
    # Remove gram weights (e.g., "300g"), parentheticals, and normalize
    text = re.sub(r'\b\d+g\b', '', text)
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'[,;:]', ' ', text)
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def tokenize(text):
    # Split into meaningful tokens
    tokens = text.split()
    # Filter out common stop words and prep methods that don't affect substitutability
    prep_words = {'from', 'tube', 'thawed', 'shredded', 'sliced', 'chopped', 'minced', 'drained'}
    return [t for t in tokens if t and t not in prep_words]


def extract_core_food(tokens):
    # Core food is typically the first 1-2 meaningful tokens
    if not tokens:
        return set()
    core = set()
    for i, token in enumerate(tokens[:2]):
        if len(token) > 2:  # Skip very short tokens
            core.add(token)
    return core


def extract_qualifiers(tokens, core):
    # Qualifiers are tokens not in the core
    return set(t for t in tokens if t not in core)


def compute_core_match(ing_core, usda_core, ing_tokens, usda_tokens):
    # Score how well the core food items match
    if not ing_core or not usda_core:
        return 0.0

    # Check for direct overlap in core
    overlap = ing_core & usda_core
    if overlap:
        overlap_ratio = len(overlap) / max(len(ing_core), len(usda_core))
        return 10.0 * overlap_ratio

    # Check for substring matches (e.g., "tomato" in "tomatoes")
    for ing_word in ing_core:
        for usda_word in usda_core:
            if ing_word in usda_word or usda_word in ing_word:
                return 7.0

    # Check if any core words appear in full token lists
    ing_set = set(ing_tokens)
    usda_set = set(usda_tokens)
    if ing_core & usda_set or usda_core & ing_set:
        return 5.0

    return 0.0


def evaluate_specificity_alignment(ing_quals, usda_quals, ing_core, usda_core):
    # Key insight: unqualified ingredients should match generic USDA entries
    # Qualified ingredients should have matching qualifiers

    ing_is_qualified = len(ing_quals) > 0
    usda_is_qualified = len(usda_quals) > 0

    # Case 1: Ingredient is unqualified (simple/generic)
    if not ing_is_qualified:
        if not usda_is_qualified:
            # Both unqualified - excellent match
            return 10.0
        else:
            # USDA adds qualifiers ingredient didn't ask for
            # Check if qualifiers are benign (like "table" for salt)
            benign_qualifiers = {'table', 'raw', 'fresh', 'plain'}
            if usda_quals.issubset(benign_qualifiers):
                return 7.0
            # Non-benign qualifiers reduce substitutability
            return 3.0 - len(usda_quals)

    # Case 2: Ingredient is qualified (has descriptors)
    else:
        if not usda_is_qualified:
            # USDA dropped qualifiers - less substitutable
            return 2.0

        # Both qualified - check alignment
        overlap = ing_quals & usda_quals
        ing_only = ing_quals - usda_quals
        usda_only = usda_quals - usda_quals

        # Score based on overlap
        if overlap:
            overlap_ratio = len(overlap) / len(ing_quals)
            base = 8.0 * overlap_ratio

            # Penalize extra qualifiers in USDA
            if usda_only:
                base -= len(usda_only) * 1.5

            return base
        else:
            # No overlap in qualifiers - poor match
            return 1.0


def compute_mismatch_penalty(ing_quals, usda_quals, ing_text, usda_text):
    # Penalize specific problematic mismatches
    penalty = 0.0

    # State mismatches (cooked vs not)
    state_words = {'cooked', 'uncooked', 'raw', 'frozen', 'canned', 'dried', 'fresh'}
    ing_states = ing_quals & state_words
    usda_states = usda_quals & state_words

    if ing_states != usda_states:
        # Different states mentioned
        if 'cooked' in usda_states and 'cooked' not in ing_states:
            penalty += 3.0  # USDA says cooked when ingredient doesn't
        if 'raw' in usda_states and 'canned' in ing_states:
            penalty += 2.5

    # Form mismatches (diced, whole, etc.)
    form_words = {'diced', 'whole', 'sliced', 'crushed', 'ground', 'paste', 'sauce'}
    ing_forms = ing_quals & form_words
    usda_forms = usda_quals & form_words

    if ing_forms and not (ing_forms & usda_forms):
        # Ingredient specifies form, USDA doesn't match
        penalty += 2.5

    if usda_forms and not (ing_forms & usda_forms):
        # USDA specifies different form
        if 'sauce' in ing_forms and 'sauce' not in usda_forms:
            penalty += 3.0  # sauce vs base ingredient
        else:
            penalty += 1.5

    # Added ingredients penalty (with oil, with butter, etc.)
    if 'with' in usda_text and 'with' not in ing_text:
        penalty += 2.0

    # Cherry/specific variety loss
    if 'cherry' in ing_text and 'cherry' not in usda_text:
        penalty += 1.5

    return penalty
