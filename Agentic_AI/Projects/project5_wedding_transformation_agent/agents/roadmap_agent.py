from reportlab.lib.units import cm
from reportlab.platypus import Paragraph
from profile import UserProfile
from agents.base import Section, STYLES, styled_table, spacer, bullets

MONTHS = ["August", "September", "October", "November", "December"]


def build(p: UserProfile) -> Section:
    # Simple, conservative projection: ~0.4kg/week average net change (fat loss
    # outpacing the slower lean-mass gain typical on a vegetarian recomposition).
    weekly_change_kg = 0.4
    rows = [["Month", "Weight Target", "Waist", "Visible Change", "Strength Milestone"]]
    weight = p.weight_kg
    milestones = [
        "Baseline lifts established across all 6 sessions",
        "+5-10% load on main compounds vs Month 1",
        "Visible arm/shoulder definition, waist trending down",
        "Near target physique, strength plateauing intentionally (maintenance phase begins)",
        "Wedding week &mdash; taper, maintain, don't chase new PRs",
    ]
    for i, month in enumerate(MONTHS):
        weight = round(weight - (weekly_change_kg * 4 if i < 4 else 0), 1)
        waist_note = "starting point" if i == 0 else ("-1 to -1.5 inch vs Aug" if i < 4 else "-2 to -3 inch vs Aug, maintained")
        visible = ["Starting point", "Slight leaning out", "Noticeably leaner + fuller muscle",
                   "Defined, wedding-ready physique emerging", "Peak condition for the wedding"][i]
        rows.append([month, f"~{weight} kg", waist_note, visible, milestones[i]])

    flow = [
        Paragraph("Section 10 &mdash; Wedding Physique Plan (Month-by-Month)", STYLES["H1"]),
        Paragraph(
            f"From {p.plan_start_month} {p.plan_start_year} to your {p.wedding_month} "
            f"{p.wedding_year} wedding &mdash; a conservative, sustainable trajectory "
            f"(~0.4 kg/week average net change), not a crash plan.",
            STYLES["Body"]),
        spacer(),
        styled_table(rows, col_widths=[2.3 * cm, 2.3 * cm, 2.6 * cm, 3.8 * cm, 4 * cm]),
        spacer(),
        Paragraph("Why this pace, not faster", STYLES["H2"]),
        *bullets([
            "Faster fat loss (>0.7kg/week) usually costs muscle too &mdash; the opposite of your goal",
            "This pace keeps energy high enough to actually complete 6 gym sessions/week",
            "December is a taper/maintain month by design &mdash; you don't want to be in a deep deficit during wedding events with heavy food",
        ]),
    ]
    return Section("Wedding Physique Roadmap", flow)
