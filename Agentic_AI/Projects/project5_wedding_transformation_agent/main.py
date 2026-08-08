"""
Entry point: build profile -> run agent pipeline -> assemble PDF.

Usage:
    python main.py
"""

import os
from profile import DEFAULT_PROFILE
from orchestrator import run_pipeline
from pdf_builder import build as build_pdf


def main():
    profile = DEFAULT_PROFILE
    print(f"Building Wedding Transformation Guide for {profile.name} "
          f"({profile.height_cm}cm, {profile.weight_kg}kg, age {profile.age})...")

    print("Running agent pipeline:")
    sections = run_pipeline(profile)
    print(f"  {len(sections)} sections generated.")

    out_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "Wedding_Transformation_Guide.pdf")

    print("Assembling PDF...")
    build_pdf(sections, profile, out_path)
    print(f"Done -> {out_path}")


if __name__ == "__main__":
    main()
