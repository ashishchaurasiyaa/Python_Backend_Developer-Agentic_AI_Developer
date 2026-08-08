from reportlab.lib.units import cm
from reportlab.platypus import Paragraph
from profile import UserProfile
from agents.base import Section, STYLES, styled_table, spacer, bullets

SCHEDULE = [
    ("MB-VITE (multivitamin)", "With breakfast", "1 dose", "Covers micronutrient gaps, take with food for absorption"),
    ("Creatine monohydrate", "Post-workout (any time on rest days)", "5 g", "Timing doesn't matter much, consistency does"),
    ("Pre-workout", "20-30 min before training", "1 scoop", "Skip on rest days; cycle off 1 week every 8 weeks"),
    ("Ashwagandha", "After dinner", "As per label (~300-600mg)", "Supports recovery & stress; take consistently, not just pre-training"),
    ("Magnesium", "Before bed", "As per label", "Supports sleep quality & muscle recovery"),
    ("Vitamin D3/B12", "With breakfast", "As per label, if levels are low", "Only needed if blood test (Section 11) shows deficiency"),
]


def build(p: UserProfile) -> Section:
    flow = [
        Paragraph("Section 9 &mdash; Supplement Guide", STYLES["H1"]),
        Paragraph(
            "Based on what you already have on hand. None of these are required to reach "
            "your goal &mdash; they support a whole-food plan, they don't replace it.",
            STYLES["Body"]),
        spacer(),
        styled_table([["Supplement", "Timing", "Dose", "Note"]] + SCHEDULE,
                     col_widths=[3.5 * cm, 3.5 * cm, 2.5 * cm, 5.5 * cm]),
        spacer(),
        Paragraph("Rest Day Adjustment", STYLES["H2"]),
        *bullets([
            "Skip pre-workout entirely on rest days",
            "Still take creatine (works on total body creatine stores, not per-workout)",
            "Keep multivitamin, ashwagandha, and magnesium on the same daily schedule",
        ]),
        spacer(),
        Paragraph("Common Mistakes to Avoid", STYLES["H2"]),
        *bullets([
            "Taking pre-workout late in the day &mdash; disrupts sleep, which hurts recovery more than the workout boost helps",
            "Doubling creatine dose thinking it works faster &mdash; 5g/day is the maintenance dose, more doesn't help",
            "Relying on supplements to fix a calorie/protein shortfall &mdash; fix food first, supplements second",
            "Stacking multiple new supplements at once &mdash; you won't know what's working or causing side effects",
        ]),
    ]
    return Section("Supplement Guide", flow)
