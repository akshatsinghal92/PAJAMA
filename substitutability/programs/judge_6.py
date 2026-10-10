import re
import math
from collections import Counter


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing = str(ingredient).lower().strip()
        usda = str(usda_match).lower().strip()

        if not ing or not usda:
            return 0.0

        # Extract core text (remove gram weights, parentheticals)
        ing_clean = re.sub(r'^\d+g?\s*', '', ing)
        ing_clean = re.sub(r'\([^)]*\)', '', ing_clean)
        ing_clean = re.sub(r'\s+', ' ', ing_clean).strip()

        usda_clean = re.sub(r'\([^)]*\)', '', usda)
        usda_clean = re.sub(r'\s+', ' ', usda_clean).strip()

        # Tokenize into words
        ing_tokens = set(re.findall(r'\b\w+\b', ing_clean))
        usda_tokens = set(re.findall(r'\b\w+\b', usda_clean))

        if not ing_tokens or not usda_tokens:
            return 0.0

        # Remove common stop words that don't affect food identity
        stop_words = {'from', 'tube', 'the', 'a', 'an', 'of', 'and', 'or'}
        ing_tokens = ing_tokens - stop_words
        usda_tokens = usda_tokens - stop_words

        if not ing_tokens or not usda_tokens:
            return 0.0

        # Extract primary food noun (first 1-2 significant tokens)
        ing_list = re.findall(r'\b\w+\b', ing_clean)
        usda_list = re.findall(r'\b\w+\b', usda_clean)

        # Get head words (first 2 non-stop tokens)
        ing_head = [w for w in ing_list if w not in stop_words][:2]
        usda_head = [w for w in usda_list if w not in stop_words][:2]

        # Core identity scoring: Weighted token overlap
        common_tokens = ing_tokens.intersection(usda_tokens)
        union_tokens = ing_tokens.union(usda_tokens)

        # Jaccard similarity as base score
        jaccard = len(common_tokens) / len(union_tokens) if union_tokens else 0.0

        # Boost for head-word matches (primary food identity)
        head_match_score = 0.0
        if ing_head and usda_head:
            ing_head_set = set(ing_head)
            usda_head_set = set(usda_head)
            head_overlap = ing_head_set.intersection(usda_head_set)
            head_match_score = len(head_overlap) / max(len(ing_head_set), len(usda_head_set))

        # Character-level similarity for close variants (e.g., "vinegar" vs "vinegar")
        char_ing = Counter(ing_clean.replace(' ', ''))
        char_usda = Counter(usda_clean.replace(' ', ''))
        char_common = sum((char_ing & char_usda).values())
        char_total = sum((char_ing | char_usda).values())
        char_sim = char_common / char_total if char_total > 0 else 0.0

        # Penalty for preparation state mismatches
        prep_penalty = 0.0

        # Cooking state indicators
        cooked_terms = {'cooked', 'boiled', 'fried', 'baked', 'roasted', 'grilled'}
        raw_terms = {'raw', 'fresh', 'uncooked'}

        ing_has_cooked = any(term in ing_tokens for term in cooked_terms)
        usda_has_cooked = any(term in usda_tokens for term in cooked_terms)
        ing_has_raw = any(term in ing_tokens for term in raw_terms)
        usda_has_raw = any(term in usda_tokens for term in raw_terms)

        # Penalize cooking state mismatches
        if (ing_has_cooked and usda_has_raw) or (ing_has_raw and usda_has_cooked):
            prep_penalty += 0.3
        elif ing_has_cooked != usda_has_cooked and (ing_has_cooked or usda_has_cooked):
            prep_penalty += 0.2

        # Form/texture indicators
        form_terms = {
            'diced', 'chopped', 'sliced', 'whole', 'shredded', 'ground',
            'paste', 'sauce', 'puree', 'crushed', 'minced'
        }
        ing_forms = ing_tokens.intersection(form_terms)
        usda_forms = usda_tokens.intersection(form_terms)

        # Penalize if forms are mentioned but different
        if ing_forms and usda_forms and not ing_forms.intersection(usda_forms):
            prep_penalty += 0.25
        elif (ing_forms or usda_forms) and not ing_forms.intersection(usda_forms):
            # One specifies form, other doesn't
            prep_penalty += 0.15

        # Liquid/oil qualifiers
        liquid_terms = {'oil', 'sauce', 'paste', 'liquid', 'juice'}
        ing_liquid = ing_tokens.intersection(liquid_terms)
        usda_liquid = usda_tokens.intersection(liquid_terms)

        if ing_liquid != usda_liquid and (ing_liquid or usda_liquid):
            prep_penalty += 0.2

        # Combine scores with weights
        base_score = (
            jaccard * 0.3 +
            head_match_score * 0.5 +
            char_sim * 0.2
        )

        # Apply penalty
        final_score = max(0.0, base_score - prep_penalty)

        # Scale to 0-100 range
        score = final_score * 100.0

        # Add bonus for very high similarity (near-perfect matches)
        if jaccard > 0.7 and head_match_score > 0.8:
            score += 10.0

        # Cap at 100
        score = min(100.0, score)

        return round(score, 2)

    except Exception:
        return 0.0
