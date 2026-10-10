import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing_clean = clean_text(ingredient)
        usda_clean = clean_text(usda_match)

        if not ing_clean or not usda_clean:
            return 0.0

        # Extract tokens
        ing_tokens = tokenize(ing_clean)
        usda_tokens = tokenize(usda_clean)

        if not ing_tokens or not usda_tokens:
            return 0.0

        # Identify qualifiers vs core terms
        ing_qualifiers = extract_qualifiers(ing_tokens)
        usda_qualifiers = extract_qualifiers(usda_tokens)

        ing_core = extract_core_terms(ing_tokens)
        usda_core = extract_core_terms(usda_tokens)

        # Core food match (must overlap significantly)
        core_overlap = len(set(ing_core) & set(usda_core))
        core_max = max(len(ing_core), len(usda_core))
        if core_max == 0:
            return 0.0
        core_score = (core_overlap / core_max) * 40

        # Specificity alignment score
        ing_specificity = len(ing_qualifiers)
        usda_specificity = len(usda_qualifiers)

        # Count qualifier matches and mismatches
        qualifier_match = len(set(ing_qualifiers) & set(usda_qualifiers))
        ing_only = set(ing_qualifiers) - set(usda_qualifiers)
        usda_only = set(usda_qualifiers) - set(ing_qualifiers)

        # If ingredient is unqualified (generic), reward generic USDA match
        if ing_specificity == 0:
            if usda_specificity == 0:
                specificity_score = 50  # Both generic - perfect
            else:
                # USDA adds qualifiers ingredient doesn't have
                specificity_score = max(0, 50 - usda_specificity * 15)
        else:
            # Ingredient has qualifiers - check alignment
            if usda_specificity == 0:
                # USDA is too generic for qualified ingredient
                specificity_score = max(0, 30 - ing_specificity * 8)
            else:
                # Both have qualifiers - check match quality
                match_rate = qualifier_match / max(ing_specificity, 1)
                missing_penalty = len(ing_only) * 12
                extra_penalty = len(usda_only) * 10
                specificity_score = max(0, match_rate * 60 - missing_penalty - extra_penalty)

        # Detect problematic mismatches
        penalty = 0

        # State mismatches (cooked vs raw, etc)
        if has_state_mismatch(ing_qualifiers, usda_qualifiers):
            penalty += 25

        # Form mismatches (diced, whole, shredded, etc)
        if has_form_mismatch(ing_qualifiers, usda_qualifiers):
            penalty += 20

        # Preparation method additions in USDA
        if has_unwanted_prep(usda_qualifiers, ing_qualifiers):
            penalty += 18

        # Variety mismatches (cherry tomatoes vs tomatoes)
        if has_variety_mismatch(ing_tokens, usda_tokens):
            penalty += 15

        total_score = core_score + specificity_score - penalty

        return max(0.0, min(100.0, total_score))

    except Exception:
        return 0.0


def clean_text(text):
    # Remove gram weights like "300g", "30 g"
    text = re.sub(r'\b\d+\s*g\b', '', text, flags=re.IGNORECASE)
    # Remove parentheticals
    text = re.sub(r'\([^)]*\)', '', text)
    # Remove punctuation except commas (they're meaningful in USDA)
    text = re.sub(r'[^\w\s,]', ' ', text)
    return text.strip().lower()


def tokenize(text):
    # Split on whitespace and commas, filter empty
    tokens = re.split(r'[\s,]+', text)
    return [t for t in tokens if t and len(t) > 1]


def extract_qualifiers(tokens):
    # Qualifier words that indicate specificity
    qualifier_words = {
        'frozen', 'fresh', 'canned', 'dried', 'cooked', 'raw', 'roasted',
        'baked', 'grilled', 'fried', 'boiled', 'steamed', 'smoked',
        'diced', 'sliced', 'chopped', 'minced', 'shredded', 'whole',
        'ground', 'crushed', 'mashed', 'cubed', 'grated',
        'extra', 'virgin', 'light', 'dark', 'white', 'red', 'green',
        'unsalted', 'salted', 'sweetened', 'unsweetened', 'organic',
        'with', 'without', 'oil', 'butter', 'salt', 'sugar',
        'cherry', 'roma', 'beefsteak', 'grape', 'plum',
        'boneless', 'skinless', 'bone', 'skin',
        'table', 'sea', 'kosher', 'iodized'
    }
    return [t for t in tokens if t in qualifier_words]


def extract_core_terms(tokens):
    # Core food terms (not prep/state words)
    stop_words = {
        'frozen', 'fresh', 'canned', 'dried', 'cooked', 'raw', 'roasted',
        'baked', 'grilled', 'fried', 'boiled', 'steamed', 'smoked',
        'diced', 'sliced', 'chopped', 'minced', 'shredded', 'whole',
        'ground', 'crushed', 'mashed', 'cubed', 'grated',
        'extra', 'virgin', 'light', 'dark',
        'unsalted', 'salted', 'sweetened', 'unsweetened', 'organic',
        'with', 'without', 'drained', 'thawed',
        'boneless', 'skinless'
    }
    return [t for t in tokens if t not in stop_words]


def has_state_mismatch(ing_qual, usda_qual):
    # Detect state conflicts (cooked vs raw, frozen vs fresh, etc)
    state_groups = [
        {'cooked', 'boiled', 'steamed', 'baked', 'roasted', 'fried', 'grilled'},
        {'raw', 'fresh', 'uncooked'},
        {'frozen'},
        {'dried', 'dehydrated'},
        {'canned'}
    ]

    ing_states = set()
    usda_states = set()

    for group in state_groups:
        if any(q in group for q in ing_qual):
            ing_states.add(tuple(group))
        if any(q in group for q in usda_qual):
            usda_states.add(tuple(group))

    # If both have states but different ones
    if ing_states and usda_states and not ing_states.intersection(usda_states):
        return True
    return False


def has_form_mismatch(ing_qual, usda_qual):
    # Detect form conflicts (diced vs whole, etc)
    form_words = {'diced', 'whole', 'sliced', 'chopped', 'shredded', 'ground', 'crushed'}
    ing_forms = set(ing_qual) & form_words
    usda_forms = set(usda_qual) & form_words

    # If ingredient specifies a form but USDA has a different one
    if ing_forms and usda_forms and ing_forms != usda_forms:
        return True
    return False


def has_unwanted_prep(usda_qual, ing_qual):
    # USDA adds preparation methods ingredient doesn't have
    prep_words = {'with', 'oil', 'butter', 'salt', 'sugar'}
    usda_prep = set(usda_qual) & prep_words
    ing_prep = set(ing_qual) & prep_words

    # If USDA has prep words ingredient doesn't
    if usda_prep and not usda_prep.issubset(ing_prep):
        return True
    return False


def has_variety_mismatch(ing_tokens, usda_tokens):
    # Detect variety/subtype conflicts
    varieties = {'cherry', 'roma', 'grape', 'plum', 'beefsteak', 'heirloom'}
    ing_varieties = set(ing_tokens) & varieties
    usda_varieties = set(usda_tokens) & varieties

    # If ingredient specifies variety but USDA doesn't have it
    if ing_varieties and not ing_varieties.issubset(usda_varieties):
        return True
    return False
