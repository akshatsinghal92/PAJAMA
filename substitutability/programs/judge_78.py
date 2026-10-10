import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        # Remove gram weights like "200g", "30g"
        ingredient = re.sub(r'^\d+g?\s*', '', ingredient)

        # Extract base ingredient (before comma/parentheses)
        ing_base = re.split(r'[,(]', ingredient)[0].strip()
        usda_base = re.split(r',', usda_match)[0].strip()

        # Extract all qualifiers
        ing_qualifiers = extract_qualifiers(ingredient)
        usda_qualifiers = extract_qualifiers(usda_match)

        # Categorize qualifiers
        color_words = {'red', 'green', 'yellow', 'white', 'black', 'brown', 'orange', 'purple', 'pink', 'golden'}
        cut_words = {'diced', 'chopped', 'sliced', 'shredded', 'minced', 'whole', 'halved', 'quartered', 'cubed', 'julienned', 'crushed', 'ground'}
        fat_words = {'skim', 'low-fat', 'whole', 'full-fat', 'reduced-fat', '2%', '1%', 'nonfat', 'lean', 'extra-lean'}
        part_words = {'breast', 'thigh', 'wing', 'leg', 'drumstick', 'tenderloin', 'fillet', 'steak', 'chop', 'rib', 'loin'}
        prep_words = {'raw', 'cooked', 'frozen', 'canned', 'fresh', 'dried', 'roasted', 'baked', 'fried', 'grilled', 'boiled', 'steamed'}
        additive_words = {'with oil', 'with salt', 'with butter', 'with sauce', 'with seasoning', 'unsalted', 'salted', 'unsweetened', 'sweetened'}
        variety_words = {'bell', 'sweet', 'hot', 'cherry', 'roma', 'beefsteak', 'plum', 'grape', 'heirloom'}

        score = 75.0

        # Check color mismatches (critical discriminator)
        ing_colors = ing_qualifiers & color_words
        usda_colors = usda_qualifiers & color_words
        if ing_colors and usda_colors:
            if ing_colors != usda_colors:
                score -= 40.0  # Heavy penalty for color mismatch
            else:
                score += 10.0  # Reward matching colors
        elif ing_colors or usda_colors:
            score += 5.0  # Neutral when one unspecified

        # Check cut mismatches
        ing_cuts = ing_qualifiers & cut_words
        usda_cuts = usda_qualifiers & cut_words
        if ing_cuts and usda_cuts:
            if not ing_cuts & usda_cuts:  # No overlap
                # Special case: shredded/raw can be compatible
                if not (('shredded' in ing_cuts and 'raw' in usda_qualifiers) or
                        ('raw' in ing_qualifiers and any(c in usda_cuts for c in ['shredded', 'chopped']))):
                    score -= 25.0
            else:
                score += 8.0

        # Check fat level mismatches
        ing_fat = ing_qualifiers & fat_words
        usda_fat = usda_qualifiers & fat_words
        if ing_fat and usda_fat and ing_fat != usda_fat:
            score -= 35.0  # Noticeable difference
        elif ing_fat == usda_fat and ing_fat:
            score += 12.0

        # Check part mismatches (breast vs thigh matters)
        ing_parts = ing_qualifiers & part_words
        usda_parts = usda_qualifiers & part_words
        if ing_parts and usda_parts and ing_parts != usda_parts:
            score -= 38.0  # Very noticeable
        elif ing_parts == usda_parts and ing_parts:
            score += 10.0

        # Check preparation state mismatches
        ing_prep = ing_qualifiers & prep_words
        usda_prep = usda_qualifiers & prep_words

        # Critical: raw vs cooked is a deal-breaker
        if ('raw' in ing_prep and 'cooked' in usda_prep) or ('cooked' in ing_prep and 'raw' in usda_prep):
            score -= 45.0
        elif ('frozen' in ing_prep and 'fresh' in usda_prep) or ('fresh' in ing_prep and 'frozen' in usda_prep):
            score -= 15.0  # Less critical
        elif ing_prep == usda_prep and ing_prep:
            score += 8.0

        # Check additive mismatches (with oil, with salt, etc.)
        ing_add = extract_phrase_qualifiers(ingredient, additive_words)
        usda_add = extract_phrase_qualifiers(usda_match, additive_words)

        # Drained ingredient should not match "with oil" or "with salt"
        if 'drained' in ingredient:
            if any(phrase in usda_match for phrase in ['with oil', 'with butter', 'with salt']):
                score -= 50.0  # Very bad match

        # Check for additive contradictions
        if 'unsalted' in ingredient and 'salted' in usda_match:
            score -= 30.0
        elif 'salted' in ingredient and 'unsalted' in usda_match:
            score -= 30.0
        elif 'unsweetened' in ingredient and 'sweetened' in usda_match:
            score -= 30.0

        # Check variety mismatches
        ing_variety = ing_qualifiers & variety_words
        usda_variety = usda_qualifiers & variety_words
        if ing_variety and usda_variety and ing_variety != usda_variety:
            score -= 28.0
        elif ing_variety == usda_variety and ing_variety:
            score += 9.0

        # Sauce vs base ingredient penalty
        if 'sauce' in ingredient and 'sauce' not in usda_match:
            score -= 42.0
        elif 'paste' in ingredient and 'paste' not in usda_match:
            score -= 35.0

        # Overall qualifier density bonus
        total_qualifiers = len(ing_qualifiers | usda_qualifiers)
        matching_qualifiers = len(ing_qualifiers & usda_qualifiers)
        if total_qualifiers > 0:
            match_ratio = matching_qualifiers / total_qualifiers
            score += match_ratio * 15.0

        # Penalize if USDA has many more qualifiers (over-specified)
        if len(usda_qualifiers) > len(ing_qualifiers) + 3:
            score -= 10.0

        # Clamp score to 0-100 range
        return max(0.0, min(100.0, score))

    except Exception:
        return 50.0

def extract_qualifiers(text):
    """Extract individual qualifier words from text."""
    # Remove punctuation and split into words
    words = re.findall(r'\b[a-z]+\b', text)
    # Filter out common non-qualifier words
    stop_words = {'the', 'and', 'or', 'from', 'with', 'without', 'for', 'of', 'in', 'on', 'at', 'to', 'a', 'an'}
    return set(w for w in words if w not in stop_words and len(w) > 1)

def extract_phrase_qualifiers(text, phrase_set):
    """Extract multi-word phrases from text that match items in phrase_set."""
    found = set()
    for phrase in phrase_set:
        if phrase in text:
            found.add(phrase)
    return found
