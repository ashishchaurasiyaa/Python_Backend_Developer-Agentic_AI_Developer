from reportlab.lib.units import cm
from reportlab.platypus import Paragraph
from profile import UserProfile
from agents.base import Section, STYLES, styled_table, spacer

TESTS = [
    ("CBC (Complete Blood Count)", "Baseline health, rules out anemia (common on veg diets)"),
    ("Vitamin D", "Very commonly low in India; deficiency affects strength & recovery"),
    ("Vitamin B12", "Vegetarians are at higher risk of low B12; affects energy levels"),
    ("Lipid Profile", "Baseline cholesterol/triglycerides before a diet change"),
    ("HbA1c (if indicated)", "Only if family history of diabetes or doctor recommends"),
    ("Liver &amp; Kidney Function", "Only if your doctor recommends, e.g. before starting new supplements"),
]


def build(p: UserProfile) -> Section:
    flow = [
        Paragraph("Section 11 &mdash; Recommended Blood Tests", STYLES["H1"]),
        Paragraph(
            "Optional but useful before a 4-5 month training block, especially since you're "
            "vegetarian (B12/D3/Iron are the common gaps). This is general guidance, not a "
            "medical prescription &mdash; a doctor should interpret your actual results.",
            STYLES["Body"]),
        spacer(),
        styled_table([["Test", "Why It's Useful"]] + TESTS, col_widths=[5 * cm, 10 * cm]),
        spacer(),
        Paragraph("How to read results (general guidance only)", STYLES["H2"]),
        Paragraph(
            "If Vitamin D or B12 comes back low, that alone can explain low energy or slow "
            "recovery regardless of how well your training and diet plan is followed &mdash; "
            "worth fixing first with your doctor's guidance before assuming the training plan "
            "needs changing.",
            STYLES["Body"]),
    ]
    return Section("Blood Tests", flow)
