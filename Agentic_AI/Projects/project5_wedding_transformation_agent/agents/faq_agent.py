from reportlab.platypus import Paragraph
from profile import UserProfile
from agents.base import Section, STYLES, spacer

FAQS = [
    ("Does soya reduce testosterone?",
     "Not at normal dietary intakes — this concern comes from very high-dose isolated soy "
     "isoflavone studies, not from eating soya chunks a few times a week. This plan caps it "
     "at 30g/day regardless, mainly for digestion and variety."),
    ("Is paneer healthy?",
     "Yes — it's a complete, high-protein dairy food. The only real caution is preparations "
     "swimming in extra ghee/oil at restaurants; the home recipes here control that."),
    ("Is creatine safe?",
     "Yes, one of the most studied and safe supplements available. 5g/day maintenance dose, "
     "stay hydrated. Not linked to kidney damage in healthy individuals."),
    ("Should I take pre-workout daily?",
     "No — skip it on rest days, and consider a 1-week break every 8 weeks to avoid building "
     "tolerance to the stimulant content."),
    ("How much protein do I really need?",
     "Your calculated target is in Section 1/2 (1.8g/kg bodyweight). More isn't harmful but "
     "isn't extra useful once you're consistently hitting that number."),
    ("Can I skip whey?",
     "Yes, this entire plan is built without whey by design — paneer, dal, curd, and oats "
     "cover the protein target through whole foods."),
    ("What to eat while travelling (e.g. wedding events, work trips)?",
     "Prioritize dal + roti/rice + curd + salad at any restaurant or wedding buffet — it's "
     "available almost everywhere and hits your protein target reasonably well. Don't stress "
     "about hitting exact macros on travel days; get back on plan the next day."),
    ("What if I miss a gym day?",
     "Don't try to 'make it up' by doubling the next session — just resume the normal split "
     "the next scheduled day. Consistency over weeks matters far more than any single session."),
]


def build(p: UserProfile) -> Section:
    flow = [Paragraph("Section 14 &mdash; FAQ", STYLES["H1"]), spacer()]
    for q, a in FAQS:
        flow.append(Paragraph(f"Q: {q}", STYLES["H3"]))
        flow.append(Paragraph(f"A: {a}", STYLES["Body"]))
        flow.append(spacer(0.25))
    return Section("FAQ", flow)
