from reportlab.lib.units import cm
from reportlab.platypus import Paragraph
from profile import UserProfile
from agents.base import Section, STYLES, styled_table, spacer

BUDGET_ROWS = [
    ["Dairy (paneer, milk, curd)", "Rs. 2,200 - 2,600"],
    ["Pulses & legumes", "Rs. 900 - 1,200"],
    ["Vegetables & fruits", "Rs. 1,500 - 2,000"],
    ["Grains (oats, atta, rice)", "Rs. 700 - 900"],
    ["Dry fruits & seeds top-up", "Rs. 800 - 1,200 (already stocked, lasts 4-6 weeks)"],
    ["Ghee & oil", "Rs. 400 - 500"],
    ["Supplements (already purchased, refill later)", "Rs. 0 this month"],
    ["TOTAL (approx.)", "Rs. 6,500 - 8,400 / month"],
]


def build(p: UserProfile) -> Section:
    flow = [
        Paragraph("Section 13 &mdash; Monthly Grocery Budget", STYLES["H1"]),
        Paragraph(
            "Rough estimate for one person on this plan, current India retail pricing "
            "(2026). Adjust to your local market.",
            STYLES["Body"]),
        spacer(),
        styled_table([["Category", "Estimated Monthly Cost"]] + BUDGET_ROWS, col_widths=[9 * cm, 6 * cm]),
        spacer(),
        Paragraph(
            "Cost-saving tip: buying dals, rajma, chole, and dry fruits in 1-2kg packs from a "
            "wholesale/kirana store instead of small packs typically cuts this by 10-15%.",
            STYLES["Body"]),
    ]
    return Section("Monthly Budget", flow)
