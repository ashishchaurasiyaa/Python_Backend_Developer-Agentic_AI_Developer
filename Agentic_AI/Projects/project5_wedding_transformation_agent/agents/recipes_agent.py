from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, KeepTogether
from profile import UserProfile
from data.recipes import RECIPES
from data.foods import sum_macros
from agents.base import Section, STYLES, styled_table, spacer, bullets


def build(p: UserProfile) -> Section:
    flow = [
        Paragraph("Section 5 &mdash; 30 High-Protein Vegetarian Recipes", STYLES["H1"]),
        Paragraph(
            "Every macro below is calculated from actual ingredient quantities "
            "(see data/foods.py) &mdash; not estimated.",
            STYLES["Body"]),
        spacer(),
    ]
    for i, r in enumerate(RECIPES, 1):
        macro_items = [(key, grams) for key, grams, _ in r["ingredients"]]
        m = sum_macros(macro_items)
        block = [
            Paragraph(f"{i}. {r['name']} <font size=8 color='grey'>[{r['category']}, "
                      f"~{r['cook_time_min']} min]</font>", STYLES["H3"]),
            *bullets([disp for _, _, disp in r["ingredients"]]),
            Paragraph("Method: " + " ".join(f"({j}) {s}" for j, s in enumerate(r["method"], 1)),
                      STYLES["Small"]),
            styled_table([
                ["Protein", "Carbs", "Fat", "Calories"],
                [f"{m['protein']} g", f"{m['carbs']} g", f"{m['fat']} g", f"{m['kcal']:.0f} kcal"],
            ], col_widths=[3.5 * cm] * 4),
            spacer(0.25),
        ]
        flow.append(KeepTogether(block))
    return Section("30 Recipes", flow)
