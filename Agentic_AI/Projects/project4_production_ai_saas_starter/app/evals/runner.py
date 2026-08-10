"""Eval runner.

Scores every case in the dataset assertion by assertion and writes two
artifacts: machine-readable results and a Markdown report with the numbers that
belong in a README — pass rate, cost per task, p50/p95 latency, and the list of
guardrail violations that fired.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from app.config import REPORT_DIR
from app.evals.dataset import CASES, Case
from app.llm import Backend, get_backend
from app.agent.triage import AgentRun, triage


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    checks: list[Check]
    duration_ms: int
    cost_usd: float
    tools_called: list[str]
    violations: list[str]
    trace_id: str
    error: Optional[str] = None
    output: Optional[dict[str, Any]] = None


@dataclass
class EvalReport:
    provider: str
    cases_total: int
    cases_passed: int
    checks_total: int
    checks_passed: int
    total_cost_usd: float
    p50_ms: int
    p95_ms: int
    results: list[CaseResult] = field(default_factory=list)

    @property
    def case_pass_rate(self) -> float:
        return self.cases_passed / self.cases_total if self.cases_total else 0.0

    @property
    def check_pass_rate(self) -> float:
        return self.checks_passed / self.checks_total if self.checks_total else 0.0

    @property
    def cost_per_case(self) -> float:
        return self.total_cost_usd / self.cases_total if self.cases_total else 0.0


def check_case(case: Case, run: AgentRun) -> list[Check]:
    """Evaluate one run against one case's assertions."""
    checks: list[Check] = []

    if case.expect_error:
        ok = (not run.ok) and bool(run.error) and run.error.startswith(case.expect_error)
        checks.append(
            Check(
                f"error startswith {case.expect_error!r}",
                ok,
                f"got {run.error!r}",
            )
        )
        return checks

    checks.append(
        Check("produces valid output", run.ok, run.error or "")
    )
    if not run.ok or run.result is None:
        return checks

    data = run.result.model_dump()

    for field_name, expected in case.expect.items():
        actual = data.get(field_name)
        checks.append(
            Check(
                f"{field_name} == {expected!r}",
                actual == expected,
                f"got {actual!r}",
            )
        )

    called = run.trace.tools_called
    for tool in case.must_call:
        checks.append(
            Check(f"calls {tool}", tool in called, f"called {called}")
        )
    for tool in case.must_not_call:
        checks.append(
            Check(f"does not call {tool}", tool not in called, f"called {called}")
        )

    reply = data.get("draft_reply", "").lower()
    for forbidden in case.forbid_reply:
        checks.append(
            Check(
                f"reply omits {forbidden!r}",
                forbidden.lower() not in reply,
                "found in draft_reply",
            )
        )

    raised = [v.code for v in run.violations]
    for code in case.violations:
        checks.append(Check(f"raises {code}", code in raised, f"raised {raised}"))

    return checks


def run_case(case: Case, backend: Backend) -> CaseResult:
    run = triage(case.ticket, backend=backend, case_id=case.id)
    run.trace.write()
    checks = check_case(case, run)
    return CaseResult(
        case_id=case.id,
        passed=all(c.passed for c in checks),
        checks=checks,
        duration_ms=run.trace.duration_ms,
        cost_usd=run.trace.cost_usd,
        tools_called=run.trace.tools_called,
        violations=[v.code for v in run.violations],
        trace_id=run.trace.trace_id,
        error=run.error,
        output=run.result.model_dump() if run.result else None,
    )


def run_eval(
    cases: Optional[list[Case]] = None,
    backend: Optional[Backend] = None,
) -> EvalReport:
    cases = cases if cases is not None else CASES
    backend = backend or get_backend()

    results = [run_case(case, backend) for case in cases]
    latencies = sorted(r.duration_ms for r in results)

    all_checks = [c for r in results for c in r.checks]
    return EvalReport(
        provider=backend.name,
        cases_total=len(results),
        cases_passed=sum(1 for r in results if r.passed),
        checks_total=len(all_checks),
        checks_passed=sum(1 for c in all_checks if c.passed),
        total_cost_usd=sum(r.cost_usd for r in results),
        p50_ms=_percentile(latencies, 50),
        p95_ms=_percentile(latencies, 95),
        results=results,
    )


def _percentile(sorted_values: list[int], pct: int) -> int:
    if not sorted_values:
        return 0
    idx = min(len(sorted_values) - 1, int(round(pct / 100 * (len(sorted_values) - 1))))
    return sorted_values[idx]


def write_report(report: EvalReport) -> tuple[str, str]:
    os.makedirs(REPORT_DIR, exist_ok=True)
    json_path = os.path.join(REPORT_DIR, "eval_results.json")
    md_path = os.path.join(REPORT_DIR, "eval_report.md")

    with open(json_path, "w", encoding="utf-8") as fh:
        payload = asdict(report)
        payload["case_pass_rate"] = round(report.case_pass_rate, 4)
        payload["check_pass_rate"] = round(report.check_pass_rate, 4)
        payload["cost_per_case_usd"] = round(report.cost_per_case, 6)
        json.dump(payload, fh, indent=2)

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(_markdown(report))

    return json_path, md_path


def _markdown(report: EvalReport) -> str:
    lines = [
        "# Triage agent — eval report",
        "",
        f"**Provider:** `{report.provider}`",
    ]
    if report.provider == "stub":
        lines.append(
            "> Stub backend: these numbers measure the harness and the guardrails, "
            "not model quality. Set `ANTHROPIC_API_KEY` for model numbers."
        )
    # Stub token counts are a character-length estimate, not real usage, so the
    # cost figures under the stub are synthetic and labelled as such.
    synthetic = " *(synthetic)*" if report.provider == "stub" else ""
    lines += [
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Cases passed | {report.cases_passed}/{report.cases_total} "
        f"({report.case_pass_rate:.0%}) |",
        f"| Assertions passed | {report.checks_passed}/{report.checks_total} "
        f"({report.check_pass_rate:.0%}) |",
        f"| Cost per case | ${report.cost_per_case:.4f}{synthetic} |",
        f"| Total cost | ${report.total_cost_usd:.4f}{synthetic} |",
        f"| Latency p50 | {report.p50_ms} ms |",
        f"| Latency p95 | {report.p95_ms} ms |",
        "",
        "## Cases",
        "",
        "| Case | Result | Tools | Violations | ms |",
        "|---|---|---|---|---|",
    ]
    for r in report.results:
        lines.append(
            f"| `{r.case_id}` | {'PASS' if r.passed else 'FAIL'} | "
            f"{', '.join(r.tools_called) or '—'} | "
            f"{', '.join(r.violations) or '—'} | {r.duration_ms} |"
        )

    failures = [r for r in report.results if not r.passed]
    if failures:
        lines += ["", "## Failed assertions", ""]
        for r in failures:
            lines.append(f"### `{r.case_id}` (trace `{r.trace_id}`)")
            for c in r.checks:
                if not c.passed:
                    lines.append(f"- {c.name} — {c.detail}")
            lines.append("")
    return "\n".join(lines) + "\n"
