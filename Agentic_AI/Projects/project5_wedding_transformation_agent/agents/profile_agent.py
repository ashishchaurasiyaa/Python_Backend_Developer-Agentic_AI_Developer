from reportlab.lib.units import cm
from profile import UserProfile
from calculators import macro_targets, water_target_l
from agents.base import Section, STYLES, styled_table, spacer, bullets
from reportlab.platypus import Paragraph


def build(p: UserProfile) -> Section:
    m = macro_targets(p)
    flow = [
        Paragraph("Section 1 &mdash; Personal Profile &amp; Goals", STYLES["H1"]),
        Paragraph(
            f"This guide is built specifically for you &mdash; every number in it is "
            f"calculated from the stats below, not a generic template.",
            STYLES["Body"]),
        spacer(),
        styled_table([
            ["Metric", "Value"],
            ["Height", f"{p.height_cm} cm"],
            ["Current weight", f"{p.weight_kg} kg"],
            ["BMI", f"{p.bmi}"],
            ["Age", f"{p.age} years"],
            ["Goal", p.goal.title()],
            ["Wedding target", f"{p.wedding_month} {p.wedding_year}"],
            ["Diet", f"{p.diet.title()} (no eggs)"],
            ["Max soya/day", f"{p.max_soya_g_per_day} g"],
            ["Training days/week", str(p.gym_days_per_week)],
            ["Activity level", p.activity_level.title()],
        ], col_widths=[6 * cm, 9 * cm]),
        spacer(),
        Paragraph("Your Daily Targets (calculated, Mifflin-St Jeor equation)", STYLES["H2"]),
        styled_table([
            ["Target", "Value", "Why"],
            ["BMR", f"{m['bmr']} kcal", "Calories burned at complete rest"],
            ["TDEE", f"{m['tdee']} kcal", "BMR x activity multiplier (6 gym days/week)"],
            ["Daily calories", f"{m['calories']} kcal", "~15% deficit below TDEE for lean recomposition"],
            ["Protein", f"{m['protein_g']} g", "1.8 g/kg bodyweight &mdash; muscle retention on a cut"],
            ["Fat", f"{m['fat_g']} g", "~25% of calories &mdash; hormone health"],
            ["Carbs", f"{m['carbs_g']} g", "Remaining calories &mdash; fuels 6-day training"],
            ["Water", f"{water_target_l(p)} L", "~45 ml/kg bodyweight, active adult"],
        ], col_widths=[3.5 * cm, 3 * cm, 8.5 * cm]),
        spacer(),
        Paragraph("Kitchen equipment this guide is designed around", STYLES["H3"]),
        *bullets(p.kitchen_equipment),
        spacer(0.2),
        Paragraph("Pantry already on hand (used throughout the recipes)", STYLES["H3"]),
        *bullets(p.pantry_dry_fruits_seeds + p.pantry_sweeteners_spices + p.pantry_packaged),
        spacer(0.2),
        Paragraph(
            "Note: these targets are estimates from a standard formula, not a medical "
            "assessment. Re-weigh weekly and adjust calories by ±100-150 kcal if weight "
            "isn't moving in the expected direction after 2-3 weeks.",
            STYLES["Small"]),
    ]
    return Section("Profile & Goals", flow)
