import re
from collections import Counter


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize to lowercase
        ing_text = ingredient.lower().strip()
        usda_text = usda_match.lower().strip()

        # Strip amount prefix (e.g., "200g", "30g", "1.5kg")
        ing_text = re.sub(r'^\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|cup|tbsp|tsp)\s*', '', ing_text)

        # Remove parentheticals from ingredient
        ing_text = re.sub(r'\([^)]*\)', '', ing_text)

        # Remove post-comma clauses from ingredient (e.g., ", drained", ", thawed")
        ing_base = ing_text.split(',')[0].strip()

        # Define noise/prep words to strip
        noise_words = {
            'fresh', 'frozen', 'dried', 'canned', 'raw', 'cooked',
            'chopped', 'diced', 'sliced', 'shredded', 'minced', 'crushed',
            'whole', 'ground', 'grated', 'peeled', 'unpeeled',
            'to', 'taste', 'from', 'tube', 'drained', 'thawed',
            'organic', 'natural', 'extra', 'virgin', 'pure',
            'unsalted', 'salted', 'sweetened', 'unsweetened'
        }

        # Tokenize and filter
        def tokenize_and_filter(text):
            # Split on whitespace and common delimiters
            tokens = re.findall(r'\b[a-z]+\b', text)
            # Filter out noise words and very short tokens
            return [t for t in tokens if t not in noise_words and len(t) > 1]

        ing_tokens = tokenize_and_filter(ing_base)
        usda_tokens = tokenize_and_filter(usda_text)

        if not ing_tokens or not usda_tokens:
            return 0.0

        # Create token sets for overlap calculation
        ing_set = set(ing_tokens)
        usda_set = set(usda_tokens)

        # Calculate basic Jaccard similarity
        intersection = ing_set & usda_set
        union = ing_set | usda_set

        if not union:
            return 0.0

        jaccard = len(intersection) / len(union)

        # Bonus for ordered token matches (bigrams)
        ordered_bonus = 0.0
        if len(ing_tokens) > 1 and len(usda_tokens) > 1:
            ing_bigrams = set(zip(ing_tokens[:-1], ing_tokens[1:]))
            usda_bigrams = set(zip(usda_tokens[:-1], usda_tokens[1:]))
            if ing_bigrams and usda_bigrams:
                bigram_overlap = len(ing_bigrams & usda_bigrams) / max(len(ing_bigrams), len(usda_bigrams))
                ordered_bonus = bigram_overlap * 20

        # Penalty for unmatched tokens in USDA (extra specificity not in ingredient)
        unmatched_usda = usda_set - ing_set
        usda_penalty = len(unmatched_usda) * 5

        # Penalty for unmatched tokens in ingredient (ingredient asks for something USDA doesn't have)
        unmatched_ing = ing_set - usda_set
        ing_penalty = len(unmatched_ing) * 8

        # Calculate weighted score
        base_score = jaccard * 100

        # Apply bonuses and penalties
        score = base_score + ordered_bonus - usda_penalty - ing_penalty

        # Ensure score is non-negative
        score = max(0.0, score)

        return score

    except Exception:
        return 0.0
