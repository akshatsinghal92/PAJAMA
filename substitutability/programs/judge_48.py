import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize to lowercase
        ing = ingredient.lower().strip()
        usda = usda_match.lower().strip()

        # Remove gram weights (e.g., "200g", "30g")
        ing = re.sub(r'\b\d+\.?\d*\s*g\b', '', ing)

        # Remove parentheticals
        ing = re.sub(r'\([^)]*\)', '', ing)
        usda = re.sub(r'\([^)]*\)', '', usda)

        # Noise words to remove (prep methods and filler words only)
        noise = {'diced', 'chopped', 'minced', 'sliced', 'shredded', 'to', 'taste',
                 'from', 'tube', 'bottle', 'package', 'about', 'approximately',
                 'optional', 'thawed'}

        # Extract all alphabetic tokens
        ing_tokens = [t for t in re.findall(r'\b[a-z]+\b', ing) if t not in noise and len(t) > 1]
        usda_tokens = [t for t in re.findall(r'\b[a-z]+\b', usda) if t not in noise and len(t) > 1]

        if not ing_tokens or not usda_tokens:
            return 0.0

        ing_set = set(ing_tokens)
        usda_set = set(usda_tokens)
        intersection = ing_set & usda_set

        # 1. Core metric: bidirectional token containment
        # How much of ingredient is covered by USDA, and vice versa
        ing_containment = len(intersection) / len(ing_set) if ing_set else 0
        usda_containment = len(intersection) / len(usda_set) if usda_set else 0

        # Harmonic mean favors balanced bidirectional coverage
        if ing_containment + usda_containment > 0:
            containment_score = 2 * (ing_containment * usda_containment) / (ing_containment + usda_containment)
        else:
            containment_score = 0.0

        # 2. Position-aware token matching
        # Tokens appearing in similar relative positions score higher
        position_matches = 0
        position_sum = 0.0
        for i, ing_tok in enumerate(ing_tokens):
            for j, usda_tok in enumerate(usda_tokens):
                if ing_tok == usda_tok:
                    ing_pos = i / max(len(ing_tokens) - 1, 1)
                    usda_pos = j / max(len(usda_tokens) - 1, 1)
                    position_closeness = 1 - abs(ing_pos - usda_pos)
                    position_sum += position_closeness
                    position_matches += 1

        position_score = (position_sum / position_matches) if position_matches > 0 else 0.0

        # 3. Ordered bigram overlap
        # Check for consecutive token pairs that match
        ing_bigrams = set(zip(ing_tokens[:-1], ing_tokens[1:])) if len(ing_tokens) > 1 else set()
        usda_bigrams = set(zip(usda_tokens[:-1], usda_tokens[1:])) if len(usda_tokens) > 1 else set()
        bigram_intersection = ing_bigrams & usda_bigrams

        bigram_score = 0.0
        if ing_bigrams or usda_bigrams:
            bigram_union = ing_bigrams | usda_bigrams
            bigram_score = len(bigram_intersection) / len(bigram_union) if bigram_union else 0.0

        # 4. State conflict detection
        # Penalize conflicting preparation/form states
        penalty = 0.0

        # Check for drained vs with-oil/with-water conflicts
        if 'drained' in ing and ('oil' in usda or 'water' in ' '.join(usda_tokens)):
            penalty += 0.35

        # Check for raw vs cooked conflicts
        ing_has_raw = 'raw' in ing_tokens
        ing_has_cooked = 'cooked' in ing_tokens
        usda_has_raw = 'raw' in usda_tokens
        usda_has_cooked = 'cooked' in usda_tokens

        if (ing_has_raw and usda_has_cooked) or (ing_has_cooked and usda_has_raw):
            penalty += 0.25

        # Check for specific form mismatches (sauce vs raw ingredient)
        if 'sauce' in ing_tokens and 'sauce' not in usda_tokens:
            penalty += 0.30
        if 'sauce' in usda_tokens and 'sauce' not in ing_tokens:
            penalty += 0.30

        # Check for specific type mismatches (e.g., "whole cherry" vs generic)
        specific_types = {'cherry', 'grape', 'roma', 'beef', 'chicken', 'pork',
                          'penne', 'spaghetti', 'rigatoni', 'fusilli'}
        ing_specifics = ing_set & specific_types
        usda_specifics = usda_set & specific_types

        # If ingredient specifies a type but USDA doesn't have it, penalize
        if ing_specifics and not (ing_specifics & usda_specifics):
            penalty += 0.20

        # 5. Exact phrase match bonus
        # Check if key ingredient phrase appears in USDA or vice versa
        phrase_bonus = 0.0
        ing_phrase = ' '.join(ing_tokens[:min(2, len(ing_tokens))])
        usda_phrase = ' '.join(usda_tokens[:min(2, len(usda_tokens))])
        usda_full = ' '.join(usda_tokens)
        ing_full = ' '.join(ing_tokens)

        if ing_phrase in usda_full or usda_phrase in ing_full:
            phrase_bonus = 0.15

        # Combine all metrics into final score (0-100 scale)
        base_score = (
            containment_score * 40 +
            position_score * 25 +
            bigram_score * 20 +
            phrase_bonus * 15
        )

        # Apply penalty
        final_score = max(0.0, base_score - (penalty * 100))

        return final_score

    except Exception:
        return 0.0
