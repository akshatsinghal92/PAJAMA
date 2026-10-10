import re

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ing_clean = normalize_text(ingredient)
        usda_clean = normalize_text(usda_match)

        if not ing_clean or not usda_clean:
            return 0.0

        ing_core = extract_core_food(ing_clean)
        usda_core = extract_core_food(usda_clean)

        if not ing_core or not usda_core:
            return 10.0

        base_score = compute_lcs_similarity(ing_core, usda_core) * 100

        state_penalty = detect_state_conflict(ing_clean, usda_clean)
        form_penalty = detect_form_conflict(ing_clean, usda_clean)
        modifier_penalty = detect_modifier_conflict(ing_clean, usda_clean)

        final_score = max(0.0, base_score - state_penalty - form_penalty - modifier_penalty)

        return final_score

    except Exception:
        return 5.0


def normalize_text(text):
    text = re.sub(r'\b\d+g\b', '', text)
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'[,;:]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text.lower()


def extract_core_food(text):
    stopwords = {
        'frozen', 'canned', 'fresh', 'cooked', 'raw', 'uncooked', 'drained',
        'thawed', 'dried', 'ground', 'whole', 'diced', 'chopped', 'shredded',
        'sliced', 'crushed', 'minced', 'grated', 'from', 'with', 'tube',
        'jar', 'can', 'oil', 'table', 'spices'
    }

    words = text.split()
    core_words = [w for w in words if w not in stopwords and len(w) > 1]

    return ' '.join(core_words[:4])


def compute_lcs_similarity(s1, s2):
    if not s1 or not s2:
        return 0.0

    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    lcs_len = dp[m][n]
    max_len = max(m, n)

    return lcs_len / max_len if max_len > 0 else 0.0


def detect_state_conflict(ing, usda):
    penalty = 0.0

    cooked_indicators = ['cooked', 'boiled', 'fried', 'baked', 'roasted', 'grilled', 'sauteed']
    raw_indicators = ['raw', 'uncooked', 'fresh']

    ing_cooked = any(word in ing for word in cooked_indicators)
    usda_cooked = any(word in usda for word in cooked_indicators)
    ing_raw = any(word in ing for word in raw_indicators)
    usda_raw = any(word in usda for word in raw_indicators)

    if ing_cooked and usda_raw:
        penalty += 35.0
    elif ing_raw and usda_cooked:
        penalty += 35.0
    elif (not ing_cooked and usda_cooked) and ('pasta' in ing or 'noodle' in ing):
        penalty += 45.0

    return penalty


def detect_form_conflict(ing, usda):
    penalty = 0.0

    form_descriptors = {
        'diced': 5, 'whole': 5, 'shredded': 3, 'sliced': 4,
        'chopped': 4, 'crushed': 4, 'minced': 4, 'paste': 7,
        'sauce': 7, 'puree': 6, 'chunks': 5, 'pieces': 5
    }

    ing_forms = {form: weight for form, weight in form_descriptors.items() if form in ing}
    usda_forms = {form: weight for form, weight in form_descriptors.items() if form in usda}

    if ing_forms and not any(f in usda_forms for f in ing_forms):
        max_weight = max(ing_forms.values())
        penalty += max_weight * 3.5

    if 'sauce' in ing and 'sauce' not in usda:
        penalty += 30.0
    elif 'paste' in ing and 'paste' not in usda:
        penalty += 25.0

    return penalty


def detect_modifier_conflict(ing, usda):
    penalty = 0.0

    if 'drained' in ing and 'with' in usda:
        penalty += 25.0

    if 'with oil' in usda and 'drained' in ing:
        penalty += 20.0

    if 'cherry' in ing and 'cherry' not in usda and 'tomato' in ing:
        penalty += 15.0

    if ('penne' in ing or 'spaghetti' in ing or 'rigatoni' in ing) and 'pasta' in usda:
        if 'cooked' in usda:
            penalty += 30.0

    return penalty
