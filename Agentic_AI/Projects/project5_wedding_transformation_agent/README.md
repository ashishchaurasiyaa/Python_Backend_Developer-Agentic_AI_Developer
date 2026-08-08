# Project 5 — Wedding Transformation Agent

An **agentic pipeline** that generates a personalized ~60-page "Wedding Transformation
Guide" PDF: nutrition plan, grocery list, recipes, 30-day meal plan, 6-day gym program,
cardio schedule, supplement guide, month-by-month roadmap, blood-test checklist, habit
tracker, budget, and FAQ.

## Why this exists

This started as a ChatGPT conversation asking for a 50–60 page personalized diet +
gym PDF. A single chat response can't reliably hold that much content — numbers drift,
sections get truncated, macros stop adding up. The fix is the same pattern used
throughout this repo (see `Level6_Agent_Patterns`): **break the big task into small,
single-responsibility agents, run them in a fixed pipeline, and assemble the verified
output** — instead of asking one giant generation to do everything at once.

## Architecture (Orchestrator–Worker pattern)

```
main.py
  └─ orchestrator.run_pipeline(profile)
        ├─ ProfileAgent        -> personal profile & targets section
        ├─ NutritionAgent      -> calorie/macro science section
        ├─ GroceryAgent        -> weekly + monthly grocery list
        ├─ KitchenAgent        -> equipment-based meal-prep section
        ├─ RecipesAgent        -> 30 recipes, macros computed from FOOD_DB
        ├─ MealPlanAgent       -> 30-day plan, every meal macro-summed & verified
        ├─ GymAgent            -> 6-day workout program
        ├─ CardioAgent         -> Aug→Dec cardio progression
        ├─ SupplementsAgent    -> supplement timing/dosage
        ├─ RoadmapAgent        -> month-by-month physique targets
        ├─ BloodTestAgent      -> recommended panels
        ├─ TrackerAgent        -> weekly habit tracker pages
        ├─ BudgetAgent         -> monthly cost estimate
        └─ FAQAgent            -> common questions
  └─ pdf_builder.build(sections) -> output/Wedding_Transformation_Guide.pdf
```

Each agent is a small pure function: `Profile -> Section` (a title + list of reportlab
flowables). No agent talks to an LLM — all numbers come from `calculators.py`
(Mifflin-St Jeor BMR/TDEE, protein targets) and `data/foods.py` (a macro database per
100 g), so **every calorie/protein number in the PDF is calculated, not guessed**.
That was a deliberate choice over calling the Claude API for this: nutrition numbers
need to be reliable and reproducible run-to-run, not fluent.

## Personalization baked in

Edit `profile.py` to change any of this:

- Height 164.8 cm, weight 71 kg, age 29 (edit `age` — was given as a band, 29 is the
  midpoint of 28–30), gym 6 days/week
- Pure vegetarian, **no eggs**, soya capped at 30 g/day
- Wedding target: December 2026
- Pantry already on hand: pista, kaju, badam, makhane, kishmish, chia, pumpkin seeds,
  sunflower seeds, chuhare, shahad, dhaage-wali mishri, laung, kali mirch, elaichi,
  Pintola Chocolate High Protein Oats (26 g protein/100 g)
- Kitchen equipment: induction, pressure cooker, grinder, tawa, kadhai (no oven)
- Supplements already purchased: creatine, MB-VITE, magnesium, ashwagandha,
  pre-workout, vitamin D3/B12

## Run it

```bash
cd Projects/project5_wedding_transformation_agent
pip install -r requirements.txt
python main.py
```

Output: `output/Wedding_Transformation_Guide.pdf` (~55-65 pages).

## Re-running / extending

Because content is generated from `profile.py` + `data/foods.py`, changing your
weight, re-running after a progress update, or adding a new pantry item just means
editing those two files and re-running `main.py` — no need to regenerate anything by
hand. To add a new section, drop a new file in `agents/` following the existing
`Profile -> Section` shape and register it in `orchestrator.py`.

## Disclaimer

Calorie/macro targets use a standard estimation formula (Mifflin-St Jeor) and general
sports-nutrition heuristics. Blood test panels are commonly recommended screens, not
medical advice — confirm with a doctor before acting on them, especially before
changing supplement doses.
