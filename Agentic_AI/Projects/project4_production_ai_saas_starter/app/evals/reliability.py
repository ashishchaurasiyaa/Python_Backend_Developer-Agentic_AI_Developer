"""Consecutive-run reliability.

A single passing run proves almost nothing: agents that pass ~60% of single
runs in a demo drop to ~25% measured over eight consecutive runs at production
load. This module measures that directly — the same cases, N times, reporting
both the all-pass streak and how often the agent gives the *same* answer twice.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from app.config import REPORT_DIR
from app.evals.dataset import CASES, Case
from app.evals.runner import run_case
from app.llm import Backend, get_backend


@dataclass
class CaseReliability:
    case_id: str
    runs: int
    passes: int
    distinct_outputs: int

    @property
    def pass_rate(self) -> float:
        return self.passes / self.runs if self.runs else 0.0

    @property
    def stable(self) -> bool:
        """Same answer every time."""
        return self.distinct_outputs <= 1


@dataclass
class ReliabilityReport:
    provider: str
    runs: int
    cases: list[CaseReliability] = field(default_factory=list)
    all_pass_streak: int = 0

    @property
    def fully_reliable(self) -> list[str]:
        return [c.case_id for c in self.cases if c.passes == c.runs]

    @property
    def flaky(self) -> list[str]:
        return [c.case_id for c in self.cases if 0 < c.passes < c.runs]

    @property
    def always_failing(self) -> list[str]:
        return [c.case_id for c in self.cases if c.passes == 0]


def run_reliability(
    runs: int = 8,
    cases: Optional[list[Case]] = None,
    backend: Optional[Backend] = None,
) -> ReliabilityReport:
    cases = cases if cases is not None else CASES
    backend = backend or get_backend()

    passes: dict[str, int] = {c.id: 0 for c in cases}
    outputs: dict[str, set[str]] = {c.id: set() for c in cases}
    streak = 0
    streak_broken = False

    for _ in range(runs):
        round_all_passed = True
        for case in cases:
            result = run_case(case, backend)
            if result.passed:
                passes[case.id] += 1
            else:
                round_all_passed = False
            outputs[case.id].add(
                json.dumps(result.output, sort_keys=True) if result.output else "<error>"
            )
        if round_all_passed and not streak_broken:
            streak += 1
        elif not round_all_passed:
            streak_broken = True

    return ReliabilityReport(
        provider=backend.name,
        runs=runs,
        cases=[
            CaseReliability(
                case_id=c.id,
                runs=runs,
                passes=passes[c.id],
                distinct_outputs=len(outputs[c.id]),
            )
            for c in cases
        ],
        all_pass_streak=streak,
    )


def write_reliability(report: ReliabilityReport) -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, "reliability_report.md")
    unstable = [c.case_id for c in report.cases if not c.stable]

    lines = [
        "# Triage agent — consecutive-run reliability",
        "",
        f"**Provider:** `{report.provider}` · **Runs per case:** {report.runs}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Consecutive all-pass rounds | {report.all_pass_streak}/{report.runs} |",
        f"| Cases passing every run | {len(report.fully_reliable)}/{len(report.cases)} |",
        f"| Flaky cases | {len(report.flaky)} |",
        f"| Always failing | {len(report.always_failing)} |",
        f"| Non-deterministic outputs | {len(unstable)} |",
        "",
        "| Case | Passes | Distinct outputs |",
        "|---|---|---|",
    ]
    for c in report.cases:
        lines.append(
            f"| `{c.case_id}` | {c.passes}/{c.runs} ({c.pass_rate:.0%}) | "
            f"{c.distinct_outputs} |"
        )
    if report.flaky:
        lines += ["", "**Flaky — these are the real bugs:** " + ", ".join(
            f"`{cid}`" for cid in report.flaky
        )]

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path
