from reportlab.platypus import Paragraph
from profile import UserProfile
from agents.base import Section, STYLES, spacer, bullets


def build(p: UserProfile) -> Section:
    flow = [
        Paragraph("Section 4 &mdash; Kitchen Setup &amp; Meal Prep", STYLES["H1"]),
        Paragraph(
            "Every recipe in this guide is deliberately built around only the equipment "
            "you have &mdash; no oven, no blender-specific steps that need extra gear.",
            STYLES["Body"]),
        spacer(),
        Paragraph("Your equipment &rarr; what it's used for", STYLES["H2"]),
        *bullets([
            "Induction &mdash; all stovetop cooking, milk warming, sautéing",
            "Pressure cooker &mdash; dals, rajma, chole, rice (fastest, most consistent way to cook pulses)",
            "Mixer/grinder &mdash; gravies, besan from chana dal, chutneys, energy-ball paste",
            "Tawa &mdash; roti, paratha, chilla, paneer tikka, roasting seeds/makhana",
            "Kadhai &mdash; curries, stir-fries, dry-roasting, deep dish cooking",
        ]),
        spacer(),
        Paragraph("Sunday Meal-Prep Routine (60-75 minutes)", STYLES["H2"]),
        *bullets([
            "Pressure-cook a large batch of 2 dals for the week, refrigerate in daily portions",
            "Boil rajma/chole once, freeze in 2 portions",
            "Roast a week's worth of makhana + seed mix, store airtight",
            "Chop onion-tomato base in bulk, refrigerate for quick gravies",
            "Portion dry fruits/seeds into small daily boxes to avoid over/under-eating them",
            "Pre-mash paneer for bhurji so weekday breakfast takes under 10 minutes",
        ]),
        spacer(),
        Paragraph("Weeknight Speed Rule", STYLES["H2"]),
        Paragraph(
            "If a recipe takes over 20 minutes active time, it goes on the weekend-cook list, "
            "not weekdays. Every weekday recipe in Section 5 is chosen to be under 20 minutes.",
            STYLES["Body"]),
    ]
    return Section("Kitchen & Meal Prep", flow)
