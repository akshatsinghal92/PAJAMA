import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        if not ingredient or not usda_match:
            return 0.0

        # Remove gram weights from ingredient
        ingredient_clean = re.sub(r'^\d+g?\s*', '', ingredient)

        # Extract preparation state markers
        ing_states = extract_states(ingredient_clean)
        usda_states = extract_states(usda_match)

        # Extract core food terms
        ing_core = extract_core_food(ingredient_clean)
        usda_core = extract_core_food(usda_match)

        # Assign macro classes
        ing_macro_class = assign_macro_class(ing_core, ing_states)
        usda_macro_class = assign_macro_class(usda_core, usda_states)

        # Calculate base score from macro class alignment
        macro_score = calculate_macro_alignment(ing_macro_class, usda_macro_class)

        # Calculate state consistency penalty
        state_penalty = calculate_state_penalty(ing_states, usda_states)

        # Calculate form consistency bonus (sauce vs base, cooked vs raw)
        form_score = calculate_form_consistency(ingredient_clean, usda_match, ing_states, usda_states)

        # Core food term overlap
        overlap_score = calculate_term_overlap(ing_core, usda_core)

        # Final score: weighted combination
        final_score = (
            macro_score * 0.35 +
            form_score * 0.30 +
            overlap_score * 0.25 +
            (100 - state_penalty) * 0.10
        )

        return max(0.0, min(100.0, final_score))

    except Exception:
        return 50.0


def extract_states(text):
    states = set()
    state_markers = {
        'cooked', 'raw', 'frozen', 'canned', 'dried', 'fresh', 'thawed',
        'drained', 'undrained', 'with oil', 'with butter', 'with salt',
        'uncooked', 'baked', 'fried', 'boiled', 'steamed', 'roasted',
        'ground', 'whole', 'chopped', 'diced', 'shredded', 'sliced'
    }

    for marker in state_markers:
        if marker in text:
            states.add(marker)

    return states


def extract_core_food(text):
    # Remove parentheticals
    text = re.sub(r'\([^)]*\)', '', text)
    # Remove common prep phrases
    text = re.sub(r',.*', '', text)

    # Extract key food words
    stop_words = {'the', 'a', 'an', 'from', 'with', 'of', 'for', 'in', 'to'}
    words = re.findall(r'\b[a-z]+\b', text)
    core_words = [w for w in words if w not in stop_words and len(w) > 2]

    return ' '.join(core_words[:5])  # First 5 meaningful words


def assign_macro_class(food_text, states):
    # Macro classes based on typical nutritional profiles
    pure_fats = ['oil', 'butter', 'lard', 'shortening', 'ghee']
    lean_proteins = ['chicken breast', 'turkey breast', 'fish', 'cod', 'tilapia', 'shrimp', 'egg white']
    fatty_proteins = ['salmon', 'beef', 'pork', 'lamb', 'egg']
    dairy = ['milk', 'cheese', 'yogurt', 'cream', 'sour cream']
    leafy_greens = ['spinach', 'lettuce', 'kale', 'arugula', 'cabbage', 'chard']
    starchy_carbs = ['pasta', 'rice', 'bread', 'potato', 'corn', 'oat']
    legumes = ['bean', 'lentil', 'chickpea', 'pea']
    nuts_seeds = ['almond', 'walnut', 'peanut', 'sesame', 'tahini', 'cashew']
    condiments = ['sauce', 'paste', 'vinegar', 'mustard', 'ketchup', 'mayo']
    spices = ['salt', 'pepper', 'spice', 'garlic powder', 'onion powder']
    sugars = ['sugar', 'honey', 'syrup', 'molasses']

    classes = []

    # Check each category
    if any(f in food_text for f in pure_fats):
        classes.append('pure_fat')
    if any(f in food_text for f in lean_proteins):
        classes.append('lean_protein')
    if any(f in food_text for f in fatty_proteins):
        classes.append('fatty_protein')
    if any(f in food_text for f in dairy):
        classes.append('dairy')
    if any(f in food_text for f in leafy_greens):
        classes.append('leafy_green')
    if any(f in food_text for f in starchy_carbs):
        classes.append('starchy_carb')
    if any(f in food_text for f in legumes):
        classes.append('legume')
    if any(f in food_text for f in nuts_seeds):
        classes.append('nut_seed')
    if any(f in food_text for f in condiments):
        classes.append('condiment')
    if any(f in food_text for f in spices):
        classes.append('spice')
    if any(f in food_text for f in sugars):
        classes.append('sugar')

    return classes if classes else ['unknown']


