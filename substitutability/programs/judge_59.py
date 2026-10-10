import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        # Remove gram weights (e.g., "300g", "40 g")
        ingredient = re.sub(r'^\d+\s*g\s+', '', ingredient)
        ingredient = re.sub(r'^\d+\s*g\b', '', ingredient)

        # Extract parenthetical content separately to check context
        ing_parens = re.findall(r'\(([^)]+)\)', ingredient)
        usda_parens = re.findall(r'\(([^)]+)\)', usda_match)

        # Remove parentheticals for main comparison
        ingredient_clean = re.sub(r'\([^)]+\)', '', ingredient).strip()
        usda_clean = re.sub(r'\([^)]+\)', '', usda_match).strip()

        # Split on commas to get all descriptors
        ing_tokens = set(re.findall(r'\w+', ingredient_clean))
        usda_tokens = set(re.findall(r'\w+', usda_clean))

        # Category 1: Heavy additives/compounds (most severe penalty)
        heavy_additives = {
            'sauce', 'seasoned', 'marinated', 'breaded', 'battered',
            'sweetened', 'flavored', 'spiced', 'glazed', 'frosted',
            'creamed', 'buttered', 'sugared', 'candied', 'honey'
        }

        # Category 2: Moderate additives (medium penalty)
        moderate_additives = {
            'salted', 'seasoning', 'blend', 'mix', 'prepared',
            'processed', 'enriched', 'fortified', 'mixed'
        }

        # Category 3: Processing state changes (light-medium penalty)
        processing_states = {
            'cooked', 'fried', 'baked', 'roasted', 'grilled',
            'boiled', 'steamed', 'toasted', 'smoked'
        }

        # Category 4: Added ingredients (medium-heavy penalty)
        added_ingredients = {
            'with', 'added', 'plus', 'oil', 'butter', 'salt',
            'sugar', 'cream', 'cheese', 'garlic', 'onion'
        }

        # Start with base score
        score = 100.0

        # Check for heavy additives in USDA but not in ingredient
        heavy_in_usda = heavy_additives & usda_tokens
        heavy_in_ing = heavy_additives & ing_tokens
        heavy_asymmetry = heavy_in_usda - heavy_in_ing
        score -= len(heavy_asymmetry) * 35.0

        # Check for moderate additives
        mod_in_usda = moderate_additives & usda_tokens
        mod_in_ing = moderate_additives & ing_tokens
        mod_asymmetry = mod_in_usda - mod_in_ing
        score -= len(mod_asymmetry) * 20.0

        # Check for processing state mismatches
        proc_in_usda = processing_states & usda_tokens
        proc_in_ing = processing_states & ing_tokens

        # Special handling: if ingredient mentions prep states, USDA should match
        if proc_in_ing and not proc_in_usda:
            score -= 15.0
        elif proc_in_usda and not proc_in_ing:
            # USDA has processing not mentioned in ingredient
            score -= 25.0

        # Check for "with" pattern indicating added components
        if 'with' in usda_clean and 'with' not in ingredient_clean:
            # Extract what comes after "with"
            with_match = re.search(r'with\s+(\w+)', usda_clean)
            if with_match:
                added_item = with_match.group(1)
                if added_item not in ingredient_clean:
                    score -= 30.0

        # Check for added ingredients keywords
        added_in_usda = added_ingredients & usda_tokens
        added_in_ing = added_ingredients & ing_tokens
        added_asymmetry = added_in_usda - added_in_ing
        score -= len(added_asymmetry) * 18.0

        # Bonus: reward high overlap of core food terms
        # Exclude common modifiers
        exclude_words = {
            'canned', 'fresh', 'frozen', 'dried', 'raw', 'whole',
            'diced', 'chopped', 'sliced', 'shredded', 'ground',
            'the', 'and', 'or', 'from', 'in', 'on', 'at'
        }

        core_ing = ing_tokens - heavy_additives - moderate_additives - processing_states - exclude_words - added_ingredients
        core_usda = usda_tokens - heavy_additives - moderate_additives - processing_states - exclude_words - added_ingredients

        if core_usda and core_ing:
            overlap = len(core_ing & core_usda)
            union = len(core_ing | core_usda)
            if union > 0:
                jaccard = overlap / union
                score += jaccard * 15.0

        # Detect compound vs simple mismatch
        # If ingredient is simple (1-2 words) but USDA is complex (4+ descriptors), penalize
        ing_word_count = len([w for w in ing_tokens if len(w) > 2])
        usda_word_count = len([w for w in usda_tokens if len(w) > 2])

        if ing_word_count <= 2 and usda_word_count >= 5:
            score -= 12.0

        # Clamp score to 0-100 range
        score = max(0.0, min(100.0, score))

        return round(score, 2)

    except Exception:
        return 50.0
