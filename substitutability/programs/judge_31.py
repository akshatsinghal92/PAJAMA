import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        if not ingredient or not usda_match:
            return 0.0

        # Clean ingredient: remove gram weights, parentheticals
        ing_clean = re.sub(r'^\d+g?\s*', '', ingredient)
        ing_clean = re.sub(r'\([^)]*\)', '', ing_clean)
        ing_clean = re.sub(r'\s+', ' ', ing_clean).strip()

        # Extract core nouns (strip common prep/state words)
        prep_words = {
            'frozen', 'thawed', 'fresh', 'raw', 'cooked', 'boiled', 'steamed',
            'fried', 'baked', 'roasted', 'grilled', 'diced', 'chopped', 'sliced',
            'shredded', 'minced', 'ground', 'crushed', 'canned', 'dried', 'drained',
            'rinsed', 'whole', 'halved', 'quartered'
        }

        def extract_core(text):
            tokens = text.replace(',', ' ').split()
            core = [t for t in tokens if t not in prep_words and len(t) > 2]
            return ' '.join(core)

        ing_core = extract_core(ing_clean)
        usda_core = extract_core(usda_match)

        # Macro category keywords (nutritional profile signatures)
        pure_fats = {'oil', 'butter', 'lard', 'ghee', 'shortening', 'margarine'}
        lean_proteins = {'chicken breast', 'turkey breast', 'cod', 'tilapia', 'tuna',
                        'shrimp', 'tofu', 'egg whites', 'cottage cheese'}
        fatty_proteins = {'beef', 'pork', 'salmon', 'mackerel', 'sausage', 'bacon',
                         'lamb', 'duck', 'sardines'}
        dairy_fats = {'cheese', 'cream', 'yogurt', 'milk', 'sour cream'}
        refined_carbs = {'pasta', 'rice', 'bread', 'flour', 'noodles', 'couscous',
                        'quinoa', 'cereal', 'oats', 'granola'}
        starchy_veg = {'potato', 'corn', 'peas', 'sweet potato', 'yam', 'squash'}
        low_cal_veg = {'lettuce', 'spinach', 'kale', 'cabbage', 'broccoli', 'cauliflower',
                      'cucumber', 'celery', 'zucchini', 'asparagus', 'green beans'}
        fruits = {'apple', 'banana', 'orange', 'berry', 'grape', 'melon', 'peach',
                 'pear', 'mango', 'pineapple', 'cherry', 'tomato'}
        condiments = {'sauce', 'vinegar', 'mustard', 'ketchup', 'mayo', 'dressing',
                     'paste', 'salsa'}
        spices = {'salt', 'pepper', 'paprika', 'cumin', 'coriander', 'turmeric',
                 'cinnamon', 'ginger', 'garlic powder', 'onion powder', 'basil',
                 'oregano', 'thyme', 'rosemary'}
        nuts_seeds = {'almond', 'walnut', 'peanut', 'cashew', 'pecan', 'sesame',
                     'tahini', 'sunflower', 'pumpkin seed'}

        def get_macro_category(text):
            categories = []
            if any(f in text for f in pure_fats):
                categories.append('pure_fat')
            if any(p in text for p in lean_proteins):
                categories.append('lean_protein')
            if any(p in text for p in fatty_proteins):
                categories.append('fatty_protein')
            if any(d in text for d in dairy_fats):
                categories.append('dairy_fat')
            if any(c in text for c in refined_carbs):
                categories.append('refined_carb')
            if any(s in text for s in starchy_veg):
                categories.append('starchy_veg')
            if any(v in text for v in low_cal_veg):
                categories.append('low_cal_veg')
            if any(f in text for f in fruits):
                categories.append('fruit')
            if any(c in text for c in condiments):
                categories.append('condiment')
            if any(s in text for s in spices):
                categories.append('spice')
            if any(n in text for n in nuts_seeds):
                categories.append('nut_seed_fat')
            return set(categories)

        ing_cats = get_macro_category(ing_clean)
        usda_cats = get_macro_category(usda_match)

        # Detect preparation state mismatches that change macros
        ing_raw = 'raw' in ing_clean or 'fresh' in ing_clean
        ing_cooked = any(w in ing_clean for w in ['cooked', 'boiled', 'fried', 'baked', 'roasted'])
        ing_drained = 'drained' in ing_clean
        ing_with_oil = 'with oil' in ing_clean or 'in oil' in ing_clean

        usda_raw = 'raw' in usda_match or 'fresh' in usda_match
        usda_cooked = any(w in usda_match for w in ['cooked', 'boiled', 'fried', 'baked', 'roasted'])
        usda_drained = 'drained' in usda_match
        usda_with_oil = 'with oil' in usda_match or 'in oil' in usda_match

        # Check if ingredient is a modified form (sauce/paste vs base)
        ing_is_processed = any(w in ing_clean for w in ['sauce', 'paste', 'dressing', 'spread'])
        usda_is_base = not any(w in usda_match for w in ['sauce', 'paste', 'dressing', 'spread'])

        # Scoring
        score = 50.0

        # Category matching (core nutritional profile)
        if ing_cats and usda_cats:
            overlap = len(ing_cats & usda_cats)
            total = len(ing_cats | usda_cats)
            if total > 0:
                category_sim = overlap / total
                score += category_sim * 30
        elif not ing_cats and not usda_cats:
            score += 15

        # Core food matching
        ing_tokens = set(ing_core.split())
        usda_tokens = set(usda_core.split())

        if ing_tokens and usda_tokens:
            core_overlap = len(ing_tokens & usda_tokens)
            core_total = max(len(ing_tokens), len(usda_tokens))
            if core_total > 0:
                core_sim = core_overlap / core_total
                score += core_sim * 25

        # Penalize preparation state mismatches
        prep_mismatch = False

        # Raw vs cooked changes macros (water loss)
        if (ing_raw and usda_cooked) or (ing_cooked and usda_raw):
            if 'refined_carb' in ing_cats or 'refined_carb' in usda_cats:
                score -= 40
                prep_mismatch = True

        # Drained vs with oil is a huge macro change
        if (ing_drained and usda_with_oil) or (ing_with_oil and usda_drained):
            score -= 35
            prep_mismatch = True

        # Sauce/paste vs base ingredient (different macros)
        if ing_is_processed and usda_is_base:
            score -= 30
            prep_mismatch = True

        # Reward exact or near-exact matches
        similarity = 0.0
        ing_words = ing_clean.replace(',', ' ').split()
        usda_words = usda_match.replace(',', ' ').split()

        ing_set = set(ing_words)
        usda_set = set(usda_words)

        if ing_set and usda_set:
            shared = len(ing_set & usda_set)
            total = len(ing_set | usda_set)
            if total > 0:
                similarity = shared / total
                if similarity > 0.7:
                    score += 15

        # Clamp to reasonable range
        score = max(0.0, min(100.0, score))

        return round(score, 2)

    except Exception:
        return 50.0
