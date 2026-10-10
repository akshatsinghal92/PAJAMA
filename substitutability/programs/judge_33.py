import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing = ingredient.lower().strip()
        usda = usda_match.lower().strip()

        # Remove gram weights (e.g., "200g")
        ing = re.sub(r'^\d+g?\s*', '', ing)

        # Remove parentheticals from ingredient
        ing = re.sub(r'\([^)]*\)', '', ing)

        # Split on commas to get qualifiers
        ing_parts = [p.strip() for p in ing.split(',')]
        usda_parts = [p.strip() for p in usda.split(',')]

        # Extract main terms (first part) and qualifiers
        ing_main = ing_parts[0] if ing_parts else ""
        usda_main = usda_parts[0] if usda_parts else ""

        ing_quals = set(ing_parts[1:]) if len(ing_parts) > 1 else set()
        usda_quals = set(usda_parts[1:]) if len(usda_parts) > 1 else set()

        # Extract key words from main terms
        ing_words = set(re.findall(r'\b\w+\b', ing_main))
        usda_words = set(re.findall(r'\b\w+\b', usda_main))

        # Preparation states that are acceptable to ignore
        prep_terms = {
            'shredded', 'chopped', 'diced', 'sliced', 'minced', 'crushed',
            'ground', 'grated', 'peeled', 'trimmed', 'thawed', 'frozen',
            'drained', 'rinsed'
        }

        # States that matter for substitutability
        important_states = {
            'cooked', 'raw', 'roasted', 'fried', 'baked', 'boiled',
            'canned', 'fresh', 'dried', 'smoked', 'pickled', 'fermented'
        }

        # Specific variants that matter
        specific_variants = {
            'penne', 'spaghetti', 'fusilli', 'rigatoni', 'fettuccine',
            'cherry', 'grape', 'plum', 'roma', 'beefsteak',
            'whole', 'diced', 'crushed', 'stewed', 'pureed',
            'extra virgin', 'virgin', 'light', 'dark', 'white',
            'table', 'sea', 'kosher', 'himalayan',
            'sauce', 'paste', 'powder', 'oil', 'butter'
        }

        score = 50.0  # Start at neutral

        # Check for core food match
        ing_core = ing_words - prep_terms
        usda_core = usda_words - prep_terms

        overlap = len(ing_core & usda_core)
        if overlap == 0:
            return 20.0  # Poor match

        # Reward overlap in core terms
        score += overlap * 5

        # Check for important state mismatches
        ing_states = ing_words & important_states
        usda_states = usda_words & important_states
        ing_qual_states = set()
        for q in ing_quals:
            ing_qual_states.update(re.findall(r'\b\w+\b', q))
        ing_qual_states &= important_states
        all_ing_states = ing_states | ing_qual_states

        usda_qual_states = set()
        for q in usda_quals:
            usda_qual_states.update(re.findall(r'\b\w+\b', q))
        usda_qual_states &= important_states
        all_usda_states = usda_states | usda_qual_states

        # Penalize added important states not in ingredient
        added_states = all_usda_states - all_ing_states
        if added_states:
            score -= len(added_states) * 15

        # Penalize removed important states from ingredient
        removed_states = all_ing_states - all_usda_states
        if removed_states:
            score -= len(removed_states) * 15

        # Check for specific variant mismatches
        ing_variants = ing_words & specific_variants
        usda_variants = usda_words & specific_variants

        # Also check in qualifiers
        for q in ing_quals:
            ing_variants.update(set(re.findall(r'\b\w+\b', q)) & specific_variants)
        for q in usda_quals:
            usda_variants.update(set(re.findall(r'\b\w+\b', q)) & specific_variants)

        # If ingredient specifies a variant, USDA should match it
        if ing_variants:
            if usda_variants & ing_variants:
                score += 10  # Good: variant preserved
            else:
                score -= 20  # Bad: specific variant lost
        else:
            # Ingredient is unqualified - prefer generic USDA entry
            if usda_variants:
                score -= 10  # Penalize adding specificity
            else:
                score += 5  # Reward staying general

        # Check qualifier alignment
        if ing_quals and not usda_quals:
            # Ingredient has qualifiers but USDA doesn't - might be dropping info
            non_prep_ing_quals = [q for q in ing_quals if not any(p in q for p in prep_terms)]
            if non_prep_ing_quals:
                score -= 10

        if usda_quals and not ing_quals:
            # USDA adds qualifiers not in ingredient
            non_prep_usda_quals = [q for q in usda_quals if not any(p in q for p in prep_terms)]
            if non_prep_usda_quals:
                score -= 8

        # Bonus for very close matches
        if ing_main == usda_main or ing_core == usda_core:
            score += 15

        # Clamp score to reasonable range
        return max(0.0, min(100.0, score))

    except Exception:
        return 25.0
