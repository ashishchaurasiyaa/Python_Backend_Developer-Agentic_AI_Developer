"""
30 recipes, built only from the user's actual pantry + kitchen equipment
(induction, pressure cooker, grinder, tawa, kadhai — no oven).

Each recipe's macros are NOT hand-typed: `recipes_agent.py` and
`meal_plan_agent.py` both compute them from `data/foods.py` via
`sum_macros(ingredients)`, so recipe macros and meal-plan macros can never
drift out of sync with each other.

`ingredients`: list of (food_key, grams, display_string) — food_key must
exist in data.foods.FOOD_DB.
"""

RECIPES = [
    # ---------------- BREAKFAST ----------------
    {
        "name": "High-Protein Chocolate Oats Bowl", "category": "breakfast", "cook_time_min": 8,
        "ingredients": [("oats_pintola", 50, "50g Pintola Choc Protein Oats"),
                         ("milk_toned", 200, "200ml toned milk"),
                         ("almonds", 10, "10g almonds, chopped"),
                         ("chia_seeds", 10, "10g chia seeds")],
        "method": ["Warm milk on induction (do not boil).", "Stir in oats, cook 3-4 min till thick.",
                    "Top with chopped almonds and chia seeds.", "Rest 2 min (chia thickens) and serve."],
    },
    {
        "name": "Overnight Oats with Makhana Crunch", "category": "breakfast", "cook_time_min": 5,
        "ingredients": [("oats_pintola", 50, "50g Pintola Choc Protein Oats"),
                         ("curd", 100, "100g curd"),
                         ("makhana", 15, "15g roasted makhana"),
                         ("honey", 10, "10g honey")],
        "method": ["Mix oats + curd in a jar, refrigerate overnight.",
                    "Next morning top with crushed roasted makhana and a drizzle of honey."],
    },
    {
        "name": "Paneer Bhurji", "category": "breakfast", "cook_time_min": 12,
        "ingredients": [("paneer", 100, "100g paneer, crumbled"),
                         ("mixed_veg", 60, "60g onion-tomato-capsicum, chopped"),
                         ("oil", 5, "1 tsp oil")],
        "method": ["Heat oil in kadhai, saute chopped veg 3-4 min.",
                    "Add crumbled paneer, turmeric, salt, pepper.",
                    "Cook 4-5 min on medium flame, stirring. Serve with 2 rotis."],
    },
    {
        "name": "Besan Chilla", "category": "breakfast", "cook_time_min": 10,
        "ingredients": [("chana_dal", 40, "40g besan (gram flour, ground from chana dal)"),
                         ("curd", 30, "30g curd (for batter)"),
                         ("oil", 5, "1 tsp oil")],
        "method": ["Grind chana dal in mixer to besan (or use store besan).",
                    "Whisk besan + curd + water into a smooth batter with chopped onion/spinach.",
                    "Cook like a pancake on tawa, both sides, with a little oil."],
    },
    {
        "name": "Sprouted Moong Salad Bowl", "category": "breakfast", "cook_time_min": 10,
        "ingredients": [("moong_dal", 40, "40g moong dal, soaked & sprouted"),
                         ("mixed_veg", 80, "80g cucumber-tomato-onion"),
                         ("pumpkin_seeds", 10, "10g pumpkin seeds")],
        "method": ["Soak moong dal overnight, drain, let sprout 12-24h.",
                    "Toss with chopped veg, lemon, chaat masala, pumpkin seeds."],
    },
    {
        "name": "Paneer Paratha (Stuffed)", "category": "breakfast", "cook_time_min": 15,
        "ingredients": [("paneer", 80, "80g paneer, mashed & spiced"),
                         ("atta_roti", 2, "atta for 2 medium parathas"),
                         ("ghee", 5, "1 tsp ghee for cooking")],
        "method": ["Mash paneer with green chilli, coriander, salt.",
                    "Stuff into atta dough, roll gently, cook on tawa with ghee till golden."],
    },
    {
        "name": "Chia-Almond Milk Pudding", "category": "breakfast", "cook_time_min": 5,
        "ingredients": [("chia_seeds", 25, "25g chia seeds"),
                         ("milk_toned", 200, "200ml toned milk"),
                         ("dates", 15, "15g chopped chuhare"),
                         ("honey", 5, "1 tsp honey")],
        "method": ["Whisk chia into milk, add honey, refrigerate 3+ hours or overnight.",
                    "Top with chopped chuhare before eating."],
    },

    # ---------------- SNACKS ----------------
    {
        "name": "Roasted Chana Trail Mix", "category": "snack", "cook_time_min": 2,
        "ingredients": [("roasted_chana", 30, "30g roasted chana"),
                         ("raisins", 10, "10g kishmish"),
                         ("almonds", 10, "10g almonds")],
        "method": ["Mix and portion into small boxes for the week — zero cooking."],
    },
    {
        "name": "Roasted Makhana Masala Snack", "category": "snack", "cook_time_min": 10,
        "ingredients": [("makhana", 40, "40g makhana"),
                         ("ghee", 5, "1 tsp ghee")],
        "method": ["Dry roast makhana in kadhai on low flame 6-8 min till crisp.",
                    "Toss with a little ghee, black pepper, and a pinch of salt off heat."],
    },
    {
        "name": "Curd + Chia + Pumpkin Seed Bowl", "category": "snack", "cook_time_min": 3,
        "ingredients": [("curd", 150, "150g curd"),
                         ("chia_seeds", 10, "10g chia seeds"),
                         ("pumpkin_seeds", 10, "10g pumpkin seeds")],
        "method": ["Mix chilled curd with chia and pumpkin seeds, rest 5 min, eat."],
    },
    {
        "name": "Paneer Tikka (Tawa)", "category": "snack", "cook_time_min": 15,
        "ingredients": [("paneer", 100, "100g paneer cubes"),
                         ("curd", 50, "50g curd for marinade"),
                         ("mixed_veg", 40, "40g capsicum-onion cubes")],
        "method": ["Marinate paneer + veg in curd, tikka masala, 30 min.",
                    "Skewer or pan-sear on tawa with a little oil till charred spots form."],
    },
    {
        "name": "Sunflower-Pumpkin Seed Mix", "category": "snack", "cook_time_min": 5,
        "ingredients": [("sunflower_seeds", 15, "15g sunflower seeds"),
                         ("pumpkin_seeds", 15, "15g pumpkin seeds")],
        "method": ["Dry roast both seeds together in kadhai 3-4 min on low flame, cool, store airtight."],
    },
    {
        "name": "Sprout Chaat", "category": "snack", "cook_time_min": 8,
        "ingredients": [("moong_dal", 40, "40g sprouted moong"),
                         ("mixed_veg", 50, "50g onion-tomato"),
                         ("dates", 10, "10g chopped chuhare for sweetness")],
        "method": ["Steam sprouts 3-4 min, cool, mix with chopped veg, chaat masala, lemon, chuhare."],
    },
    {
        "name": "Protein Oats Energy Balls", "category": "snack", "cook_time_min": 15,
        "ingredients": [("oats_pintola", 60, "60g Pintola Choc Protein Oats"),
                         ("dates", 40, "40g chuhare, deseeded"),
                         ("cashews", 15, "15g kaju"),
                         ("honey", 10, "10g honey")],
        "method": ["Grind dates + cashews in mixer to a paste.", "Mix in oats and honey, roll into 6-8 balls.",
                    "Refrigerate 30 min to set. Keeps ~1 week."],
    },
    {
        "name": "Roasted Soya Chunk Bites", "category": "snack", "cook_time_min": 12,
        "ingredients": [("soya_chunks", 30, "30g soya chunks (within 30g/day cap)"),
                         ("oil", 5, "1 tsp oil")],
        "method": ["Boil soya chunks 5 min, squeeze out water.",
                    "Pan-roast in kadhai with oil, turmeric, chilli, garam masala till dry and crisp."],
    },

    # ---------------- LUNCH / DINNER MAINS ----------------
    {
        "name": "Palak Paneer", "category": "main", "cook_time_min": 20,
        "ingredients": [("paneer", 100, "100g paneer cubes"),
                         ("spinach", 150, "150g spinach"),
                         ("oil", 8, "2 tsp oil")],
        "method": ["Blanch and puree spinach in grinder.",
                    "Saute onion-tomato-ginger-garlic in kadhai, add spinach puree, simmer.",
                    "Add paneer cubes, simmer 5 min, finish with a splash of milk."],
    },
    {
        "name": "Paneer Curry (Restaurant Style, Home Version)", "category": "main", "cook_time_min": 20,
        "ingredients": [("paneer", 120, "120g paneer cubes"),
                         ("mixed_veg", 100, "100g onion-tomato gravy base"),
                         ("oil", 8, "2 tsp oil")],
        "method": ["Grind onion-tomato-cashew into a smooth gravy paste in grinder.",
                    "Cook paste in kadhai with oil and spices 8-10 min.",
                    "Add paneer, simmer 5 min, serve with 2 rotis."],
    },
    {
        "name": "Moong Dal Tadka", "category": "main", "cook_time_min": 20,
        "ingredients": [("moong_dal", 60, "60g moong dal, dry"),
                         ("mixed_veg", 40, "40g onion-tomato"),
                         ("ghee", 5, "1 tsp ghee for tadka")],
        "method": ["Pressure cook dal with turmeric, salt, 3 whistles.",
                    "Tadka: heat ghee, cumin, garlic, dried red chilli, pour over dal."],
    },
    {
        "name": "Masoor Dal", "category": "main", "cook_time_min": 20,
        "ingredients": [("masoor_dal", 60, "60g masoor dal, dry"),
                         ("mixed_veg", 40, "40g onion-tomato"),
                         ("oil", 5, "1 tsp oil")],
        "method": ["Pressure cook dal, 3 whistles.", "Tadka with cumin, garlic, oil, pour over dal."],
    },
    {
        "name": "Rajma", "category": "main", "cook_time_min": 35,
        "ingredients": [("rajma", 70, "70g rajma, soaked overnight"),
                         ("mixed_veg", 60, "60g onion-tomato gravy"),
                         ("oil", 8, "2 tsp oil")],
        "method": ["Soak rajma 8h, pressure cook 5-6 whistles till soft.",
                    "Cook onion-tomato masala in kadhai, add boiled rajma, simmer 10 min."],
    },
    {
        "name": "Chole", "category": "main", "cook_time_min": 35,
        "ingredients": [("chole", 70, "70g chole, soaked overnight"),
                         ("mixed_veg", 60, "60g onion-tomato gravy"),
                         ("oil", 8, "2 tsp oil")],
        "method": ["Soak chole 8h, pressure cook 5-6 whistles.",
                    "Cook masala in kadhai, add chole, simmer 10-12 min with chole masala."],
    },
    {
        "name": "Chana Dal", "category": "main", "cook_time_min": 25,
        "ingredients": [("chana_dal", 60, "60g chana dal, dry"),
                         ("mixed_veg", 40, "40g onion-tomato"),
                         ("ghee", 5, "1 tsp ghee")],
        "method": ["Pressure cook chana dal 4-5 whistles (firmer than moong/masoor).",
                    "Tadka with ghee, cumin, hing, pour over dal."],
    },
    {
        "name": "Arhar Dal (Plain Tadka Dal)", "category": "main", "cook_time_min": 20,
        "ingredients": [("arhar_dal", 60, "60g arhar dal, dry"),
                         ("mixed_veg", 30, "30g tomato"),
                         ("ghee", 5, "1 tsp ghee")],
        "method": ["Pressure cook dal 3-4 whistles.", "Tadka with ghee, jeera, hing, curry leaves."],
    },
    {
        "name": "Paneer + Veg Stir Fry", "category": "main", "cook_time_min": 15,
        "ingredients": [("paneer", 100, "100g paneer cubes"),
                         ("mixed_veg", 120, "120g mixed capsicum-carrot-beans"),
                         ("oil", 8, "2 tsp oil")],
        "method": ["Pan-sear paneer cubes in kadhai till light golden, set aside.",
                    "Stir-fry veg on high flame 4-5 min, toss paneer back in with soy-free seasoning."],
    },
    {
        "name": "Rajma-Chawal Bowl", "category": "main", "cook_time_min": 30,
        "ingredients": [("rajma", 60, "60g rajma (dry weight), cooked as above"),
                         ("rice_cooked", 150, "150g cooked rice"),
                         ("mixed_veg", 30, "30g onion-tomato in gravy")],
        "method": ["Use cooked Rajma recipe above.", "Serve over 150g steamed rice — a complete post-leg-day carb-up bowl."],
    },

    # ---------------- PRE / POST WORKOUT + BEDTIME ----------------
    {
        "name": "Pre-Workout Banana-Date Energy Bite", "category": "pre_workout", "cook_time_min": 5,
        "ingredients": [("dates", 20, "20g chuhare"),
                         ("oats_pintola", 15, "15g oats")],
        "method": ["Mash dates, mix with oats, eat 30-40 min before training for quick carbs."],
    },
    {
        "name": "Pre-Workout Coffee + Makhana", "category": "pre_workout", "cook_time_min": 5,
        "ingredients": [("makhana", 20, "20g roasted makhana")],
        "method": ["Black coffee (with pre-workout supplement as planned) + a small handful of roasted makhana."],
    },
    {
        "name": "Post-Workout Paneer + Fruit Bowl", "category": "post_workout", "cook_time_min": 5,
        "ingredients": [("paneer", 100, "100g paneer, plain"),
                         ("honey", 10, "10g honey")],
        "method": ["Eat plain or lightly sweetened paneer within 45 min post-training alongside creatine dose."],
    },
    {
        "name": "Post-Workout Curd-Oats Shake", "category": "post_workout", "cook_time_min": 5,
        "ingredients": [("curd", 150, "150g curd"),
                         ("oats_pintola", 30, "30g Pintola oats"),
                         ("honey", 10, "10g honey")],
        "method": ["Blend curd + oats + honey in mixer/grinder into a thick shake. Drink post-training."],
    },
    {
        "name": "Bedtime Warm Turmeric-Elaichi Milk", "category": "bedtime", "cook_time_min": 5,
        "ingredients": [("milk_toned", 200, "200ml toned milk")],
        "method": ["Warm milk on induction with a pinch of turmeric, crushed elaichi, and a clove (laung).",
                    "Add magnesium/ashwagandha supplement dose here if scheduled at bedtime."],
    },
]

RECIPES_BY_CATEGORY = {}
for _r in RECIPES:
    RECIPES_BY_CATEGORY.setdefault(_r["category"], []).append(_r)
