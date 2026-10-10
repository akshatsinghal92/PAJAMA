import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        # Remove gram weights like "200g", "30g" from ingredient
        ingredient = re.sub(r'^\d+g?\s*', '', ingredient)

        # Extract core food name (before comma/parentheses)
        def get_core_name(text):
            # Remove parentheses content
            text = re.sub(r'\([^)]*\)', '', text)
            # Get text before comma
            text = text.split(',')[0].strip()
            return text

        ing_core = get_core_name(ingredient)
        usda_core = get_core_name(usda_match)

        # Define culinary state markers that affect functional role
        # These are grouped by whether they're compatible or not
        state_markers = {
            'preparation_state': ['raw', 'cooked', 'baked', 'fried', 'grilled', 'roasted', 'steamed', 'boiled'],
            'moisture_state': ['drained', 'with liquid', 'in water', 'in oil', 'dry', 'dried'],
            'processing_state': ['fresh', 'frozen', 'canned', 'jarred', 'bottled'],
            'form_state': ['whole', 'diced', 'chopped', 'minced', 'shredded', 'sliced', 'ground', 'paste', 'sauce', 'powder'],
            'enhancement': ['with oil', 'with butter', 'with salt', 'seasoned', 'unseasoned', 'plain']
        }

        def extract_states(text):
            states = defaultdict(list)
            for category, markers in state_markers.items():
                for marker in markers:
                    if marker in text:
                        states[category].append(marker)
            return states

        ing_states = extract_states(ingredient)
        usda_states = extract_states(usda_match)

        # Start with base score from core name similarity
        score = 50.0

        # Check core food match
        ing_words = set(ing_core.split())
        usda_words = set(usda_core.split())

        # Remove common stop words that don't affect culinary role
        stop_words = {'the', 'a', 'an', 'and', 'or', 'with', 'from', 'to'}
        ing_words -= stop_words
        usda_words -= stop_words

        if not ing_words or not usda_words:
            return 20.0

        # Core food overlap ratio
        overlap = len(ing_words & usda_words)
        union = len(ing_words | usda_words)
        if union > 0:
            core_match = overlap / union
            score += core_match * 40

        # Critical state mismatch penalties
        # These are states that fundamentally change culinary role
        critical_mismatches = 0

        # Preparation state mismatch (raw vs cooked is critical)
        ing_prep = ing_states['preparation_state']
        usda_prep = usda_states['preparation_state']
        if ing_prep or usda_prep:
            if ing_prep and usda_prep:
                # Both specify prep state - must match
                if not any(p in usda_prep for p in ing_prep):
                    critical_mismatches += 2
            elif ing_prep and not usda_prep:
                # Ingredient specifies prep but USDA doesn't (ambiguous)
                critical_mismatches += 0.5
            elif usda_prep and not ing_prep:
                # USDA specifies prep but ingredient doesn't
                if 'cooked' in usda_prep:
                    critical_mismatches += 1.5

        # Moisture state mismatch (drained vs with oil/liquid)
        ing_moist = ing_states['moisture_state']
        usda_moist = usda_states['moisture_state']
        if 'drained' in ing_moist and any(x in usda_moist for x in ['with oil', 'in oil', 'with liquid']):
            critical_mismatches += 2
        if any(x in ing_moist for x in ['with oil', 'in oil']) and 'drained' in usda_moist:
            critical_mismatches += 2

        # Form state critical for function (sauce vs base, paste vs whole)
        ing_form = ing_states['form_state']
        usda_form = usda_states['form_state']

        # Sauce/paste vs base ingredient is critical
        ing_has_sauce = 'sauce' in ing_form or 'paste' in ing_form
        usda_has_sauce = 'sauce' in usda_form or 'paste' in usda_form
        if ing_has_sauce != usda_has_sauce:
            critical_mismatches += 2

        # Ground vs whole matters for some ingredients
        if 'ground' in ing_form and 'whole' in usda_form:
            critical_mismatches += 1
        if 'whole' in ing_form and 'ground' in usda_form:
            critical_mismatches += 1

        # Physical form changes (chopped/shredded vs whole) - moderate impact
        physical_forms = {'chopped', 'diced', 'minced', 'shredded', 'sliced'}
        ing_physical = [f for f in ing_form if f in physical_forms]
        usda_physical = [f for f in usda_form if f in physical_forms]

        # If ingredient has physical prep and USDA is whole, mild penalty
        if ing_physical and 'whole' in usda_form:
            critical_mismatches += 0.5

        # Enhancement mismatches (with oil, seasoned, etc.)
        ing_enh = ing_states['enhancement']
        usda_enh = usda_states['enhancement']
        if ing_enh != usda_enh:
            if ing_enh and usda_enh:
                # Both have enhancements but different
                if not any(e in usda_enh for e in ing_enh):
                    critical_mismatches += 1.5
            elif usda_enh and not ing_enh:
                # USDA has enhancement ingredient doesn't
                critical_mismatches += 1

        # Apply penalties
        score -= critical_mismatches * 15

        # Bonus for processing state compatibility
        ing_proc = ing_states['processing_state']
        usda_proc = usda_states['processing_state']
        if ing_proc and usda_proc:
            if any(p in usda_proc for p in ing_proc):
                score += 10
        elif not ing_proc and not usda_proc:
            # Neither specifies, likely compatible
            score += 5

        # Special case bonuses for very clear matches
        if ing_core == usda_core and critical_mismatches == 0:
            score += 20

        # Ensure score is in reasonable range
        score = max(0.0, min(100.0, score))

        return round(score, 2)

    except Exception:
        return 30.0