def calculate_macro_alignment(ing_classes, usda_classes):
    if not ing_classes or not usda_classes:
        return 50.0

    # Calculate intersection
    ing_set = set(ing_classes)
    usda_set = set(usda_classes)

    if ing_set & usda_set:
        # Direct overlap
        overlap_ratio = len(ing_set & usda_set) / max(len(ing_set), len(usda_set))
        return 70.0 + overlap_ratio * 30.0

    # Check compatible classes (would have similar macros)
    compatible_pairs = {
        frozenset(['lean_protein', 'fatty_protein']),
        frozenset(['nut_seed', 'pure_fat']),
        frozenset(['starchy_carb', 'legume']),
        frozenset(['spice', 'condiment'])
    }

    for pair in compatible_pairs:
        if ing_set & pair and usda_set & pair:
            return 60.0

    # Incompatible classes (very different macros)
    incompatible = [
        ('pure_fat', 'lean_protein'),
        ('pure_fat', 'leafy_green'),
        ('sugar', 'lean_protein'),
        ('spice', 'starchy_carb'),
        ('condiment', 'leafy_green')
    ]

    for ing_c in ing_classes:
        for usda_c in usda_classes:
            if (ing_c, usda_c) in incompatible or (usda_c, ing_c) in incompatible:
                return 20.0

    return 40.0


def calculate_state_penalty(ing_states, usda_states):
    # Heavy penalty for critical mismatches
    critical_conflicts = [
        ('drained', 'with oil'),
        ('drained', 'with butter'),
        ('raw', 'cooked'),
        ('cooked', 'raw'),
        ('frozen', 'cooked'),
        ('fresh', 'canned')
    ]

    for ing_state in ing_states:
        for usda_state in usda_states:
            if (ing_state, usda_state) in critical_conflicts:
                return 60.0

    # Moderate penalty for any state mismatch
    if ing_states and usda_states and not (ing_states & usda_states):
        return 30.0

    return 0.0


def calculate_form_consistency(ingredient, usda_match, ing_states, usda_states):
    # Check for form mismatches that affect nutrition

    # Sauce/paste vs base ingredient
    if 'sauce' in ingredient and 'sauce' not in usda_match:
        return 20.0
    if 'paste' in ingredient and 'paste' not in usda_match:
        return 25.0

    # Cooked state mismatch for carbs (big calorie difference)
    carb_indicators = ['pasta', 'rice', 'noodle', 'grain']
    is_carb = any(c in ingredient or c in usda_match for c in carb_indicators)

    if is_carb:
        ing_cooked = 'cooked' in ing_states or 'cooked' in ingredient
        usda_cooked = 'cooked' in usda_states or 'cooked' in usda_match

        if ing_cooked != usda_cooked:
            return 15.0

    # Check for good matches
    core_match_patterns = [
        (r'\bvinegar\b.*\bvinegar\b', 90.0),
        (r'\bsalt\b.*\bsalt\b', 95.0),
        (r'\boil\b.*\boil\b', 85.0),
        (r'\bsauce\b.*\bsauce\b', 80.0)
    ]

    combined = ingredient + ' ' + usda_match
    for pattern, score in core_match_patterns:
        if re.search(pattern, combined):
            return score

    # Default moderate score
    return 60.0


def calculate_term_overlap(ing_core, usda_core):
    if not ing_core or not usda_core:
        return 40.0

    ing_words = set(ing_core.split())
    usda_words = set(usda_core.split())

    if not ing_words or not usda_words:
        return 40.0

    overlap = ing_words & usda_words

    if not overlap:
        return 20.0

    # Jaccard similarity
    jaccard = len(overlap) / len(ing_words | usda_words)

    return 30.0 + jaccard * 70.0
