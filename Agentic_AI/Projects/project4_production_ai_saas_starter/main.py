"""Project 4 — Production AI SaaS: support-ticket triage agent.

    python main.py demo "Where is my order A1002?"
    python main.py eval
    python main.py reliability --runs 8

Runs without an API key against a deterministic stub backend, so the eval
harness is reproducible in CI. Set ANTHROPIC_API_KEY (or --provider anthropic)
to run against Claude.
"""

import argparse
import json
import sys

from app.agent.triage import triage
from app.evals.mutation import run_mutation_suite
from app.evals.reliability import run_reliability, write_reliability
from app.evals.runner import run_eval, write_report
from app.llm import get_backend


def cmd_demo(args: argparse.Namespace) -> int:
    backend = get_backend(args.provider)
    run = triage(args.ticket, backend=backend, case_id="demo")
    path = run.trace.write()

    if not run.ok:
        print(f"[FAIL] {run.error}")
        print(f"trace: {path} ({run.trace.trace_id})")
        return 1

    print(json.dumps(run.result.model_dump(), indent=2))
    print()
    print(f"provider     : {run.trace.provider}")
    print(f"tools called : {', '.join(run.trace.tools_called) or '—'}")
    print(f"violations   : {', '.join(v.code for v in run.violations) or '—'}")
    print(f"tokens       : {run.trace.input_tokens} in / {run.trace.output_tokens} out")
    print(f"cost         : ${run.trace.cost_usd:.5f}")
    print(f"latency      : {run.trace.duration_ms} ms")
    print(f"trace        : {path} ({run.trace.trace_id})")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    backend = get_backend(args.provider)
    report = run_eval(backend=backend)
    json_path, md_path = write_report(report)

    print(f"provider   : {report.provider}")
    print(f"cases      : {report.cases_passed}/{report.cases_total} "
          f"({report.case_pass_rate:.0%})")
    print(f"assertions : {report.checks_passed}/{report.checks_total} "
          f"({report.check_pass_rate:.0%})")
    print(f"cost/case  : ${report.cost_per_case:.5f}")
    print(f"latency    : p50 {report.p50_ms} ms · p95 {report.p95_ms} ms")
    print(f"report     : {md_path}")
    print(f"results    : {json_path}")

    for r in report.results:
        if r.passed:
            continue
        print(f"\nFAIL {r.case_id} (trace {r.trace_id})")
        for c in r.checks:
            if not c.passed:
                print(f"  - {c.name} — {c.detail}")

    # Non-zero exit so CI can gate on the pass rate.
    return 0 if report.cases_passed == report.cases_total else 1


def cmd_reliability(args: argparse.Namespace) -> int:
    backend = get_backend(args.provider)
    report = run_reliability(runs=args.runs, backend=backend)
    path = write_reliability(report)

    print(f"provider          : {report.provider}")
    print(f"runs per case     : {report.runs}")
    print(f"all-pass rounds   : {report.all_pass_streak}/{report.runs}")
    print(f"always passing    : {len(report.fully_reliable)}/{len(report.cases)}")
    print(f"flaky             : {', '.join(report.flaky) or '—'}")
    print(f"always failing    : {', '.join(report.always_failing) or '—'}")
    print(f"report            : {path}")
    return 0 if report.all_pass_streak == report.runs else 1


def cmd_mutation(args: argparse.Namespace) -> int:
    """Break the agent on purpose and check the eval suite notices."""
    results, unexpected = run_mutation_suite()
    for r in results:
        if r.caught:
            status = f"CAUGHT  (+{len(r.newly_failing)} failing)"
        elif r.expected_to_survive:
            status = f"survived — covered by {r.covered_by}"
        else:
            status = "SURVIVED — eval suite has a hole here"
        print(f"{'ok ' if r.ok else 'GAP'} {r.name:28} {status}")
        if r.newly_failing:
            print(f"      {', '.join(r.newly_failing)}")
    print(f"\nunexpected survivors: {unexpected}")
    return 0 if unexpected == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py", description=__doc__)
    parser.add_argument(
        "--provider",
        choices=["stub", "anthropic"],
        default=None,
        help="Model backend. Defaults to anthropic when ANTHROPIC_API_KEY is set.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="Triage a single ticket.")
    demo.add_argument("ticket")
    demo.set_defaults(func=cmd_demo)

    ev = sub.add_parser("eval", help="Run the eval suite and write a report.")
    ev.set_defaults(func=cmd_eval)

    rel = sub.add_parser("reliability", help="Run every case N times.")
    rel.add_argument("--runs", type=int, default=8)
    rel.set_defaults(func=cmd_reliability)

    mut = sub.add_parser("mutation", help="Check the eval suite catches defects.")
    mut.set_defaults(func=cmd_mutation)

    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    sys.exit(args.func(args))
