import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    """
    Score USDA match substitutability based on modifier and qualifier consistency.
    Variant 3/8: Token-based penalty scoring with discriminating qualifier categories.
    """
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing = ingredient.lower().strip()
        usda = usda_match.lower().strip()

        # Remove gram weights like "200g", "30g"
        ing = re.sub(r'^\d+g?\s*', '', ing)

        # Extract tokens (words) from both strings
        ing_tokens = set(re.findall(r'\b[a-z]+\b', ing))
        usda_tokens = set(re.findall(r'\b[a-z]+\b', usda))

        # Define discriminating qualifier categories
        color_qualifiers = {'red', 'green', 'white', 'yellow', 'black', 'brown', 'orange', 'purple', 'golden'}
        cut_qualifiers = {'diced', 'sliced', 'chopped', 'shredded', 'minced', 'whole', 'crushed', 'ground', 'cubed', 'julienned'}
        fat_qualifiers = {'skim', 'whole', 'lowfat', 'nonfat', 'reduced', 'light', 'fat', 'lean'}
        part_qualifiers = {'breast', 'thigh', 'leg', 'wing', 'drumstick', 'fillet', 'loin', 'rib', 'shoulder'}
        cooking_state = {'raw', 'cooked', 'frozen', 'fresh', 'canned', 'dried', 'roasted', 'grilled', 'fried', 'boiled', 'baked'}
        preparation = {'drained', 'rinsed', 'thawed', 'peeled', 'seeded', 'blanched', 'marinated'}
        sweetness = {'sweet', 'unsweetened', 'sweetened', 'sugar', 'unsalted', 'salted'}
        variety = {'cherry', 'grape', 'roma', 'beefsteak', 'bell', 'jalapeno', 'serrano', 'poblano'}
        form = {'sauce', 'paste', 'oil', 'juice', 'powder', 'flakes', 'chunks', 'pieces'}

        all_qualifiers = (color_qualifiers | cut_qualifiers | fat_qualifiers |
                         part_qualifiers | cooking_state | preparation |
                         sweetness | variety | form)

        # Extract present qualifiers
        ing_quals = ing_tokens & all_qualifiers
        usda_quals = usda_tokens & all_qualifiers

        # Start with base score
        score = 50.0

        # Check for matching qualifiers (reward)
        matches = ing_quals & usda_quals
        score += len(matches) * 8.0

        # Check for contradicting qualifiers (heavy penalty)
        contradictions = 0

        # Color contradictions
        ing_colors = ing_quals & color_qualifiers
        usda_colors = usda_quals & color_qualifiers
        if ing_colors and usda_colors and ing_colors != usda_colors:
            contradictions += 1
            score -= 25.0

        # Cut contradictions
        ing_cuts = ing_quals & cut_qualifiers
        usda_cuts = usda_quals & cut_qualifiers
        if ing_cuts and usda_cuts and ing_cuts != usda_cuts:
            contradictions += 1
            score -= 20.0

        # Fat level contradictions
        ing_fat = ing_quals & fat_qualifiers
        usda_fat = usda_quals & fat_qualifiers
        if ing_fat and usda_fat and ing_fat != usda_fat:
            contradictions += 1
            score -= 22.0

        # Part contradictions (breast vs thigh)
        ing_parts = ing_quals & part_qualifiers
        usda_parts = usda_quals & part_qualifiers
        if ing_parts and usda_parts and ing_parts != usda_parts:
            contradictions += 1
            score -= 28.0

        # Cooking state contradictions (raw vs cooked, drained vs with oil)
        ing_state = ing_quals & cooking_state
        usda_state = usda_quals & cooking_state
        if ing_state and usda_state:
            # Special cases: drained in ingredient but cooked in USDA is bad
            if 'drained' in ing_quals and 'cooked' in usda_state:
                contradictions += 1
                score -= 30.0
            elif ing_state != usda_state and not (ing_state <= usda_state or usda_state <= ing_state):
                contradictions += 1
                score -= 18.0

        # Preparation method contradictions
        ing_prep = ing_quals & preparation
        usda_prep = usda_quals & preparation
        if ing_prep and usda_prep and ing_prep != usda_prep:
            contradictions += 1
            score -= 26.0

        # Form contradictions (sauce vs base ingredient)
        ing_form = ing_quals & form
        usda_form = usda_quals & form
        if ing_form and usda_form and ing_form != usda_form:
            contradictions += 1
            score -= 24.0
        elif ing_form and not usda_form:
            # Ingredient specifies form but USDA doesn't (e.g., tahini sauce vs tahini)
            score -= 15.0

        # Variety contradictions
        ing_var = ing_quals & variety
        usda_var = usda_quals & variety
        if ing_var and usda_var and ing_var != usda_var:
            contradictions += 1
            score -= 20.0
        elif ing_var and not usda_var:
            # Ingredient specifies variety but USDA is generic
            score -= 12.0

        # Sweetness contradictions
        ing_sweet = ing_quals & sweetness
        usda_sweet = usda_quals & sweetness
        if ing_sweet and usda_sweet and ing_sweet != usda_sweet:
            contradictions += 1
            score -= 19.0

        # Bonus for exact qualifier alignment
        if ing_quals and usda_quals and ing_quals == usda_quals:
            score += 15.0

        # Slight penalty if ingredient has many qualifiers but USDA has few
        if len(ing_quals) > len(usda_quals) + 1:
            score -= 8.0

        # Bonus if unspecified qualifiers (no conflict)
        if not ing_quals or not usda_quals:
            if not contradictions:
                score += 5.0

        # Clamp score to reasonable range
        score = max(0.0, min(100.0, score))

        return round(score, 2)

    except Exception:
        return 25.0
