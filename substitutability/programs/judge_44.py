import re
from collections import Counter


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize and clean text
        def clean_text(text):
            text = text.lower().strip()
            # Remove gram weights like "300g", "40g"
            text = re.sub(r'\b\d+g\b', '', text)
            # Remove other quantity patterns
            text = re.sub(r'\b\d+(\.\d+)?\s*(ml|kg|oz|lb|cup|tbsp|tsp|teaspoon|tablespoon)\b', '', text)
            # Remove common noise words and prep phrases
            noise = r'\b(diced|chopped|sliced|minced|shredded|crushed|to taste|from tube|fresh|frozen|thawed|drained)\b'
            text = re.sub(noise, '', text)
            # Remove parentheticals
            text = re.sub(r'\([^)]*\)', '', text)
            # Clean up punctuation and extra spaces
            text = re.sub(r'[,;:]', ' ', text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

        ingredient_clean = clean_text(ingredient)
        usda_clean = clean_text(usda_match)

        if not ingredient_clean or not usda_clean:
            return 0.0

        # Tokenize into words
        ingredient_tokens = [t for t in ingredient_clean.split() if len(t) > 1]
        usda_tokens = [t for t in usda_clean.split() if len(t) > 1]

        if not ingredient_tokens or not usda_tokens:
            return 0.0

        # Component 1: Jaccard similarity on token sets
        ingredient_set = set(ingredient_tokens)
        usda_set = set(usda_tokens)
        intersection = ingredient_set & usda_set
        union = ingredient_set | usda_set
        jaccard = len(intersection) / len(union) if union else 0.0

        # Component 2: Ordered bigram overlap (preserves word order)
        def get_bigrams(tokens):
            if len(tokens) < 2:
                return []
            return [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]

        ingredient_bigrams = get_bigrams(ingredient_tokens)
        usda_bigrams = get_bigrams(usda_tokens)

        if ingredient_bigrams and usda_bigrams:
            bigram_ingredient_set = set(ingredient_bigrams)
            bigram_usda_set = set(usda_bigrams)
            bigram_intersection = bigram_ingredient_set & bigram_usda_set
            bigram_union = bigram_ingredient_set | bigram_usda_set
            bigram_jaccard = len(bigram_intersection) / len(bigram_union) if bigram_union else 0.0
        else:
            bigram_jaccard = 0.0

        # Component 3: Token frequency weighted overlap
        ingredient_counter = Counter(ingredient_tokens)
        usda_counter = Counter(usda_tokens)

        overlap_score = 0.0
        for token in ingredient_set:
            if token in usda_counter:
                # Weight by frequency in ingredient
                overlap_score += min(ingredient_counter[token], usda_counter[token])

        max_possible = sum(ingredient_counter.values())
        frequency_overlap = overlap_score / max_possible if max_possible > 0 else 0.0

        # Component 4: Penalty for missing critical ingredient tokens in USDA
        # Critical tokens are content words that appear in ingredient but not in USDA
        missing_ingredient_tokens = ingredient_set - usda_set
        missing_penalty = len(missing_ingredient_tokens) / max(len(ingredient_set), 1)

        # Component 5: Bonus for substring matches (e.g., "tomato" in "tomatoes")
        substring_bonus = 0.0
        for ing_token in ingredient_tokens:
            for usda_token in usda_tokens:
                if len(ing_token) >= 4 and len(usda_token) >= 4:
                    if ing_token in usda_token or usda_token in ing_token:
                        substring_bonus += 0.5
        substring_bonus = min(substring_bonus, 2.0)  # Cap the bonus

        # Component 6: Check for state mismatches that matter
        # Look for preparation state conflicts in original text
        orig_ingredient = ingredient.lower()
        orig_usda = usda_match.lower()

        state_penalty = 0.0
        # Check for raw vs cooked mismatches
        if 'raw' in orig_ingredient and 'cooked' in orig_usda:
            state_penalty += 2.0
        if 'cooked' in orig_ingredient and 'raw' in orig_usda:
            state_penalty += 2.0
        # Check for oil/fat additions
        if 'with oil' in orig_usda and 'oil' not in orig_ingredient:
            state_penalty += 1.5
        # Check for sauce vs base ingredient
        if 'sauce' in orig_ingredient and 'sauce' not in orig_usda:
            state_penalty += 1.5

        # Final score calculation (0-10 scale)
        # Weight different components
        score = (
            jaccard * 4.0 +              # Base token overlap
            bigram_jaccard * 3.0 +       # Ordered bigram overlap
            frequency_overlap * 2.0 +    # Frequency-weighted overlap
            substring_bonus * 0.5 -      # Substring match bonus
            missing_penalty * 2.0 -      # Penalty for missing tokens
            state_penalty                # State mismatch penalty
        )

        # Normalize to 0-10 range
        score = max(0.0, min(10.0, score))

        return score

    except Exception as e:
        return 0.0
