from reportlab.platypus import Paragraph
from profile import UserProfile
from calculators import macro_targets
from agents.base import Section, STYLES, spacer, bullets


def build(p: UserProfile) -> Section:
    m = macro_targets(p)
    flow = [
        Paragraph("Section 2 &mdash; Nutrition Science, In Plain Terms", STYLES["H1"]),

        Paragraph("How your calorie target was calculated", STYLES["H2"]),
        Paragraph(
            f"BMR (Mifflin-St Jeor) = 10 &times; weight(kg) + 6.25 &times; height(cm) &minus; "
            f"5 &times; age + 5 = <b>{m['bmr']} kcal</b>. This is multiplied by an activity "
            f"factor of {p.activity_multiplier} (6 lifting days/week) to get TDEE = "
            f"<b>{m['tdee']} kcal</b> &mdash; the calories you burn in a normal day. "
            f"Your target of <b>{m['calories']} kcal</b> is a moderate ~15% deficit below "
            f"TDEE, floored so it never drops below BMR+150 &mdash; deep enough to lose fat, "
            f"shallow enough to keep training hard.",
            STYLES["Body"]),
        spacer(),

        Paragraph("Protein &mdash; the non-negotiable number", STYLES["H2"]),
        Paragraph(
            f"Target: <b>{m['protein_g']} g/day</b> (1.8 g per kg bodyweight). On a calorie "
            f"deficit, protein is what tells your body to keep muscle instead of burning it "
            f"for fuel. Spread across 5-6 meals of 20-30g each is more effective than 2 huge "
            f"protein hits &mdash; your body can only use so much protein per sitting for "
            f"muscle repair.",
            STYLES["Body"]),
        spacer(),

        Paragraph("Protein quality on a vegetarian diet (PDCAAS/DIAAS)", STYLES["H2"]),
        Paragraph(
            "Whole eggs and whey score near-perfect on protein quality scores because they "
            "contain all essential amino acids in the right ratio. Most single plant proteins "
            "(dals, rice) are missing or low in one or two amino acids. The fix is "
            "<b>combining</b> proteins across the day, not any single 'perfect' vegetarian food:",
            STYLES["Body"]),
        *bullets([
            "Dal + Rice/Roti &mdash; classic combination, fills the amino acid gaps in both",
            "Paneer + Dal &mdash; paneer (milk protein) is naturally complete, boosts the meal",
            "Soya chunks (max 30g/day) &mdash; one of the few plant proteins close to complete on its own",
            "Curd/milk daily &mdash; complete protein, easy to hit consistently",
        ]),
        spacer(),

        Paragraph("Carbs &amp; Fats", STYLES["H2"]),
        Paragraph(
            f"Carbs ({m['carbs_g']}g) are not the enemy &mdash; they fuel your 6 gym sessions/week. "
            f"Time more carbs around training (pre/post-workout meals) and fewer at night. "
            f"Fats ({m['fat_g']}g, ~25% of calories) come mainly from ghee, nuts, and seeds &mdash; "
            f"don't drop fat too low, it supports testosterone production which matters for "
            f"muscle gain.",
            STYLES["Body"]),
        spacer(),

        Paragraph("Muscle gain vs fat loss &mdash; can you do both?", STYLES["H2"]),
        Paragraph(
            "Doing both at once (\"body recomposition\") works best for lifters who are newer "
            "to structured training or returning after a break &mdash; which fits a fresh "
            "6-day program. Expect the scale to move slowly (0.3-0.5 kg/week) while your "
            "waist and visible muscle definition change faster than the number on the scale.",
            STYLES["Body"]),
        spacer(),

        Paragraph("Common myths, answered", STYLES["H2"]),
        *bullets([
            "\"Soya reduces testosterone\" &mdash; not at normal intakes (this plan caps it at "
            "30g/day anyway, more for digestion/variety than any hormone concern).",
            "\"Paneer is unhealthy\" &mdash; paneer is a complete, high-protein dairy food; "
            "the concern is only with excess deep-fried preparations, not paneer itself.",
            "\"You must take creatine forever once you start\" &mdash; false, no rebound effect; "
            "you simply return to baseline if you stop.",
            "\"Whey is mandatory to build muscle\" &mdash; false, whole foods can fully meet "
            "protein targets, whey is just convenient, not required (this plan skips it).",
        ]),
    ]
    return Section("Nutrition Science", flow)
