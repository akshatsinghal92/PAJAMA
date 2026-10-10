import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize to lowercase
        ing = ingredient.lower().strip()
        usda = usda_match.lower().strip()

        # Strip gram weights (e.g., "300g", "30 g")
        ing = re.sub(r'\b\d+\s*g\b', '', ing)

        # Strip parentheticals
        ing = re.sub(r'\([^)]*\)', '', ing)

        # Remove punctuation except spaces
        ing = re.sub(r'[,;:\.]', ' ', ing)
        usda = re.sub(r'[,;:\.]', ' ', usda)

        # Define noise/modifier words to filter
        noise_words = {
            'diced', 'chopped', 'sliced', 'minced', 'shredded', 'grated',
            'to', 'taste', 'from', 'tube', 'can', 'jar', 'bottle',
            'dried', 'fresh', 'frozen', 'thawed', 'drained',
            'raw', 'cooked', 'roasted', 'grilled', 'steamed', 'boiled',
            'whole', 'ground', 'crushed', 'powdered', 'canned',
            'organic', 'unsalted', 'salted', 'uncooked',
            'the', 'and', 'or', 'with', 'oil'
        }

        # Tokenize (extract words)
        ing_tokens = [w for w in re.findall(r'\b[a-z]+\b', ing) if len(w) > 1]
        usda_tokens = [w for w in re.findall(r'\b[a-z]+\b', usda) if len(w) > 1]

        # Separate core food words from modifiers
        ing_core = [t for t in ing_tokens if t not in noise_words]
        usda_core = [t for t in usda_tokens if t not in noise_words]

        if not ing_core or not usda_core:
            return 0.0

        # 1. Set-based Jaccard similarity of core tokens
        ing_set = set(ing_core)
        usda_set = set(usda_core)

        intersection = ing_set & usda_set
        union = ing_set | usda_set

        if not union:
            return 0.0

        jaccard = len(intersection) / len(union)

        # 2. Ordered bigram overlap (position-sensitive)
        ing_bigrams = [' '.join(ing_core[i:i+2]) for i in range(len(ing_core) - 1)]
        usda_bigrams = [' '.join(usda_core[i:i+2]) for i in range(len(usda_core) - 1)]

        bigram_score = 0.0
        if ing_bigrams and usda_bigrams:
            ing_bg_set = set(ing_bigrams)
            usda_bg_set = set(usda_bigrams)
            bg_intersection = ing_bg_set & usda_bg_set
            bg_union = ing_bg_set | usda_bg_set
            if bg_union:
                bigram_score = len(bg_intersection) / len(bg_union)

        # 3. Token frequency cosine similarity
        ing_counter = Counter(ing_core)
        usda_counter = Counter(usda_core)

        dot_product = sum(ing_counter[token] * usda_counter[token] for token in intersection)
        ing_magnitude = sum(count ** 2 for count in ing_counter.values()) ** 0.5
        usda_magnitude = sum(count ** 2 for count in usda_counter.values()) ** 0.5

        cosine_score = 0.0
        if ing_magnitude > 0 and usda_magnitude > 0:
            cosine_score = dot_product / (ing_magnitude * usda_magnitude)

        # 4. Exact subsequence match bonus
        ing_text = ' '.join(ing_core)
        usda_text = ' '.join(usda_core)

        subsequence_bonus = 0.0
        if ing_text in usda_text or usda_text in ing_text:
            subsequence_bonus = 0.15

        # 5. Penalty for mismatched modifiers (original full token sets)
        ing_modifiers = set(t for t in ing_tokens if t in noise_words)
        usda_modifiers = set(t for t in usda_tokens if t in noise_words)

        modifier_mismatch = len(ing_modifiers.symmetric_difference(usda_modifiers))
        modifier_penalty = min(0.2, modifier_mismatch * 0.05)

        # Weighted combination (scale to 0-100)
        base_score = (
            35 * jaccard +
            25 * bigram_score +
            25 * cosine_score +
            15 * subsequence_bonus
        )

        final_score = max(0.0, base_score - (modifier_penalty * 100))

        return round(final_score, 2)

    except Exception:
        return 0.0
