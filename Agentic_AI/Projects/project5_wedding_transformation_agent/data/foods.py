"""
Food macro database — grams of protein / carbs / fat / kcal per 100 g (or per
unit, noted in the key) of raw/as-purchased ingredient, sourced from standard
Indian nutrition references (IFCT-style values, rounded).

This is the single source of numeric truth for recipes and the meal plan —
every macro shown in the PDF is computed by summing these values for the
quantities used, never hand-typed, so a change here propagates everywhere.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Food:
    name: str
    unit: str        # "100g", "1 egg-equivalent unit", "1 glass (250ml)" etc.
    protein_g: float
    carbs_g: float
    fat_g: float
    kcal: float


# Values are per 100 g unless unit says otherwise.
FOOD_DB = {
    # Dairy
    "paneer": Food("Paneer", "100g", 18.3, 1.2, 20.8, 265),
    "milk_toned": Food("Toned milk", "100ml", 3.3, 4.9, 3.0, 60),
    "curd": Food("Curd (dahi)", "100g", 3.5, 3.4, 4.0, 62),

    # Pulses (dry, before cooking; values per 100 g dry)
    "moong_dal": Food("Moong dal", "100g", 24.0, 56.0, 1.2, 334),
    "masoor_dal": Food("Masoor dal", "100g", 25.0, 55.0, 0.7, 325),
    "arhar_dal": Food("Arhar/Toor dal", "100g", 22.3, 57.6, 1.7, 335),
    "chana_dal": Food("Chana dal", "100g", 20.8, 59.8, 5.3, 364),
    "rajma": Food("Rajma (kidney beans, dry)", "100g", 22.9, 60.6, 1.3, 333),
    "chole": Food("Chole (chickpeas, dry)", "100g", 20.5, 61.0, 5.3, 364),
    "roasted_chana": Food("Roasted chana", "100g", 22.5, 58.0, 5.0, 350),
    "soya_chunks": Food("Soya chunks (dry)", "100g", 52.0, 33.0, 0.5, 345),

    # Grains / packaged
    "oats_pintola": Food("Pintola Chocolate High Protein Oats", "100g", 26.0, 52.0, 8.0, 400),
    "atta_roti": Food("Whole wheat atta (1 medium roti ~30g)", "1 roti", 3.1, 15.0, 0.7, 80),
    "rice_cooked": Food("Rice, cooked", "100g", 2.7, 28.0, 0.3, 130),

    # Dry fruits / seeds (as in pantry)
    "almonds": Food("Badam (almonds)", "100g", 21.2, 21.6, 49.9, 579),
    "cashews": Food("Kaju (cashews)", "100g", 18.2, 30.2, 43.8, 553),
    "pistachios": Food("Pista", "100g", 20.6, 27.2, 45.3, 560),
    "raisins": Food("Kishmish (raisins)", "100g", 3.1, 79.2, 0.5, 299),
    "makhana": Food("Makhana (fox nuts, roasted)", "100g", 9.7, 76.9, 0.1, 347),
    "chia_seeds": Food("Chia seeds", "100g", 16.5, 42.1, 30.7, 486),
    "pumpkin_seeds": Food("Pumpkin seeds", "100g", 30.2, 10.7, 49.0, 559),
    "sunflower_seeds": Food("Sunflower seeds", "100g", 20.8, 20.0, 51.5, 584),
    "dates": Food("Chuhare (dried dates)", "100g", 2.5, 75.0, 0.4, 282),
    "honey": Food("Shahad (honey)", "100g", 0.3, 82.4, 0.0, 304),

    # Vegetables (light macro impact, tracked mainly for fiber/micronutrients)
    "mixed_veg": Food("Mixed seasonal vegetables", "100g", 2.0, 6.0, 0.3, 35),
    "spinach": Food("Spinach (palak)", "100g", 2.9, 3.6, 0.4, 23),

    # Fats
    "ghee": Food("Ghee", "100g", 0.0, 0.0, 100.0, 900),
    "oil": Food("Cooking oil", "100g", 0.0, 0.0, 100.0, 884),
}


def macros_for(food_key: str, grams: float):
    """Return (protein, carbs, fat, kcal) for `grams` of the given food."""
    f = FOOD_DB[food_key]
    factor = grams / 100.0
    return (
        round(f.protein_g * factor, 1),
        round(f.carbs_g * factor, 1),
        round(f.fat_g * factor, 1),
        round(f.kcal * factor, 0),
    )


def sum_macros(items: list):
    """items: list of (food_key, grams). Returns dict protein/carbs/fat/kcal totals."""
    totals = {"protein": 0.0, "carbs": 0.0, "fat": 0.0, "kcal": 0.0}
    for key, grams in items:
        p, c, fa, k = macros_for(key, grams)
        totals["protein"] += p
        totals["carbs"] += c
        totals["fat"] += fa
        totals["kcal"] += k
    return {k: round(v, 1) for k, v in totals.items()}
