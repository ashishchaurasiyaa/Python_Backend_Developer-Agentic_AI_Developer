from reportlab.lib.units import cm
from reportlab.platypus import Paragraph
from profile import UserProfile
from agents.base import Section, STYLES, styled_table, spacer

MONTHLY_CARDIO = [
    ("August", "3x/week, 20 min incline walk (5-8% incline, easy pace)", "8,000"),
    ("September", "4x/week, 20-25 min incline walk + 1x 10 min HIIT (post-leg-day)", "8,500"),
    ("October", "4x/week, 25 min incline walk + 2x 12 min HIIT", "9,000"),
    ("November", "5x/week, 25-30 min incline walk + 2x 15 min HIIT", "9,500"),
    ("December", "Taper week of wedding: 3x/week light walk only, prioritize rest & sleep", "7,000"),
]


def build(p: UserProfile) -> Section:
    flow = [
        Paragraph("Section 8 &mdash; Cardio &amp; Step Plan", STYLES["H1"]),
        Paragraph(
            "Cardio ramps up gradually from August to November to protect strength gains, "
            "then tapers in December wedding week so you show up recovered, not depleted.",
            STYLES["Body"]),
        spacer(),
        styled_table([["Month", "Cardio Prescription", "Daily Step Target"]] + MONTHLY_CARDIO,
                     col_widths=[3 * cm, 9.5 * cm, 3 * cm]),
        spacer(),
        Paragraph("Notes", STYLES["H2"]),
        Paragraph(
            "Incline treadmill walking (\"rucking-style\") burns fat with minimal interference "
            "to strength recovery &mdash; prioritize this over running. HIIT sessions (sprints, "
            "battle ropes, or bike intervals) go on non-leg-day or the Saturday finisher slot in "
            "Section 7 to avoid compounding leg fatigue.",
            STYLES["Body"]),
    ]
    return Section("Cardio Plan", flow)
