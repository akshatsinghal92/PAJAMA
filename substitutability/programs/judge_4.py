import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing_clean = normalize_text(ingredient)
        usda_clean = normalize_text(usda_match)

        if not ing_clean or not usda_clean:
            return 0.0

        # Extract core food tokens
        ing_tokens = extract_core_tokens(ing_clean)
        usda_tokens = extract_core_tokens(usda_clean)

        if not ing_tokens or not usda_tokens:
            return 0.0

        # Score using n-gram overlap with positional weighting
        score = 0.0

        # 1. Unigram overlap with position weights (earlier = more important)
        ing_unigrams = create_weighted_tokens(ing_tokens)
        usda_unigrams = create_weighted_tokens(usda_tokens)
        unigram_score = calculate_weighted_overlap(ing_unigrams, usda_unigrams)
        score += unigram_score * 40

        # 2. Bigram overlap (core food identity)
        ing_bigrams = create_ngrams(ing_tokens, 2)
        usda_bigrams = create_ngrams(usda_tokens, 2)
        bigram_score = calculate_overlap(ing_bigrams, usda_bigrams)
        score += bigram_score * 30

        # 3. Check for core food noun exact match (first meaningful word)
        core_match = check_core_match(ing_tokens, usda_tokens)
        score += core_match * 20

        # 4. Penalize state mismatches
        state_penalty = check_state_mismatch(ing_clean, usda_clean)
        score -= state_penalty

        # 5. Penalize form mismatches
        form_penalty = check_form_mismatch(ing_clean, usda_clean)
        score -= form_penalty

        # Ensure score is non-negative and cap at 100
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 0.0


def normalize_text(text):
    """Remove gram weights, lowercase, clean text"""
    # Remove gram weights like "300g ", "30g ", etc.
    text = re.sub(r'^\d+g?\s+', '', text)
    text = re.sub(r'^\d+\.\d+g?\s+', '', text)
    # Remove parentheticals
    text = re.sub(r'\([^)]*\)', '', text)
    # Lowercase
    text = text.lower().strip()
    return text


def extract_core_tokens(text):
    """Extract meaningful food tokens, removing prep words"""
    prep_words = {
        'frozen', 'fresh', 'canned', 'cooked', 'raw', 'dried', 'drained',
        'thawed', 'chopped', 'diced', 'sliced', 'shredded', 'minced',
        'crushed', 'ground', 'whole', 'boneless', 'skinless', 'with', 'without',
        'from', 'in', 'of', 'and', 'or', 'the', 'a', 'an', 'uncooked'
    }

    # Split on commas and whitespace
    text = text.replace(',', ' ')
    tokens = text.split()

    # Keep only meaningful tokens
    core_tokens = [t for t in tokens if t not in prep_words and len(t) > 1]

    return core_tokens


def create_weighted_tokens(tokens):
    """Create tokens with positional weights (earlier = higher weight)"""
    weighted = {}
    for i, token in enumerate(tokens):
        # Weight decreases with position (first token has highest weight)
        weight = 1.0 / (i + 1)
        weighted[token] = weighted.get(token, 0) + weight
    return weighted


def calculate_weighted_overlap(weighted1, weighted2):
    """Calculate overlap between weighted token dictionaries"""
    if not weighted1 or not weighted2:
        return 0.0

    overlap_score = 0.0
    max_score = 0.0

    for token, weight1 in weighted1.items():
        max_score += weight1
        if token in weighted2:
            # Use minimum of the two weights
            overlap_score += min(weight1, weighted2[token])

    if max_score == 0:
        return 0.0

    return overlap_score / max_score


def create_ngrams(tokens, n):
    """Create n-grams from token list"""
    if len(tokens) < n:
        return []
    ngrams = []
    for i in range(len(tokens) - n + 1):
        ngram = ' '.join(tokens[i:i+n])
        ngrams.append(ngram)
    return ngrams


def calculate_overlap(list1, list2):
    """Calculate Jaccard overlap between two lists"""
    if not list1 or not list2:
        return 0.0

    set1 = set(list1)
    set2 = set(list2)

    intersection = len(set1 & set2)
    union = len(set1 | set2)

    if union == 0:
        return 0.0

    return intersection / union


def check_core_match(ing_tokens, usda_tokens):
    """Check if the first meaningful noun matches"""
    if not ing_tokens or not usda_tokens:
        return 0.0

    # Check if first token matches
    if ing_tokens[0] == usda_tokens[0]:
        return 1.0

    # Check if first token of ingredient appears anywhere in USDA first 3 tokens
    if ing_tokens[0] in usda_tokens[:3]:
        return 0.7

    # Check if any of first 2 ingredient tokens match any of first 2 USDA tokens
    ing_head = set(ing_tokens[:2])
    usda_head = set(usda_tokens[:2])
    if ing_head & usda_head:
        return 0.5

    return 0.0


def check_state_mismatch(ing_text, usda_text):
    """Penalize state mismatches (cooked vs raw, drained vs with oil, etc.)"""
    penalty = 0.0

    # Check for cooked/raw mismatch
    ing_has_cooked = 'cooked' in ing_text
    usda_has_cooked = 'cooked' in usda_text
    ing_has_raw = 'raw' in ing_text
    usda_has_raw = 'raw' in usda_text

    if (ing_has_cooked and usda_has_raw) or (ing_has_raw and usda_has_cooked):
        penalty += 20
    elif ing_has_cooked != usda_has_cooked:
        penalty += 15

    # Check for drained vs with oil/sauce
    ing_has_drained = 'drained' in ing_text
    usda_has_oil = 'oil' in usda_text or 'sauce' in usda_text

    if ing_has_drained and usda_has_oil:
        penalty += 25

    # Check for sauce vs base ingredient
    ing_has_sauce = 'sauce' in ing_text
    usda_has_sauce = 'sauce' in usda_text

    if ing_has_sauce != usda_has_sauce:
        penalty += 20

    return penalty


def check_form_mismatch(ing_text, usda_text):
    """Penalize form mismatches (whole vs diced, paste vs powder, etc.)"""
    penalty = 0.0

    form_words = ['whole', 'diced', 'sliced', 'shredded', 'crushed',
                  'minced', 'chopped', 'paste', 'powder', 'ground']

    ing_forms = [w for w in form_words if w in ing_text]
    usda_forms = [w for w in form_words if w in usda_text]

    # If ingredient specifies a form but USDA has a different one
    if ing_forms and usda_forms:
        if set(ing_forms) != set(usda_forms):
            penalty += 15

    return penalty
