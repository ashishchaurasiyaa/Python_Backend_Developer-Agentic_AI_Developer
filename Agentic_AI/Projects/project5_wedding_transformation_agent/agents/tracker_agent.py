from reportlab.lib.units import cm
from reportlab.platypus import Paragraph
from profile import UserProfile
from agents.base import Section, STYLES, styled_table, spacer, section_break

CHECKLIST_ITEMS = ["Water (3L+)", "Sleep (7.5h+)", "Protein target hit", "Gym session done",
                    "Steps target hit", "Supplements taken"]


def _week_table():
    header = ["Day"] + CHECKLIST_ITEMS
    rows = [header]
    for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        rows.append([d] + ["[ ]"] * len(CHECKLIST_ITEMS))
    return rows


def build(p: UserProfile) -> Section:
    flow = [
        Paragraph("Section 12 &mdash; Motivation &amp; Habit Tracker", STYLES["H1"]),
        Paragraph(
            "Print or copy this page weekly (18 weeks, August to December). Consistency on "
            "these 6 habits matters more than any single perfect day.",
            STYLES["Body"]),
        spacer(),
    ]
    for week in range(1, 19):
        flow.append(Paragraph(f"Week {week}", STYLES["H2"]))
        flow.append(styled_table(_week_table(),
                                  col_widths=[1.6 * cm] + [2.15 * cm] * len(CHECKLIST_ITEMS)))
        flow.append(spacer(0.3))
        if week % 6 == 0 and week != 18:
            flow.append(section_break())
    return Section("Habit Tracker", flow)
