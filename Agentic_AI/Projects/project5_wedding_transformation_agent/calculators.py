"""
Nutrition calculators — Mifflin-St Jeor BMR/TDEE, protein/macro targets.

Kept separate from the agents so the numbers can be unit-tested and reused
by every section (Nutrition, Meal Plan, Roadmap all need the same targets).
"""

from profile import UserProfile


def bmr(p: UserProfile) -> float:
    """Mifflin-St Jeor equation."""
    base = 10 * p.weight_kg + 6.25 * p.height_cm - 5 * p.age
    return base + 5 if p.sex == "male" else base - 161


def tdee(p: UserProfile) -> float:
    return bmr(p) * p.activity_multiplier


def target_calories(p: UserProfile) -> int:
    """Moderate deficit for recomposition: ~15% below TDEE, floor at BMR+150
    so it never drops into an unsafe range for a 6-day training week."""
    deficit_cals = tdee(p) * 0.85
    floor = bmr(p) + 150
    return int(round(max(deficit_cals, floor) / 10) * 10)


def target_protein_g(p: UserProfile) -> int:
    """1.8 g/kg bodyweight — standard for muscle retention during a cut,
    pure-veg friendly target that's achievable with paneer/dal/oats."""
    return int(round(p.weight_kg * 1.8))


def target_fat_g(p: UserProfile) -> int:
    """25% of calories from fat, rounded to nearest 5g."""
    kcal = target_calories(p)
    grams = (kcal * 0.25) / 9
    return int(round(grams / 5) * 5)


def target_carbs_g(p: UserProfile) -> int:
    """Remainder of calories after protein + fat."""
    kcal = target_calories(p)
    protein_kcal = target_protein_g(p) * 4
    fat_kcal = target_fat_g(p) * 9
    remaining = max(kcal - protein_kcal - fat_kcal, 0)
    return int(round((remaining / 4) / 5) * 5)


def macro_targets(p: UserProfile) -> dict:
    return {
        "bmr": int(round(bmr(p))),
        "tdee": int(round(tdee(p))),
        "calories": target_calories(p),
        "protein_g": target_protein_g(p),
        "fat_g": target_fat_g(p),
        "carbs_g": target_carbs_g(p),
    }


def water_target_l(p: UserProfile) -> float:
    return round(p.weight_kg * 0.045, 1)  # ~45ml/kg, active adult


def weeks_to_wedding(p: UserProfile, current_month_index: int, current_year: int) -> int:
    """current_month_index: 1=Jan..12=Dec. Used by RoadmapAgent."""
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
        "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
        "December": 12,
    }
    target = months[p.wedding_month]
    year_diff = p.wedding_year - current_year
    month_diff = (year_diff * 12) + (target - current_month_index)
    return max(month_diff, 0) * 4
