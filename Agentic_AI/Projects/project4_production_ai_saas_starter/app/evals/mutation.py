"""Mutation testing for the eval suite.

An eval suite that always reports 100% is worth nothing until you know it can
report something else. This module breaks the agent on purpose, one defect at a
time, and asserts that the suite notices.

A surviving mutant is a hole in the dataset, not a passing grade. The first run
of this found one: output-side PII redaction was never exercised, because the
input guard strips emails before the model ever sees them. That gap is now
covered by tests/test_guardrails.py, and the mutant is marked accordingly.
"""

import contextlib
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

import app.agent.triage as triage_mod
import app.guardrails as guardrails
import app.llm as llm
from app.evals.runner import run_eval
from app.llm import StubBackend


@dataclass
class Mutant:
    name: str
    description: str
    apply: Callable[[], contextlib.AbstractContextManager]
    # Some defects are deliberately covered by unit tests instead of by the
    # agent-level suite; those are expected to survive here.
    expected_to_survive: bool = False
    covered_by: Optional[str] = None


@contextlib.contextmanager
def _patch(obj: object, attr: str, value: object) -> Iterator[None]:
    original = getattr(obj, attr)
    setattr(obj, attr, value)
    try:
        yield
    finally:
        setattr(obj, attr, original)


def _no_output_guard() -> contextlib.AbstractContextManager:
    return _patch(triage_mod, "guard_output", lambda result, **kw: (result, []))


def _no_refund_path() -> contextlib.AbstractContextManager:
    return _patch(llm, "_REFUND_WORDS", ("zzz-never-matches",))


def _no_size_cap() -> contextlib.AbstractContextManager:
    return _patch(guardrails, "MAX_TICKET_CHARS", 10**9)


def _no_output_pii_strip() -> contextlib.AbstractContextManager:
    return _patch(guardrails, "_strip_pii", lambda text: (text, 0))


def _no_order_lookup() -> contextlib.AbstractContextManager:
    return _patch(llm, "_ORDER_RE", __import__("re").compile(r"(?!x)x"))


def _refund_threshold_disabled() -> contextlib.AbstractContextManager:
    return _patch(guardrails, "REFUND_HUMAN_APPROVAL_THRESHOLD", 10**9)


MUTANTS = [
    Mutant("output_guardrail_disabled", "guard_output becomes a no-op", _no_output_guard),
    Mutant("refund_path_removed", "agent never recognises a refund request", _no_refund_path),
    Mutant("input_size_cap_removed", "oversized tickets reach the model", _no_size_cap),
    Mutant("order_lookup_removed", "order ids are never extracted", _no_order_lookup),
    Mutant(
        "refund_threshold_disabled",
        "high-value refunds are auto-approved",
        _refund_threshold_disabled,
        # The stub escalates from the policy tool's own ceiling, so the config
        # threshold is a second line of defence and is unit-tested instead.
        expected_to_survive=True,
        covered_by="tests/test_guardrails.py::test_high_value_refund_forces_human",
    ),
    Mutant(
        "output_pii_strip_removed",
        "PII is not stripped from the drafted reply",
        _no_output_pii_strip,
        # Input redaction means the agent-level suite cannot reach this path.
        expected_to_survive=True,
        covered_by="tests/test_guardrails.py::test_pii_in_reply_is_redacted",
    ),
]


@dataclass
class MutantResult:
    name: str
    description: str
    baseline_failures: int
    mutant_failures: int
    caught: bool
    expected_to_survive: bool
    covered_by: Optional[str]
    newly_failing: list[str]

    @property
    def ok(self) -> bool:
        """Fine if the suite caught it, or if it was known to be out of the
        suite's reach and is covered by a unit test instead."""
        if self.caught:
            return True
        return self.expected_to_survive and self.covered_by is not None


def run_mutation_suite() -> tuple[list[MutantResult], int]:
    backend = StubBackend()
    baseline = run_eval(backend=backend)
    baseline_failed = {r.case_id for r in baseline.results if not r.passed}

    results: list[MutantResult] = []
    for mutant in MUTANTS:
        with mutant.apply():
            report = run_eval(backend=backend)
        failed = {r.case_id for r in report.results if not r.passed}
        newly = sorted(failed - baseline_failed)
        results.append(
            MutantResult(
                name=mutant.name,
                description=mutant.description,
                baseline_failures=len(baseline_failed),
                mutant_failures=len(failed),
                caught=bool(newly),
                expected_to_survive=mutant.expected_to_survive,
                covered_by=mutant.covered_by,
                newly_failing=newly,
            )
        )

    # Unexpected survivors are the only real problem.
    unexpected = sum(
        1 for r in results if not r.caught and not r.expected_to_survive
    )
    return results, unexpected
