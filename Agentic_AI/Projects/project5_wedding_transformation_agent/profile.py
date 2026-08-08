"""
User profile — single source of truth for personalization.

Edit any value here and re-run `python main.py`; every downstream agent
(nutrition targets, grocery quantities, recipe macros, meal plan, gym plan)
reads from this file, so the whole PDF stays consistent.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class UserProfile:
    name: str = "Groom-to-be"

    # --- Body stats ---
    height_cm: float = 164.8
    weight_kg: float = 71.0
    # Age was given as a band (28-30); 29 = midpoint. Edit if you know the exact age —
    # it shifts BMR by ~5 kcal/year, not huge, but worth getting exact.
    age: int = 29
    sex: str = "male"

    # --- Goal ---
    goal: str = "lean muscle gain + fat loss"
    wedding_month: str = "December"
    wedding_year: int = 2026
    plan_start_month: str = "August"
    plan_start_year: int = 2026

    # --- Dietary rules ---
    diet: str = "pure vegetarian"
    eats_eggs: bool = False
    eats_tofu: bool = False
    max_soya_g_per_day: int = 30
    uses_whey: bool = False  # optional whey — plan defaults to whole-food protein

    # --- Training ---
    gym_days_per_week: int = 6
    activity_level: str = "moderately active"  # 6x lifting + walking/cardio
    # Mifflin-St Jeor activity multiplier. 1.55 = moderate exercise 3-5x/week.
    # Bumped slightly for a 6-day program without over-crediting non-training hours.
    activity_multiplier: float = 1.6

    # --- Kitchen equipment (recipes are constrained to only these) ---
    kitchen_equipment: List[str] = field(default_factory=lambda: [
        "Induction cooktop", "Pressure cooker", "Mixer/grinder", "Tawa", "Kadhai",
    ])

    # --- Pantry already on hand (from user's actual stock) ---
    pantry_dry_fruits_seeds: List[str] = field(default_factory=lambda: [
        "Pista (pistachios)", "Kaju (cashews)", "Badam (almonds)", "Makhana (fox nuts)",
        "Kishmish (raisins)", "Chia seeds", "Pumpkin seeds", "Sunflower seeds",
        "Chuhare (dried dates)",
    ])
    pantry_sweeteners_spices: List[str] = field(default_factory=lambda: [
        "Shahad (honey)", "Dhaage-wali mishri (rock candy)", "Laung (cloves)",
        "Kali mirch (black pepper)", "Elaichi (cardamom)",
    ])
    pantry_packaged: List[str] = field(default_factory=lambda: [
        "Pintola Chocolate High Protein Oats (26 g protein / 100 g)",
    ])

    # --- Supplements already purchased ---
    supplements_on_hand: List[str] = field(default_factory=lambda: [
        "Creatine monohydrate", "MB-VITE (multivitamin)", "Magnesium",
        "Ashwagandha", "Pre-workout", "Vitamin D3/B12 (as needed)",
    ])

    @property
    def bmi(self) -> float:
        h_m = self.height_cm / 100
        return round(self.weight_kg / (h_m * h_m), 1)


DEFAULT_PROFILE = UserProfile()
