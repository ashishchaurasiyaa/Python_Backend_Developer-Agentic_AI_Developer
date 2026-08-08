"""
Orchestrator — runs every section-agent in a fixed order against the shared
UserProfile and returns the ordered list of Sections for the PDF builder.

This is the "planner" in the orchestrator-worker pattern: it owns *sequence*,
each agent owns *content*. Adding a new section = write an agent module with
a `build(profile) -> Section` function, then add one line here.
"""

from profile import UserProfile
from agents.base import Section
from agents import (
    profile_agent, nutrition_agent, grocery_agent, kitchen_agent,
    recipes_agent, meal_plan_agent, gym_agent, cardio_agent,
    supplements_agent, roadmap_agent, bloodtest_agent, tracker_agent,
    budget_agent, faq_agent,
)

PIPELINE = [
    profile_agent, nutrition_agent, grocery_agent, kitchen_agent,
    recipes_agent, meal_plan_agent, gym_agent, cardio_agent,
    supplements_agent, roadmap_agent, bloodtest_agent, tracker_agent,
    budget_agent, faq_agent,
]


def run_pipeline(p: UserProfile) -> list:
    sections = []
    for agent_module in PIPELINE:
        print(f"  -> running {agent_module.__name__.split('.')[-1]} ...")
        section = agent_module.build(p)
        assert isinstance(section, Section), f"{agent_module} did not return a Section"
        assert section.flowables, f"{agent_module} produced an empty section"
        sections.append(section)
    return sections
