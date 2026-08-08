from reportlab.lib.units import cm
from reportlab.platypus import Paragraph
from profile import UserProfile
from agents.base import Section, STYLES, styled_table, spacer, bullets

# (item, weekly qty) — sized for one person, 6 training days/week
WEEKLY_DAIRY = [
    ("Paneer", "1.2 kg"), ("Toned milk", "6-7 L"), ("Curd", "1.5 kg"),
]
WEEKLY_PULSES = [
    ("Moong dal", "300 g"), ("Masoor dal", "250 g"), ("Arhar/Toor dal", "250 g"),
    ("Chana dal", "250 g"), ("Rajma (dry)", "300 g"), ("Chole (dry)", "300 g"),
    ("Roasted chana", "300 g"), ("Soya chunks", "150 g (well under 30g/day cap)"),
]
WEEKLY_VEG = [
    ("Onion, tomato, ginger-garlic", "seasoning base, as needed"),
    ("Spinach / seasonal greens", "500 g"),
    ("Capsicum, carrot, beans, cucumber", "1 kg mixed"),
]
WEEKLY_GRAINS = [
    ("Pintola Chocolate High Protein Oats", "1 pack (350-500g)"),
    ("Whole wheat atta", "1.5-2 kg"), ("Rice", "500 g"),
]
MONTHLY_PANTRY = [
    ("Badam (almonds)", "250 g"), ("Kaju (cashews)", "200 g"), ("Pista", "150 g"),
    ("Kishmish", "150 g"), ("Makhana", "250 g"), ("Chia seeds", "150 g"),
    ("Pumpkin seeds", "150 g"), ("Sunflower seeds", "150 g"), ("Chuhare", "200 g"),
    ("Shahad (honey)", "250 g jar"), ("Dhaage-wali mishri", "as needed"),
    ("Laung, kali mirch, elaichi", "small refill, lasts months"),
    ("Ghee", "500 g"), ("Cooking oil", "1 L"),
]


def build(p: UserProfile) -> Section:
    flow = [
        Paragraph("Section 3 &mdash; Complete Grocery List", STYLES["H1"]),
        Paragraph(
            "Sized for one person on this plan (6 gym days/week). Most of your dry "
            "fruits, seeds, and spices are already stocked &mdash; only the monthly "
            "top-up amount is listed for those.",
            STYLES["Body"]),
        spacer(),
        Paragraph("Weekly &mdash; Dairy", STYLES["H2"]),
        styled_table([["Item", "Weekly Quantity"]] + WEEKLY_DAIRY, col_widths=[8 * cm, 7 * cm]),
        spacer(0.3),
        Paragraph("Weekly &mdash; Pulses &amp; Legumes", STYLES["H2"]),
        styled_table([["Item", "Weekly Quantity"]] + WEEKLY_PULSES, col_widths=[8 * cm, 7 * cm]),
        spacer(0.3),
        Paragraph("Weekly &mdash; Vegetables", STYLES["H2"]),
        styled_table([["Item", "Weekly Quantity"]] + WEEKLY_VEG, col_widths=[8 * cm, 7 * cm]),
        spacer(0.3),
        Paragraph("Weekly &mdash; Grains", STYLES["H2"]),
        styled_table([["Item", "Weekly Quantity"]] + WEEKLY_GRAINS, col_widths=[8 * cm, 7 * cm]),
        spacer(0.3),
        Paragraph("Monthly Top-Up &mdash; Dry Fruits, Seeds, Sweeteners, Spices (already stocked)", STYLES["H2"]),
        styled_table([["Item", "Monthly Quantity"]] + MONTHLY_PANTRY, col_widths=[8 * cm, 7 * cm]),
        spacer(0.3),
        Paragraph("Fruits (seasonal, budget-friendly rotation)", STYLES["H2"]),
        *bullets([
            "Aug-Sep: banana, papaya, chikoo, guava",
            "Oct-Nov: apple, pomegranate, orange, guava",
            "Dec: apple, orange, pomegranate, papaya",
            "Rule of thumb: 1-2 servings/day, prioritize local & seasonal for cost + freshness",
        ]),
    ]
    return Section("Grocery List", flow)
