from reportlab.lib.units import cm
from reportlab.platypus import Paragraph
from profile import UserProfile
from agents.base import Section, STYLES, styled_table, spacer, bullets, section_break

PROGRAM = [
    ("Monday", "Chest + Triceps", [
        ("Barbell/Dumbbell Bench Press", "4", "8-10", "90s"),
        ("Incline Dumbbell Press", "3", "10-12", "75s"),
        ("Cable/Dumbbell Flyes", "3", "12-15", "60s"),
        ("Dips or Close-Grip Push-up", "3", "10-12", "60s"),
        ("Triceps Rope Pushdown", "3", "12-15", "45s"),
        ("Overhead Triceps Extension", "3", "12-15", "45s"),
    ]),
    ("Tuesday", "Back + Biceps", [
        ("Pull-ups or Lat Pulldown", "4", "8-10", "90s"),
        ("Barbell/Dumbbell Row", "4", "10-12", "75s"),
        ("Seated Cable Row", "3", "12-15", "60s"),
        ("Face Pulls", "3", "15", "45s"),
        ("Barbell/Dumbbell Curl", "3", "10-12", "60s"),
        ("Hammer Curl", "3", "12-15", "45s"),
    ]),
    ("Wednesday", "Legs", [
        ("Barbell Back Squat", "4", "8-10", "120s"),
        ("Romanian Deadlift", "3", "10-12", "90s"),
        ("Leg Press", "3", "12-15", "75s"),
        ("Walking Lunges", "3", "12/leg", "60s"),
        ("Leg Curl", "3", "12-15", "60s"),
        ("Standing Calf Raise", "4", "15-20", "45s"),
    ]),
    ("Thursday", "Shoulders", [
        ("Overhead Press", "4", "8-10", "90s"),
        ("Lateral Raise", "4", "12-15", "60s"),
        ("Rear Delt Flyes", "3", "15", "45s"),
        ("Front Raise", "3", "12-15", "45s"),
        ("Shrugs", "3", "12-15", "60s"),
        ("Plank + Side Plank", "3", "30-45s hold", "45s"),
    ]),
    ("Friday", "Upper Body (Push-Pull Mix)", [
        ("Incline Barbell Press", "3", "8-10", "90s"),
        ("Single-Arm Dumbbell Row", "3", "10-12", "75s"),
        ("Arnold Press", "3", "10-12", "60s"),
        ("Chin-ups", "3", "8-10", "75s"),
        ("Superset: Curl + Pushdown", "3", "12-12", "60s"),
        ("Cable Crunch", "3", "15-20", "45s"),
    ]),
    ("Saturday", "Legs + Abs + Cardio", [
        ("Front Squat or Goblet Squat", "3", "10-12", "90s"),
        ("Bulgarian Split Squat", "3", "10/leg", "75s"),
        ("Leg Extension", "3", "15", "60s"),
        ("Hanging Leg Raise", "3", "12-15", "45s"),
        ("Russian Twists", "3", "20", "45s"),
        ("HIIT Cardio Finisher", "1", "15 min", "-"),
    ]),
]


def build(p: UserProfile) -> Section:
    flow = [
        Paragraph("Section 7 &mdash; 6-Day Gym Program", STYLES["H1"]),
        Paragraph(
            f"Built for your {p.gym_days_per_week}-day/week schedule. Sunday is a full rest day "
            "(active recovery walk optional). Progressive overload rule below applies to every "
            "session.",
            STYLES["Body"]),
        spacer(),
        Paragraph("Progressive Overload Rule", STYLES["H2"]),
        *bullets([
            "Week 1-2: establish baseline weight for every exercise at the prescribed reps",
            "Every session after: add 2.5-5% load OR 1-2 reps once you hit the top of the rep range on all sets",
            "Deload every 6th week: same exercises, ~60% of normal weight, full recovery focus",
            "Rest periods in the table are minimums &mdash; never rush compound lifts",
        ]),
        spacer(),
    ]
    for day, split, exercises in PROGRAM:
        flow.append(Paragraph(f"{day} &mdash; {split}", STYLES["H2"]))
        rows = [["Exercise", "Sets", "Reps", "Rest"]] + list(exercises)
        flow.append(styled_table(rows, col_widths=[7 * cm, 2 * cm, 2.8 * cm, 2.2 * cm]))
        flow.append(spacer(0.3))
    flow.append(Paragraph("Sunday &mdash; Full Rest", STYLES["H2"]))
    flow.append(Paragraph(
        "Optional 20-30 min easy walk. Focus on sleep, hydration, and meal prep for the week ahead.",
        STYLES["Body"]))
    return Section("Gym Program", flow)
