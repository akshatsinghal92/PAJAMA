import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize to lowercase
        ingredient = ingredient.lower()
        usda_match = usda_match.lower()

        # Strip leading weight patterns like "300g ", "30 g ", "1.5kg "
        ingredient = re.sub(r'^\d+\.?\d*\s*(?:g|kg|ml|l|oz|lb|cup|tbsp|tsp)\s+', '', ingredient)

        # Remove parentheticals
        ingredient = re.sub(r'\([^)]*\)', '', ingredient)
        usda_match = re.sub(r'\([^)]*\)', '', usda_match)

        # Define noise words to remove (prep words, common modifiers)
        noise_words = {
            'diced', 'chopped', 'sliced', 'shredded', 'minced', 'crushed',
            'grated', 'ground', 'whole', 'halved', 'quartered',
            'to', 'taste', 'from', 'tube', 'fresh', 'frozen', 'thawed',
            'about', 'approximately', 'or', 'more'
        }

        # Tokenize by splitting on non-alphanumeric
        ingredient_tokens = [t for t in re.findall(r'\b\w+\b', ingredient) if len(t) > 1]
        usda_tokens = [t for t in re.findall(r'\b\w+\b', usda_match) if len(t) > 1]

        # Separate food nouns from descriptors
        # Descriptors are cooking states and forms
        descriptor_words = {
            'raw', 'cooked', 'boiled', 'fried', 'baked', 'roasted', 'grilled',
            'steamed', 'canned', 'dried', 'powdered', 'paste', 'sauce',
            'oil', 'juice', 'puree', 'concentrate', 'drained', 'undrained',
            'with', 'without', 'uncooked', 'prepared', 'unprepared'
        }

        # Filter out noise words but keep descriptors for later analysis
        ingredient_clean = [t for t in ingredient_tokens if t not in noise_words]
        usda_clean = [t for t in usda_tokens if t not in noise_words]

        # Extract food nouns (non-descriptors)
        ingredient_nouns = [t for t in ingredient_clean if t not in descriptor_words]
        usda_nouns = [t for t in usda_clean if t not in descriptor_words]

        # Extract descriptors
        ingredient_descriptors = [t for t in ingredient_clean if t in descriptor_words]
        usda_descriptors = [t for t in usda_clean if t in descriptor_words]

        if not ingredient_nouns and not usda_nouns:
            return 5.0  # Neutral score if no content

        # Calculate unigram Jaccard for food nouns (weighted heavily)
        noun_set_ing = set(ingredient_nouns)
        noun_set_usda = set(usda_nouns)
        noun_intersection = noun_set_ing & noun_set_usda
        noun_union = noun_set_ing | noun_set_usda

        noun_jaccard = len(noun_intersection) / len(noun_union) if noun_union else 0.0

        # Calculate bigram overlap (ordered token pairs for both nouns and all tokens)
        def get_bigrams(tokens):
            return [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens)-1)]

        ingredient_bigrams = set(get_bigrams(ingredient_nouns))
        usda_bigrams = set(get_bigrams(usda_nouns))

        bigram_intersection = ingredient_bigrams & usda_bigrams
        bigram_union = ingredient_bigrams | usda_bigrams
        bigram_jaccard = len(bigram_intersection) / len(bigram_union) if bigram_union else 0.0

        # Descriptor conflict detection (penalize mismatches in preparation state)
        descriptor_penalty = 0.0

        # Conflicting descriptor pairs
        conflicts = [
            ('raw', 'cooked'), ('drained', 'oil'), ('sauce', 'paste'),
            ('canned', 'raw'), ('uncooked', 'cooked')
        ]

        for d1, d2 in conflicts:
            if (d1 in ingredient_descriptors and d2 in usda_descriptors) or \
               (d2 in ingredient_descriptors and d1 in usda_descriptors):
                descriptor_penalty += 2.0

        # Calculate token frequency similarity using cosine similarity
        ingredient_counter = Counter(ingredient_nouns)
        usda_counter = Counter(usda_nouns)

        all_nouns = set(ingredient_nouns + usda_nouns)
        dot_product = sum(ingredient_counter[t] * usda_counter[t] for t in all_nouns)

        ing_magnitude = sum(c*c for c in ingredient_counter.values()) ** 0.5
        usda_magnitude = sum(c*c for c in usda_counter.values()) ** 0.5

        cosine_sim = 0.0
        if ing_magnitude > 0 and usda_magnitude > 0:
            cosine_sim = dot_product / (ing_magnitude * usda_magnitude)

        # Coverage: what fraction of ingredient nouns appear in USDA match
        coverage = len(noun_intersection) / len(noun_set_ing) if noun_set_ing else 0.0

        # Final weighted score (0-100 range)
        # Variant 2: Heavy weight on noun Jaccard, bigram order, coverage, cosine similarity
        score = (
            40.0 * noun_jaccard +      # Primary food noun overlap
            20.0 * bigram_jaccard +     # Ordered bigram matching
            25.0 * coverage +           # Ingredient coverage in USDA
            15.0 * cosine_sim           # Token frequency alignment
        ) - descriptor_penalty

        # Clamp to reasonable range
        score = max(0.0, min(100.0, score))

        return round(score, 2)

    except Exception:
        return 5.0
