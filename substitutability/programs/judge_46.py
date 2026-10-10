import re
from collections import Counter


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize to lowercase
        ing = ingredient.lower()
        usda = usda_match.lower()

        # Remove gram weights (e.g., "300g", "40g")
        ing = re.sub(r'\b\d+g\b', '', ing)

        # Remove common noise words and prep descriptors
        noise_words = {
            'diced', 'chopped', 'sliced', 'minced', 'crushed', 'shredded',
            'to', 'taste', 'from', 'tube', 'and', 'or', 'the', 'a', 'an',
            'fresh', 'frozen', 'thawed', 'defrosted', 'room', 'temperature',
            'optional', 'if', 'needed', 'desired', 'for', 'serving'
        }

        # Extract tokens, removing punctuation boundaries
        ing_tokens = [t for t in re.findall(r'\b[a-z]+\b', ing) if t not in noise_words and len(t) > 1]
        usda_tokens = [t for t in re.findall(r'\b[a-z]+\b', usda) if t not in noise_words and len(t) > 1]

        if not ing_tokens or not usda_tokens:
            return 0.0

        # Convert to sets for overlap calculation
        ing_set = set(ing_tokens)
        usda_set = set(usda_tokens)

        # Core overlap metric: Jaccard similarity
        intersection = ing_set & usda_set
        union = ing_set | usda_set
        jaccard = len(intersection) / len(union) if union else 0.0

        # Bidirectional coverage: what fraction of each is covered by the other
        ing_coverage = len(intersection) / len(ing_set) if ing_set else 0.0
        usda_coverage = len(intersection) / len(usda_set) if usda_set else 0.0

        # Token frequency weighting: reward matching tokens that appear multiple times
        ing_counter = Counter(ing_tokens)
        usda_counter = Counter(usda_tokens)

        freq_weighted_overlap = sum(min(ing_counter[t], usda_counter[t]) for t in intersection)
        max_possible_freq = sum(ing_counter.values()) + sum(usda_counter.values())
        freq_score = (2 * freq_weighted_overlap / max_possible_freq) if max_possible_freq > 0 else 0.0

        # Position-aware scoring: earlier tokens in USDA description are more important
        # USDA format is typically "Primary food, descriptor, descriptor"
        position_bonus = 0.0
        if usda_tokens:
            # First 3 tokens in USDA get higher weight
            important_usda = set(usda_tokens[:min(3, len(usda_tokens))])
            position_bonus = len(ing_set & important_usda) / len(important_usda) if important_usda else 0.0

        # Critical modifier detection: penalize if ingredient has state that USDA doesn't match
        critical_modifiers = {
            'raw', 'cooked', 'canned', 'dried', 'ground', 'whole', 'paste', 'sauce',
            'oil', 'powder', 'juice', 'puree', 'extract', 'concentrate'
        }

        ing_critical = ing_set & critical_modifiers
        usda_critical = usda_set & critical_modifiers

        # Penalty if ingredient has critical modifier that USDA doesn't have
        critical_penalty = 0.0
        if ing_critical:
            missing_critical = ing_critical - usda_critical
            critical_penalty = len(missing_critical) / len(ing_critical)

        # Combined score with weighted components
        base_score = (
            jaccard * 30 +                    # Overall token overlap
            ing_coverage * 25 +               # How much of ingredient is covered
            usda_coverage * 15 +              # How much of USDA is covered
            freq_score * 20 +                 # Frequency-weighted overlap
            position_bonus * 10               # Position-aware matching
        )

        # Apply critical modifier penalty
        final_score = base_score * (1.0 - critical_penalty * 0.4)

        return round(final_score, 2)

    except Exception:
        return 0.0
