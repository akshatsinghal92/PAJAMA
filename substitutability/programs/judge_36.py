import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Clean and normalize inputs
        ing_clean = normalize_text(ingredient)
        usda_clean = normalize_text(usda_match)

        # Extract tokens
        ing_tokens = extract_tokens(ing_clean)
        usda_tokens = extract_tokens(usda_clean)

        if not ing_tokens or not usda_tokens:
            return 5.0

        # Categorize tokens
        ing_core = get_core_food_tokens(ing_tokens)
        ing_qualifiers = get_qualifier_tokens(ing_tokens)
        ing_prep = get_prep_tokens(ing_tokens)

        usda_core = get_core_food_tokens(usda_tokens)
        usda_qualifiers = get_qualifier_tokens(usda_tokens)
        usda_prep = get_prep_tokens(usda_tokens)

        # Base score from core food overlap
        core_score = calculate_core_overlap(ing_core, usda_core)

        # Specificity alignment score
        specificity_score = evaluate_specificity_alignment(
            ing_qualifiers, usda_qualifiers, ing_prep, usda_prep
        )

        # Preparation state alignment
        prep_score = evaluate_prep_alignment(ing_prep, usda_prep, ing_tokens, usda_tokens)

        # Token diversity penalty (variant-specific approach)
        diversity_penalty = calculate_diversity_penalty(ing_tokens, usda_tokens)

        # Weighted combination
        final_score = (
            core_score * 0.35 +
            specificity_score * 0.40 +
            prep_score * 0.20 +
            diversity_penalty * 0.05
        )

        # Scale to 0-100
        return max(0.0, min(100.0, final_score))

    except Exception:
        return 5.0


def normalize_text(text):
    # Remove gram weights
    text = re.sub(r'^\d+g?\s*', '', text)
    text = re.sub(r'\d+g\b', '', text)
    # Remove parentheticals
    text = re.sub(r'\([^)]*\)', '', text)
    # Lowercase and clean
    text = text.lower().strip()
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text


def extract_tokens(text):
    # Split on comma and whitespace
    tokens = re.findall(r'\b\w+\b', text)
    return [t for t in tokens if len(t) > 1]


def get_core_food_tokens(tokens):
    # Common food nouns (heuristic: longer words often core, first 2-3 tokens)
    stop_words = {'and', 'the', 'with', 'from', 'for', 'per'}
    core = []
    for tok in tokens[:4]:
        if tok not in stop_words and len(tok) >= 3:
            core.append(tok)
    return set(core)


def get_qualifier_tokens(tokens):
    qualifiers = {
        'extra', 'virgin', 'whole', 'diced', 'sliced', 'shredded', 'chopped',
        'fresh', 'frozen', 'canned', 'dried', 'smoked', 'ground', 'crushed',
        'cherry', 'roma', 'beefsteak', 'table', 'sea', 'kosher',
        'light', 'dark', 'white', 'brown', 'red', 'green', 'yellow',
        'balsamic', 'apple', 'white', 'rice', 'penne', 'spaghetti', 'rigatoni'
    }
    return set(tok for tok in tokens if tok in qualifiers)


def get_prep_tokens(tokens):
    prep_words = {
        'raw', 'cooked', 'boiled', 'fried', 'baked', 'grilled', 'roasted',
        'steamed', 'thawed', 'drained', 'rinsed', 'marinated', 'seasoned',
        'uncooked', 'prepared'
    }
    return set(tok for tok in tokens if tok in prep_words)


def calculate_core_overlap(ing_core, usda_core):
    if not ing_core or not usda_core:
        return 50.0

    # Jaccard similarity with boost for perfect match
    intersection = len(ing_core & usda_core)
    union = len(ing_core | usda_core)

    if union == 0:
        return 50.0

    jaccard = intersection / union

    # Boost if main food word matches
    score = jaccard * 80 + 20
    return score


def evaluate_specificity_alignment(ing_qual, usda_qual, ing_prep, usda_prep):
    # Variant 4 specific: entropy-based specificity measure

    # Count total qualifiers in each
    ing_total = len(ing_qual) + len(ing_prep)
    usda_total = len(usda_qual) + len(usda_prep)

    # Perfect case: both have same qualifiers
    qual_match = len(ing_qual & usda_qual)
    prep_match = len(ing_prep & usda_prep)

    if ing_total == 0 and usda_total == 0:
        # Both generic - perfect alignment
        return 100.0

    if ing_total == 0:
        # Ingredient is generic
        if usda_total <= 1:
            # USDA adds minimal specificity (OK for generic entries like "Salt, table")
            return 90.0
        else:
            # USDA too specific for generic ingredient
            penalty = (usda_total - 1) * 15
            return max(30.0, 90.0 - penalty)

    # Ingredient has qualifiers
    qual_coverage = qual_match / len(ing_qual) if ing_qual else 1.0
    prep_coverage = prep_match / len(ing_prep) if ing_prep else 1.0

    # Penalize USDA adding unexpected qualifiers
    extra_qual = usda_qual - ing_qual
    extra_prep = usda_prep - ing_prep

    score = 80.0
    score += qual_coverage * 10
    score += prep_coverage * 10
    score -= len(extra_qual) * 12
    score -= len(extra_prep) * 15

    # Penalize USDA missing critical qualifiers
    missing_qual = ing_qual - usda_qual
    missing_prep = ing_prep - usda_prep
    score -= len(missing_qual) * 10
    score -= len(missing_prep) * 12

    return max(0.0, min(100.0, score))


def evaluate_prep_alignment(ing_prep, usda_prep, ing_tokens, usda_tokens):
    # Critical conflicts
    conflicts = [
        ({'raw'}, {'cooked', 'fried', 'baked', 'boiled'}),
        ({'drained'}, {'with', 'oil'}),
        ({'frozen'}, {'fresh'}),
        ({'uncooked'}, {'cooked'}),
    ]

    for set_a, set_b in conflicts:
        if (ing_prep & set_a and usda_prep & set_b) or (ing_prep & set_b and usda_prep & set_a):
            return 0.0

    # Check for specific conflict patterns in full token list
    if 'drained' in ing_tokens and 'oil' in usda_tokens:
        return 0.0

    if ing_prep == usda_prep:
        return 100.0

    if not ing_prep and not usda_prep:
        return 90.0

    # Partial match
    if ing_prep and usda_prep:
        overlap = len(ing_prep & usda_prep)
        return 50.0 + (overlap / max(len(ing_prep), len(usda_prep))) * 40

    # One has prep, other doesn't
    if ing_prep and not usda_prep:
        return 60.0

    return 70.0


def calculate_diversity_penalty(ing_tokens, usda_tokens):
    # Variant 4: use token frequency distribution
    # Measure how "typical" the match is using coefficient of variation

    ing_counter = Counter(ing_tokens)
    usda_counter = Counter(usda_tokens)

    # All tokens union
    all_tokens = set(ing_tokens) | set(usda_tokens)

    if not all_tokens:
        return 50.0

    # Create frequency vector
    freq_diffs = []
    for token in all_tokens:
        ing_freq = ing_counter.get(token, 0)
        usda_freq = usda_counter.get(token, 0)
        freq_diffs.append(abs(ing_freq - usda_freq))

    # Lower variance in frequency differences = better match
    if freq_diffs:
        avg_diff = sum(freq_diffs) / len(freq_diffs)
        variance = sum((d - avg_diff) ** 2 for d in freq_diffs) / len(freq_diffs)

        # Normalize to score
        penalty_score = 100.0 / (1.0 + variance)
        return penalty_score

    return 50.0
