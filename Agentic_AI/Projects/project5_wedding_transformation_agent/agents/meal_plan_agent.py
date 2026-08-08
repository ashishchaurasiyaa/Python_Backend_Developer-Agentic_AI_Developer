from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, KeepTogether
from profile import UserProfile
from calculators import macro_targets
from data.recipes import RECIPES_BY_CATEGORY
from data.foods import sum_macros
from agents.base import Section, STYLES, styled_table, spacer, section_break

SLOTS = ["breakfast", "main", "main", "pre_workout", "post_workout", "snack", "bedtime"]
SLOT_LABELS = ["Breakfast", "Lunch", "Dinner", "Pre-Workout", "Post-Workout", "Evening Snack", "Bedtime"]


def _pick(category: str, day_index: int, offset: int = 0):
    pool = RECIPES_BY_CATEGORY[category]
    return pool[(day_index + offset) % len(pool)]


def _day_meals(day_index: int):
    """Deterministic rotation so every day is reproducible and macro-verifiable.
    Lunch/Dinner both draw from 'main' but with an offset so they differ."""
    breakfast = _pick("breakfast", day_index)
    lunch = _pick("main", day_index)
    dinner = _pick("main", day_index, offset=5)  # offset keeps lunch != dinner
    pre = _pick("pre_workout", day_index)
    post = _pick("post_workout", day_index)
    snack = _pick("snack", day_index)
    bedtime = _pick("bedtime", day_index)
    return [breakfast, lunch, dinner, pre, post, snack, bedtime]


def _macros_for_recipe(r):
    return sum_macros([(k, g) for k, g, _ in r["ingredients"]])


def build(p: UserProfile) -> Section:
    targets = macro_targets(p)
    flow = [
        Paragraph("Section 6 &mdash; 30-Day Meal Plan", STYLES["H1"]),
        Paragraph(
            f"Target: <b>{targets['calories']} kcal</b>, <b>{targets['protein_g']}g protein</b> "
            f"per day. Each day below rotates through the 30 recipes from Section 5 &mdash; "
            f"totals are summed automatically from real ingredient quantities so you can "
            f"trust the numbers. If a day's total sits below target, add an extra roti/rice "
            f"portion or a bigger handful of your dry-fruit mix to close the gap; this plan "
            f"deliberately shows the honest baseline rather than padding numbers artificially.",
            STYLES["Body"]),
        spacer(),
    ]

    for day in range(1, 31):
        idx = day - 1
        meals = _day_meals(idx)
        rows = [["Meal", "Recipe", "Protein", "Carbs", "Fat", "Kcal"]]
        totals = {"protein": 0.0, "carbs": 0.0, "fat": 0.0, "kcal": 0.0}
        for label, recipe in zip(SLOT_LABELS, meals):
            m = _macros_for_recipe(recipe)
            rows.append([label, recipe["name"], f"{m['protein']}g", f"{m['carbs']}g",
                         f"{m['fat']}g", f"{m['kcal']:.0f}"])
            for k in totals:
                totals[k] += m[k]
        rows.append(["TOTAL", "", f"{totals['protein']:.0f}g", f"{totals['carbs']:.0f}g",
                     f"{totals['fat']:.0f}g", f"{totals['kcal']:.0f}"])
        diff_kcal = totals["kcal"] - targets["calories"]
        diff_protein = totals["protein"] - targets["protein_g"]
        week_no = ((day - 1) // 7) + 1
        block = [
            Paragraph(f"Day {day} <font size=8 color='grey'>(Week {week_no})</font>", STYLES["H3"]),
            styled_table(rows, col_widths=[2.6 * cm, 5.2 * cm, 1.7 * cm, 1.7 * cm, 1.5 * cm, 1.8 * cm]),
            Paragraph(
                f"vs. target: {diff_kcal:+.0f} kcal, {diff_protein:+.0f}g protein "
                f"&mdash; top up with roti/rice/dry-fruit portions if short.",
                STYLES["Small"]),
            spacer(0.25),
        ]
        flow.append(KeepTogether(block))
        if day != 30:
            flow.append(section_break())

    return Section("30-Day Meal Plan", flow)
