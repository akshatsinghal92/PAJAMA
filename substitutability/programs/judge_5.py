import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize and clean text
        def normalize(text):
            text = str(text).lower()
            # Remove gram weights like "200g", "30g"
            text = re.sub(r'\b\d+g\b', '', text)
            # Remove parentheticals
            text = re.sub(r'\([^)]*\)', '', text)
            # Remove comma clauses (states, post-comma info)
            text = text.split(',')[0].strip()
            return text

        ingredient_clean = normalize(ingredient)
        usda_clean = normalize(usda_match)

        if not ingredient_clean or not usda_clean:
            return 0.0

        # Tokenize into words
        def tokenize(text):
            # Split on whitespace and common separators
            tokens = re.findall(r'\b[a-z]+\b', text)
            return tokens

        ing_tokens = tokenize(ingredient_clean)
        usda_tokens = tokenize(usda_clean)

        if not ing_tokens or not usda_tokens:
            return 0.0

        # Define stop words and descriptor words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'to', 'from', 'with'}
        descriptor_words = {
            'raw', 'cooked', 'frozen', 'fresh', 'canned', 'dried', 'ground',
            'whole', 'diced', 'chopped', 'sliced', 'shredded', 'grated',
            'uncooked', 'boiled', 'fried', 'roasted', 'baked', 'steamed',
            'drained', 'undrained', 'with', 'without', 'oil', 'water', 'sauce'
        }

        # Extract core food words (not stop words, not descriptors)
        ing_core = [w for w in ing_tokens if w not in stop_words]
        usda_core = [w for w in usda_tokens if w not in stop_words]

        ing_food = [w for w in ing_core if w not in descriptor_words]
        usda_food = [w for w in usda_core if w not in descriptor_words]

        ing_desc = [w for w in ing_core if w in descriptor_words]
        usda_desc = [w for w in usda_core if w in descriptor_words]

        # Calculate core food word overlap using position-weighted scoring
        score = 0.0

        # Primary matching: core food words
        if ing_food and usda_food:
            ing_food_set = set(ing_food)
            usda_food_set = set(usda_food)

            # Count overlapping food words
            overlap = ing_food_set & usda_food_set

            # Position-weighted overlap: earlier words matter more
            position_score = 0.0
            for i, word in enumerate(ing_food):
                if word in usda_food_set:
                    # Weight decreases with position (first word = 1.0, second = 0.9, etc.)
                    weight = 1.0 / (i + 1)
                    position_score += weight * 20  # Base score per match

            # Jaccard similarity component
            union = ing_food_set | usda_food_set
            if union:
                jaccard = len(overlap) / len(union)
                score += jaccard * 40

            score += position_score

            # Bonus for exact head-word match (first food word)
            if ing_food[0] == usda_food[0]:
                score += 20
        else:
            # No food words identified, fall back to simple overlap
            ing_set = set(ing_core)
            usda_set = set(usda_core)
            overlap = ing_set & usda_set
            union = ing_set | usda_set
            if union:
                score = (len(overlap) / len(union)) * 60

        # Penalty for conflicting descriptors
        conflicting_pairs = [
            ('cooked', 'raw'), ('cooked', 'uncooked'), ('cooked', 'frozen'),
            ('frozen', 'fresh'), ('canned', 'fresh'), ('dried', 'fresh'),
            ('drained', 'oil'), ('drained', 'undrained'),
            ('whole', 'diced'), ('whole', 'chopped'), ('whole', 'sliced')
        ]

        penalty = 0.0
        for w1, w2 in conflicting_pairs:
            if (w1 in ing_desc and w2 in usda_desc) or (w2 in ing_desc and w1 in usda_desc):
                penalty += 15

        # Additional penalty if descriptors are very different
        if ing_desc and usda_desc:
            desc_overlap = set(ing_desc) & set(usda_desc)
            desc_union = set(ing_desc) | set(usda_desc)
            if desc_union:
                desc_dissimilarity = 1.0 - (len(desc_overlap) / len(desc_union))
                penalty += desc_dissimilarity * 10
        elif ing_desc or usda_desc:
            # One has descriptors, other doesn't
            penalty += 8

        final_score = max(0.0, score - penalty)

        # Normalize to 0-100 range
        return min(100.0, final_score)

    except Exception:
        return 0.0
