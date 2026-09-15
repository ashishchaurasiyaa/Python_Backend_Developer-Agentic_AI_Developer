#!/usr/bin/env python3
"""
agent_cli.py — Production AI Agent Runner using argparse
Usage:
    python agent_cli.py run  "Summarise this text" --model gpt-4o --stream
    python agent_cli.py eval --dataset evals.json  --concurrency 5
    python agent_cli.py cost --months 3
"""

import argparse
import json
import sys
from pathlib import Path


# ── Helpers ──────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="AI Agent Runner — manage and evaluate LLM agents",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Global flags (before subcommand)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument(
        "--config", type=Path, default=Path("~/.agent/config.json"),
        help="Path to config file",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── run ──────────────────────────────────────────────────────────────────
    run_p = subparsers.add_parser("run", help="Run agent with a prompt")
    run_p.add_argument("prompt", help="Prompt text (or @file.txt)")
    run_p.add_argument("--model", "-m", default="gpt-4o-mini")
    run_p.add_argument("--temperature", "-t", type=float, default=0.7)
    run_p.add_argument("--max-tokens", type=int, default=2048, dest="max_tokens")
    run_p.add_argument("--stream", action="store_true")
    run_p.add_argument("--output", type=Path, help="Save response to file")
    run_p.add_argument(
        "--tools", nargs="*", default=[],
        choices=["web_search", "calculator", "code_runner", "file_read"],
        help="Tools to enable",
    )

    # ── eval ─────────────────────────────────────────────────────────────────
    eval_p = subparsers.add_parser("eval", help="Run evaluation suite")
    eval_p.add_argument("--dataset", type=Path, required=True)
    eval_p.add_argument("--model", default="gpt-4o-mini")
    eval_p.add_argument("--concurrency", type=int, default=3)
    eval_p.add_argument("--output-dir", type=Path, default=Path("eval_results"),
                         dest="output_dir")
    eval_p.add_argument("--fail-fast", action="store_true", dest="fail_fast")

    # ── cost ─────────────────────────────────────────────────────────────────
    cost_p = subparsers.add_parser("cost", help="Show usage cost report")
    cost_p.add_argument("--months", type=int, default=1)
    cost_p.add_argument("--model", help="Filter by model (optional)")
    cost_group = cost_p.add_mutually_exclusive_group()
    cost_group.add_argument("--csv", action="store_true")
    cost_group.add_argument("--json-output", action="store_true", dest="json_output")

    return parser


# ── Handlers ─────────────────────────────────────────────────────────────────

def handle_run(args) -> int:
    print(f"[RUN]  model={args.model}  temperature={args.temperature}")
    print(f"       max_tokens={args.max_tokens}  stream={args.stream}")
    print(f"       tools={args.tools}")
    print(f"       prompt={args.prompt!r}")

    # Simulate LLM call (replace with real client)
    response = {
        "id": "resp-abc123",
        "model": args.model,
        "content": f"Mock response to: {args.prompt}",
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }

    output_text = response["content"]
    if args.output:
        args.output.write_text(output_text)
        print(f"Saved to {args.output}")
    else:
        print("\nResponse:", output_text)

    return 0


def handle_eval(args) -> int:
    if not args.dataset.exists():
        print(f"Error: dataset {args.dataset} not found", file=sys.stderr)
        return 1

    print(f"[EVAL] dataset={args.dataset}  model={args.model}")
    print(f"       concurrency={args.concurrency}  fail_fast={args.fail_fast}")
    # Load dataset and run evals …
    return 0


def handle_cost(args) -> int:
    print(f"[COST] months={args.months}  model={args.model or 'all'}")
    data = {"months": args.months, "total_usd": 12.34, "breakdown": []}
    if args.csv:
        print("month,usd")
    elif args.json_output:
        print(json.dumps(data, indent=2))
    else:
        print(f"Total cost (last {args.months} month(s)): $12.34")
    return 0


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        print(f"[DEBUG] command={args.command}  config={args.config}")

    handlers = {
        "run":  handle_run,
        "eval": handle_eval,
        "cost": handle_cost,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
