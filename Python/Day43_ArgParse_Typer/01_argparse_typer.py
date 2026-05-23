"""
Day 43 — argparse & typer: CLI Tools Complete Guide
====================================================
Target: Python Backend Developer + Agentic AI (5 YOE)

CONTENTS
--------
PART A — argparse (stdlib)
  A1. Basic parser: positional + optional args
  A2. Argument types, choices, defaults, required
  A3. Flags / store_true / store_false
  A4. Subcommands (subparsers)
  A5. Argument groups & mutually exclusive groups
  A6. nargs (multiple values)
  A7. Custom type functions
  A8. Reading from a config file (ArgumentDefaultsHelpFormatter)
  A9. Full CLI app: AI Agent Runner

PART B — typer (third-party, production favourite)
  B1. Why typer over argparse
  B2. Basic typer app: Option vs Argument
  B3. Callbacks & version flag
  B4. Subcommand groups (typer app.add_typer)
  B5. Enum choices via Python Enum
  B6. Prompt + confirm + password
  B7. Progress bar (typer.progressbar)
  B8. Full CLI app: LLM Agent CLI with typer

PART C — Production Patterns
  C1. Config layering: env → file → CLI
  C2. Testing CLI apps (CliRunner / typer test client)
  C3. Rich integration for beautiful output
  C4. Packaging CLIs with pyproject.toml entry points

PART D — Interview Q&A (10 questions)
"""

# ════════════════════════════════════════════════════════════
# PART A — argparse (stdlib)
# ════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# A1. Basic parser: positional + optional args
# ─────────────────────────────────────────────
"""
WHAT  — argparse parses sys.argv into structured Python objects.
WHY   — Gives every CLI tool --help, type coercion, and error messages for free.
HOW   — Create ArgumentParser → add_argument → parse_args()
"""

import argparse
import sys
import os
import json
import subprocess
import textwrap
from pathlib import Path
from typing import Optional
from enum import Enum


def demo_basic_parser():
    """A1 — positional + optional args."""

    parser = argparse.ArgumentParser(
        prog="ask",
        description="Ask an AI model a question",
        epilog="Example: ask 'What is Python?' --model gpt-4o",
    )

    # Positional (required, no --flag)
    parser.add_argument("prompt", help="The question to ask the AI")

    # Optional (keyword)
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="Model name (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Sampling temperature 0.0-2.0",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        dest="max_tokens",          # normalised attribute name
        help="Maximum response tokens",
    )

    # Simulate: ask "Hello!" --temperature 0.9
    args = parser.parse_args(["Hello!", "--temperature", "0.9"])

    print(f"Prompt     : {args.prompt}")
    print(f"Model      : {args.model}")
    print(f"Temperature: {args.temperature}")
    print(f"Max tokens : {args.max_tokens}")
    # Prompt     : Hello!
    # Model      : gpt-4o-mini
    # Temperature: 0.9
    # Max tokens : 512


# ─────────────────────────────────────────────
# A2. Argument types, choices, defaults, required
# ─────────────────────────────────────────────

def demo_types_and_choices():
    """A2 — type=, choices=, required=, default=."""

    parser = argparse.ArgumentParser()

    # type= performs automatic coercion + error on bad input
    parser.add_argument("--port", type=int, default=8000)

    # choices= restricts allowed values
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        dest="log_level",
    )

    # required=True forces the flag to be present
    parser.add_argument("--api-key", required=True, dest="api_key",
                        help="OpenAI / Anthropic API key")

    # type=Path from pathlib — automatic conversion
    parser.add_argument("--output", type=Path, default=Path("output.json"))

    args = parser.parse_args([
        "--api-key", "sk-test-abc123",
        "--log-level", "DEBUG",
        "--port", "9000",
    ])

    print(f"Port     : {args.port!r}  → {type(args.port).__name__}")   # int
    print(f"Log level: {args.log_level}")
    print(f"API key  : {args.api_key[:8]}...")
    print(f"Output   : {args.output!r} → {type(args.output).__name__}") # Path


# ─────────────────────────────────────────────
# A3. Flags / store_true / store_false
# ─────────────────────────────────────────────

def demo_flags():
    """A3 — Boolean flags with action='store_true'."""

    parser = argparse.ArgumentParser()

    # --verbose is False by default; becomes True when flag present
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose output")

    # --no-cache starts as True; --no-cache flag sets it False
    parser.add_argument("--no-cache", action="store_true", dest="no_cache",
                        help="Disable response cache")

    # --stream flag
    parser.add_argument("--stream", action="store_true",
                        help="Stream the response token by token")

    # Count: -vvv → args.verbosity == 3
    parser.add_argument("-V", action="count", default=0, dest="verbosity",
                        help="Increase verbosity (stackable: -VVV)")

    args = parser.parse_args(["--verbose", "--stream", "-VVV"])
    print(f"Verbose   : {args.verbose}")        # True
    print(f"No cache  : {args.no_cache}")       # False
    print(f"Stream    : {args.stream}")         # True
    print(f"Verbosity : {args.verbosity}")      # 3


# ─────────────────────────────────────────────
# A4. Subcommands (subparsers)
# ─────────────────────────────────────────────

def demo_subcommands():
    """
    A4 — Subparsers for multi-command CLIs.

    Pattern used by git, docker, aws, etc.:
        mytool <command> [options]
        mytool run  --model gpt-4o
        mytool list --filter active
        mytool stop --id abc123
    """

    parser = argparse.ArgumentParser(prog="agent")
    subparsers = parser.add_subparsers(dest="command", required=True,
                                       help="Available commands")

    # --- run ---
    run_parser = subparsers.add_parser("run", help="Run the AI agent")
    run_parser.add_argument("prompt", help="Prompt to send")
    run_parser.add_argument("--model", default="gpt-4o-mini")
    run_parser.add_argument("--stream", action="store_true")

    # --- list ---
    list_parser = subparsers.add_parser("list", help="List recent sessions")
    list_parser.add_argument("--limit", type=int, default=10)
    list_parser.add_argument("--filter",
                              choices=["active", "completed", "failed"],
                              default="all")

    # --- stop ---
    stop_parser = subparsers.add_parser("stop", help="Stop a running agent")
    stop_parser.add_argument("session_id", help="Session ID to stop")
    stop_parser.add_argument("--force", action="store_true")

    # Dispatch based on command
    def handle(args):
        if args.command == "run":
            print(f"[RUN] model={args.model}, prompt={args.prompt!r}, "
                  f"stream={args.stream}")
        elif args.command == "list":
            print(f"[LIST] limit={args.limit}, filter={args.filter}")
        elif args.command == "stop":
            print(f"[STOP] session={args.session_id}, force={args.force}")

    handle(parser.parse_args(["run", "Hello!", "--model", "gpt-4o", "--stream"]))
    handle(parser.parse_args(["list", "--limit", "5", "--filter", "active"]))
    handle(parser.parse_args(["stop", "sess-abc123", "--force"]))


# ─────────────────────────────────────────────
# A5. Argument groups & mutually exclusive groups
# ─────────────────────────────────────────────

def demo_groups():
    """A5 — Logical grouping and mutual exclusion."""

    parser = argparse.ArgumentParser(prog="llm-call")

    # ── Input group ──────────────────────────────
    input_group = parser.add_argument_group("Input Options")
    input_group.add_argument("--prompt", help="Inline prompt text")
    input_group.add_argument("--file", type=Path, help="Read prompt from file")

    # ── Mutually exclusive: --json XOR --text ────
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json-output", action="store_true",
                               dest="json_output",
                               help="Output as JSON")
    output_group.add_argument("--text-output", action="store_true",
                               dest="text_output",
                               help="Output as plain text (default)")

    # This raises SystemExit if both flags given — argparse handles the error
    args = parser.parse_args(["--prompt", "Tell me a joke", "--json-output"])
    print(f"Prompt     : {args.prompt}")
    print(f"JSON output: {args.json_output}")
    print(f"Text output: {args.text_output}")


# ─────────────────────────────────────────────
# A6. nargs — multiple values
# ─────────────────────────────────────────────

def demo_nargs():
    """A6 — nargs for consuming multiple values."""

    parser = argparse.ArgumentParser()

    # nargs='+'  → one or more values → list
    parser.add_argument("--tools", nargs="+",
                        help="Tool names to enable")

    # nargs='*'  → zero or more values → list (can be empty)
    parser.add_argument("--tags", nargs="*", default=[])

    # nargs=N    → exactly N values → list of N
    parser.add_argument("--temperature-range", nargs=2, type=float,
                        metavar=("MIN", "MAX"), dest="temp_range")

    # nargs='?'  → 0 or 1 values (const used if flag given without value)
    parser.add_argument("--output", nargs="?", const="output.json",
                        default=None)

    args = parser.parse_args([
        "--tools", "web_search", "calculator", "code_runner",
        "--tags", "prod", "v2",
        "--temperature-range", "0.2", "0.9",
        "--output",
    ])
    print(f"Tools      : {args.tools}")
    print(f"Tags       : {args.tags}")
    print(f"Temp range : {args.temp_range}")
    print(f"Output     : {args.output}")   # "output.json" (const)


# ─────────────────────────────────────────────
# A7. Custom type functions
# ─────────────────────────────────────────────

def temperature_type(value: str) -> float:
    """Custom argparse type: float in [0.0, 2.0]."""
    try:
        f = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid float")
    if not (0.0 <= f <= 2.0):
        raise argparse.ArgumentTypeError(
            f"Temperature must be between 0.0 and 2.0, got {f}"
        )
    return f


def json_type(value: str) -> dict:
    """Custom argparse type: inline JSON string → dict."""
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"Invalid JSON: {exc}")


def demo_custom_types():
    parser = argparse.ArgumentParser()
    parser.add_argument("--temperature", type=temperature_type, default=0.7)
    parser.add_argument("--extra-params", type=json_type, dest="extra",
                        default={})

    args = parser.parse_args([
        "--temperature", "0.9",
        "--extra-params", '{"top_p": 0.95, "seed": 42}',
    ])
    print(f"Temperature : {args.temperature}")
    print(f"Extra params: {args.extra}")

    # Bad value would print: error: argument --temperature: Temperature must be
    # between 0.0 and 2.0, got 3.0


# ─────────────────────────────────────────────
# A8. ArgumentDefaultsHelpFormatter + fromfile_prefix_chars
# ─────────────────────────────────────────────

def demo_help_formatter():
    """
    A8 — Formatter that automatically appends "(default: X)" to help strings.
         Also: fromfile_prefix_chars lets users pass @args.txt.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        fromfile_prefix_chars="@",   # agent @config.txt  reads args from file
    )
    parser.add_argument("--model", default="gpt-4o-mini",
                        help="Model to use")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Sampling temperature")
    parser.add_argument("--max-tokens", type=int, default=512,
                        dest="max_tokens", help="Token limit")

    # Running  python agent.py --help  would show:
    # --model MODEL           Model to use (default: gpt-4o-mini)
    # --temperature FLOAT     Sampling temperature (default: 0.7)
    # --max-tokens INT        Token limit (default: 512)

    # fromfile: create a @config.txt that contains --model\ngpt-4o\n etc.
    print("ArgumentDefaultsHelpFormatter demo registered (see --help output)")


# ─────────────────────────────────────────────
# A9. Full CLI App: AI Agent Runner
# ─────────────────────────────────────────────

AGENT_CLI_CODE = '''#!/usr/bin/env python3
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
        print("\\nResponse:", output_text)

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
    print(f"[COST] months={args.months}  model={args.model or \'all\'}")
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
'''

print("=== A9: Full CLI App (agent_cli.py) ===")
print(AGENT_CLI_CODE[:500], "…")

# Save the full CLI app alongside this file
Path("/Users/youngmanindia/Documents/PythonRevision/Python/Day43_ArgParse_Typer/agent_cli.py").write_text(AGENT_CLI_CODE)
print("Saved → Day43_ArgParse_Typer/agent_cli.py")


# ════════════════════════════════════════════════════════════
# PART B — typer (third-party)
# ════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# B1. Why typer over argparse
# ─────────────────────────────────────────────
"""
WHAT  — typer is a Python library built on top of click that builds CLIs
        purely from type annotations and default values.

WHY better than argparse:
  ✅ Zero boilerplate  — no add_argument() calls
  ✅ Type annotations  — int/float/Path/Enum auto-enforced
  ✅ Auto --help       — docstring becomes description
  ✅ Autocompletion    — shell completion out of the box
  ✅ Rich integration  — pretty tables, progress bars
  ✅ Testing           — CliRunner built-in

HOW — pip install "typer[all]"   (includes rich + shellingham)
"""

# ─────────────────────────────────────────────
# B2. Basic typer app: Option vs Argument
# ─────────────────────────────────────────────

TYPER_BASIC = '''import typer

app = typer.Typer()

@app.command()
def ask(
    # Argument  → positional, required (no --flag)
    prompt: str = typer.Argument(..., help="The prompt to send"),

    # Option    → keyword, with -- prefix
    model: str        = typer.Option("gpt-4o-mini", "--model", "-m"),
    temperature: float = typer.Option(0.7, min=0.0, max=2.0),
    max_tokens: int   = typer.Option(512, "--max-tokens"),
    stream: bool      = typer.Option(False, "--stream/--no-stream"),
    output: typer.FileTextWrite = typer.Option(None, "--output", "-o"),
):
    """Ask the AI agent a question and print the response."""
    typer.echo(f"Model      : {model}")
    typer.echo(f"Temperature: {temperature}")
    typer.echo(f"Prompt     : {prompt!r}")

    response = f"Mock response to: {prompt}"

    if output:
        output.write(response)
        typer.echo("Saved to file.")
    elif stream:
        for char in response:
            typer.echo(char, nl=False)
        typer.echo()
    else:
        typer.echo(response)


if __name__ == "__main__":
    app()
'''
print("\n=== B2: Basic typer app ===")
print(TYPER_BASIC)


# ─────────────────────────────────────────────
# B3. Callbacks & version flag
# ─────────────────────────────────────────────

TYPER_VERSION = '''import typer
from typing import Optional

__version__ = "1.4.2"

def version_callback(value: bool):
    if value:
        typer.echo(f"Agent CLI v{__version__}")
        raise typer.Exit()          # clean exit without running command

app = typer.Typer()

@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V",
        callback=version_callback,
        is_eager=True,             # evaluated BEFORE other options
        help="Show version and exit",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Agent CLI — manage LLM agents from the terminal."""
    if verbose:
        typer.echo("[DEBUG] Verbose mode on")


@app.command()
def run(prompt: str = typer.Argument(...)):
    """Run the agent."""
    typer.echo(f"Running: {prompt!r}")


if __name__ == "__main__":
    app()

# Usage:
#   python agent.py --version   →  Agent CLI v1.4.2
#   python agent.py run "Hello"
'''
print("\n=== B3: Version callback ===")
print(TYPER_VERSION)


# ─────────────────────────────────────────────
# B4. Subcommand groups
# ─────────────────────────────────────────────

TYPER_SUBCOMMANDS = '''import typer

app  = typer.Typer(help="Agent CLI")
run_app  = typer.Typer(help="Run commands")
eval_app = typer.Typer(help="Evaluation commands")

app.add_typer(run_app,  name="run")
app.add_typer(eval_app, name="eval")


@run_app.command("prompt")
def run_prompt(prompt: str, model: str = "gpt-4o-mini"):
    """Run a single prompt."""
    typer.echo(f"[prompt] model={model}  prompt={prompt!r}")


@run_app.command("file")
def run_file(path: typer.FileText = typer.Argument(...)):
    """Run prompts from a file (one per line)."""
    for line in path:
        typer.echo(f"[file] {line.strip()!r}")


@eval_app.command("suite")
def eval_suite(dataset: str, concurrency: int = 3):
    """Run evaluation suite."""
    typer.echo(f"[eval] dataset={dataset}  concurrency={concurrency}")


@eval_app.command("single")
def eval_single(prompt: str, expected: str):
    """Evaluate a single prompt/expected pair."""
    typer.echo(f"[eval-single] prompt={prompt!r}  expected={expected!r}")


if __name__ == "__main__":
    app()

# Usage:
#   python cli.py run prompt "Hello world"
#   python cli.py run file prompts.txt
#   python cli.py eval suite --dataset evals.json --concurrency 5
#   python cli.py eval single "capital of France" "Paris"
'''
print("\n=== B4: Subcommand groups ===")
print(TYPER_SUBCOMMANDS)


# ─────────────────────────────────────────────
# B5. Enum choices
# ─────────────────────────────────────────────

TYPER_ENUM = '''import typer
from enum import Enum

class ModelTier(str, Enum):
    FAST   = "fast"
    SMART  = "smart"
    VISION = "vision"

class LogLevel(str, Enum):
    DEBUG   = "DEBUG"
    INFO    = "INFO"
    WARNING = "WARNING"
    ERROR   = "ERROR"

app = typer.Typer()

@app.command()
def run(
    prompt: str,
    tier: ModelTier   = typer.Option(ModelTier.SMART, case_sensitive=False),
    log_level: LogLevel = typer.Option(LogLevel.INFO),
):
    """Run the agent — model tier controls which model is selected."""
    model_map = {
        ModelTier.FAST:   "gpt-4o-mini",
        ModelTier.SMART:  "gpt-4o",
        ModelTier.VISION: "gpt-4o-vision",
    }
    model = model_map[tier]
    typer.echo(f"tier={tier.value}  model={model}  log_level={log_level.value}")

if __name__ == "__main__":
    app()

# Usage:
#   python cli.py run "Hello" --tier smart --log-level DEBUG
#   python cli.py run "Hello" --tier FAST   (case_sensitive=False)
'''
print("\n=== B5: Enum choices ===")
print(TYPER_ENUM)


# ─────────────────────────────────────────────
# B6. Prompt + confirm + password
# ─────────────────────────────────────────────

TYPER_PROMPTS = '''import typer

app = typer.Typer()

@app.command()
def setup():
    """Interactive first-time setup."""

    # prompt() — blocks until user types input
    name = typer.prompt("Your name")

    # prompt() with default
    model = typer.prompt("Default model", default="gpt-4o-mini")

    # password — hides typing + auto-confirmation prompt
    api_key = typer.prompt("API key", hide_input=True, confirmation_prompt=True)

    # confirm() — yes/no gate (abort=True raises Exit on "no")
    ok = typer.confirm(f"Save config for {name!r}?", abort=True)

    typer.echo(f"Saved! model={model}  key={api_key[:6]}...")
    typer.secho("Setup complete ✓", fg=typer.colors.GREEN, bold=True)

if __name__ == "__main__":
    app()
'''
print("\n=== B6: Prompt + confirm + password ===")
print(TYPER_PROMPTS)


# ─────────────────────────────────────────────
# B7. Progress bar
# ─────────────────────────────────────────────

TYPER_PROGRESS = '''import typer
import time

app = typer.Typer()

@app.command()
def batch_eval(dataset: str, concurrency: int = 3):
    """Evaluate a dataset with a progress bar."""

    # Simulate loading
    items = list(range(50))  # 50 eval items

    results = []
    with typer.progressbar(items, label="Evaluating", length=len(items)) as progress:
        for item_id in progress:
            # Replace with real eval call
            time.sleep(0.05)
            results.append({"id": item_id, "pass": item_id % 5 != 0})

    passed = sum(1 for r in results if r["pass"])
    typer.echo(f"\\nResults: {passed}/{len(results)} passed")
    typer.secho(f"Accuracy: {passed/len(results):.1%}", fg=typer.colors.CYAN)

if __name__ == "__main__":
    app()
'''
print("\n=== B7: Progress bar ===")
print(TYPER_PROGRESS)


# ─────────────────────────────────────────────
# B8. Full typer CLI app: LLM Agent CLI
# ─────────────────────────────────────────────

TYPER_FULL_APP = '''#!/usr/bin/env python3
"""
llm_agent_cli.py — Production LLM Agent CLI using typer + rich
Install: pip install "typer[all]"
"""

import typer
import json
import time
from enum import Enum
from pathlib import Path
from typing import Optional

# ── Enums ────────────────────────────────────────────────────────────────────

class ModelChoice(str, Enum):
    MINI   = "gpt-4o-mini"
    GPT4O  = "gpt-4o"
    CLAUDE = "claude-3-5-sonnet-20241022"
    LOCAL  = "ollama/llama3"

class OutputFormat(str, Enum):
    TEXT = "text"
    JSON = "json"
    MD   = "markdown"

# ── App ──────────────────────────────────────────────────────────────────────

app      = typer.Typer(name="llm", help="LLM Agent CLI", add_completion=True)
run_app  = typer.Typer(help="Run agent commands")
eval_app = typer.Typer(help="Evaluation commands")

app.add_typer(run_app,  name="run")
app.add_typer(eval_app, name="eval")

__version__ = "2.0.0"

def version_cb(value: bool):
    if value:
        typer.echo(f"llm-agent v{__version__}")
        raise typer.Exit()

@app.callback()
def global_opts(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", callback=version_cb, is_eager=True
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", envvar="LLM_VERBOSE"),
):
    """LLM Agent — call models, run evals, manage sessions."""


# ── run prompt ───────────────────────────────────────────────────────────────

@run_app.command("prompt")
def run_prompt(
    prompt: str = typer.Argument(..., help="The prompt to send"),
    model: ModelChoice   = typer.Option(ModelChoice.MINI, "--model", "-m"),
    temperature: float   = typer.Option(0.7, min=0.0, max=2.0, show_default=True),
    max_tokens: int      = typer.Option(2048, "--max-tokens"),
    stream: bool         = typer.Option(False, "--stream/--no-stream"),
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--format", "-f"),
    save: Optional[Path] = typer.Option(None, "--save", "-s", help="Save to file"),
    system: Optional[str] = typer.Option(None, "--system", help="System prompt"),
    tools: Optional[list[str]] = typer.Option(None, "--tool", "-t",
                                               help="Enable a tool (repeatable)"),
):
    """Send a prompt to an LLM and display the response."""

    typer.secho(f"Model: {model.value}  T={temperature}", dim=True)

    # Simulate LLM call
    start = time.time()
    response_text = f"Response to: {prompt}"  # Replace with real call
    elapsed = time.time() - start

    # Format output
    if output_format == OutputFormat.JSON:
        result = {
            "model": model.value,
            "prompt": prompt,
            "response": response_text,
            "elapsed_s": round(elapsed, 3),
        }
        typer.echo(json.dumps(result, indent=2))
    elif output_format == OutputFormat.MD:
        typer.echo(f"## Response\\n\\n{response_text}\\n")
    else:
        typer.echo(response_text)

    if save:
        save.write_text(response_text)
        typer.secho(f"Saved → {save}", fg=typer.colors.GREEN)

    typer.secho(f"\\n⏱  {elapsed:.2f}s", dim=True)


# ── run batch ────────────────────────────────────────────────────────────────

@run_app.command("batch")
def run_batch(
    file: typer.FileText = typer.Argument(..., help="File with prompts (one/line)"),
    model: ModelChoice   = typer.Option(ModelChoice.MINI),
    output_dir: Path     = typer.Option(Path("batch_out"), "--output-dir"),
):
    """Run multiple prompts from a file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    prompts = [line.strip() for line in file if line.strip()]

    with typer.progressbar(prompts, label="Processing", length=len(prompts)) as bar:
        for i, prompt in enumerate(bar):
            response = f"Mock response to: {prompt}"
            (output_dir / f"response_{i:04d}.txt").write_text(response)

    typer.secho(f"Done! {len(prompts)} responses in {output_dir}/",
                fg=typer.colors.GREEN, bold=True)


# ── eval suite ───────────────────────────────────────────────────────────────

@eval_app.command("suite")
def eval_suite(
    dataset:     Path = typer.Argument(..., help="JSON eval dataset"),
    model: ModelChoice = typer.Option(ModelChoice.MINI),
    concurrency: int  = typer.Option(3, min=1, max=20),
    fail_fast: bool   = typer.Option(False, "--fail-fast"),
    output_dir:  Path = typer.Option(Path("eval_results"), "--output-dir"),
):
    """Run the full evaluation suite against a dataset."""
    if not dataset.exists():
        typer.secho(f"Dataset not found: {dataset}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    data = json.loads(dataset.read_text())
    items = data if isinstance(data, list) else data.get("items", [])
    output_dir.mkdir(parents=True, exist_ok=True)

    passed = failed = 0
    with typer.progressbar(items, label="Evaluating", length=len(items)) as bar:
        for item in bar:
            # Replace with real eval logic
            result = True  # mock
            if result:
                passed += 1
            else:
                failed += 1
                if fail_fast:
                    typer.secho("\\nFAIL — stopping (--fail-fast)", fg=typer.colors.RED)
                    break

    total = passed + failed
    colour = typer.colors.GREEN if failed == 0 else typer.colors.YELLOW
    typer.secho(f"\\nResults: {passed}/{total} passed ({passed/total:.1%})", fg=colour)
    raise typer.Exit(code=0 if failed == 0 else 1)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()

# Usage:
#   python llm_agent_cli.py run prompt "Hello world" --model gpt-4o --stream
#   python llm_agent_cli.py run batch prompts.txt --output-dir out/
#   python llm_agent_cli.py eval suite evals.json --concurrency 5 --fail-fast
#   python llm_agent_cli.py --version
'''

print("\n=== B8: Full typer CLI app ===")
print(TYPER_FULL_APP[:600], "…")

# Save the full typer app
Path("/Users/youngmanindia/Documents/PythonRevision/Python/Day43_ArgParse_Typer/llm_agent_cli.py").write_text(TYPER_FULL_APP)
print("Saved → Day43_ArgParse_Typer/llm_agent_cli.py")


# ════════════════════════════════════════════════════════════
# PART C — Production Patterns
# ════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# C1. Config layering: env → file → CLI
# ─────────────────────────────────────────────
"""
PRODUCTION PATTERN — Priority (highest → lowest):
  1. CLI args       (--model gpt-4o)
  2. Environment    (export LLM_MODEL=gpt-4o)
  3. Config file    (~/.agent/config.json)
  4. Hard defaults  (gpt-4o-mini)
"""

import os
from dataclasses import dataclass, field, asdict


@dataclass
class AgentConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 2048
    api_key: str = ""
    log_level: str = "INFO"

    @classmethod
    def from_file(cls, path: Path) -> "AgentConfig":
        """Load from JSON config file."""
        if path.exists():
            data = json.loads(path.read_text())
            return cls(**{k: v for k, v in data.items()
                         if k in cls.__dataclass_fields__})
        return cls()

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load from environment variables (LLM_MODEL, LLM_TEMPERATURE, …)."""
        return cls(
            model       = os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7")),
            max_tokens  = int(os.environ.get("LLM_MAX_TOKENS", "2048")),
            api_key     = os.environ.get("OPENAI_API_KEY", ""),
            log_level   = os.environ.get("LOG_LEVEL", "INFO"),
        )

    def merge_cli(self, args: argparse.Namespace) -> "AgentConfig":
        """Override with explicit CLI args (only non-default values)."""
        overrides = {
            k: v for k, v in vars(args).items()
            if v is not None and k in self.__dataclass_fields__
        }
        return AgentConfig(**{**asdict(self), **overrides})


def resolve_config(args: argparse.Namespace) -> AgentConfig:
    """
    Layered config resolution:
      file  →  env  →  CLI  →  final config
    """
    config_path = Path(args.config) if hasattr(args, "config") else Path("~/.agent/config.json")
    config_path = config_path.expanduser()

    file_cfg = AgentConfig.from_file(config_path)     # lowest priority
    env_cfg  = AgentConfig.from_env()                  # overrides file
    return env_cfg.merge_cli(args)                      # CLI wins


# Demo
parser_cfg = argparse.ArgumentParser()
parser_cfg.add_argument("--model", default=None)
parser_cfg.add_argument("--temperature", type=float, default=None)
parser_cfg.add_argument("--config", default="~/.agent/config.json")

args_cfg = parser_cfg.parse_args(["--model", "gpt-4o"])
final_cfg = resolve_config(args_cfg)
print("\n=== C1: Config Layering ===")
print(f"Final config: model={final_cfg.model!r} temp={final_cfg.temperature}")


# ─────────────────────────────────────────────
# C2. Testing CLI apps
# ─────────────────────────────────────────────
"""
ARGPARSE testing — invoke parse_args() directly:
  args = parser.parse_args(["run", "Hello", "--model", "gpt-4o"])
  assert args.model == "gpt-4o"

TYPER testing — use typer.testing.CliRunner:
  from typer.testing import CliRunner
  runner = CliRunner()
  result = runner.invoke(app, ["run", "prompt", "Hello"])
  assert result.exit_code == 0
  assert "Response" in result.output
"""

print("\n=== C2: CLI Testing Patterns ===")

# argparse test pattern (no external dependency)
def make_run_parser():
    p = argparse.ArgumentParser()
    p.add_argument("prompt")
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--stream", action="store_true")
    return p

def test_argparse_cli():
    parser = make_run_parser()

    # Happy path
    args = parser.parse_args(["Hello world", "--model", "gpt-4o", "--stream"])
    assert args.prompt == "Hello world"
    assert args.model == "gpt-4o"
    assert args.stream is True
    assert args.temperature == 0.7

    # Default values
    args2 = parser.parse_args(["Hi"])
    assert args2.model == "gpt-4o-mini"
    assert args2.stream is False

    print("All argparse tests passed ✓")

test_argparse_cli()

# Typer test pattern (requires typer installed)
TYPER_TEST_CODE = '''
from typer.testing import CliRunner
from my_cli import app       # your typer app

runner = CliRunner()

def test_run_prompt():
    result = runner.invoke(app, ["run", "prompt", "Hello world"])
    assert result.exit_code == 0
    assert "Response" in result.output

def test_invalid_temperature():
    result = runner.invoke(app, ["run", "prompt", "Hi", "--temperature", "99"])
    assert result.exit_code != 0   # typer validates min/max

def test_missing_required_argument():
    result = runner.invoke(app, ["run", "prompt"])    # no prompt
    assert result.exit_code != 0
    assert "Missing argument" in result.output

def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "v" in result.output
'''
print("Typer test pattern (requires typer):")
print(TYPER_TEST_CODE)


# ─────────────────────────────────────────────
# C3. Rich integration for beautiful output
# ─────────────────────────────────────────────

RICH_INTEGRATION = '''
# pip install rich
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
from rich import print as rprint

console = Console()

# Pretty status output
def print_agent_status(sessions: list[dict]):
    table = Table(title="Active Agent Sessions", border_style="blue")
    table.add_column("ID",     style="cyan",  no_wrap=True)
    table.add_column("Model",  style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Tokens", justify="right")

    for s in sessions:
        status_colour = "green" if s["status"] == "running" else "red"
        table.add_row(
            s["id"],
            s["model"],
            f"[{status_colour}]{s[\'status\']}[/{status_colour}]",
            f"{s[\'tokens\']:,}",
        )
    console.print(table)

# Progress bar with Rich (vs typer.progressbar)
def process_with_progress(items):
    results = []
    for item in track(items, description="Processing..."):
        results.append(f"done:{item}")
    return results

# Panel for important messages
def show_error(message: str):
    console.print(Panel(message, title="Error", border_style="red", expand=False))

def show_success(message: str):
    console.print(Panel(message, title="Success", border_style="green", expand=False))

# Usage in a typer command:
# @app.command()
# def list_sessions():
#     sessions = get_sessions()    # from DB/API
#     print_agent_status(sessions)
'''
print("\n=== C3: Rich Integration ===")
print(RICH_INTEGRATION)


# ─────────────────────────────────────────────
# C4. Packaging CLIs with pyproject.toml
# ─────────────────────────────────────────────

PYPROJECT_TOML = '''
# pyproject.toml — declares your CLI as an installable package
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "llm-agent"
version = "2.0.0"
description = "LLM Agent CLI"
requires-python = ">=3.11"
dependencies = [
    "typer[all]>=0.12",
    "rich>=13",
    "openai>=1.0",
    "anthropic>=0.20",
]

# ─── THIS IS THE KEY PART ────────────────────────────────────────────────────
[project.scripts]
llm     = "llm_agent.cli:app"       # typer app object
llm-run = "llm_agent.cli:run_app"   # sub-app shortcut

# After `pip install -e .`:
#   llm run prompt "Hello"
#   llm eval suite evals.json
#   llm-run "Hello"      (shortcut)

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "mypy", "ruff"]
'''
print("\n=== C4: pyproject.toml packaging ===")
print(PYPROJECT_TOML)


# ════════════════════════════════════════════════════════════
# PART D — Interview Q&A
# ════════════════════════════════════════════════════════════

QA = """
╔══════════════════════════════════════════════════════════════════════╗
║           PART D — Interview Q&A  (argparse + typer)                ║
╚══════════════════════════════════════════════════════════════════════╝

Q1. What is the difference between a positional argument and an optional
    argument in argparse?
A1. Positional: no -- prefix, required by position.
    Optional: starts with -- (or -), can have default, identified by name.
    parser.add_argument("prompt")          # positional
    parser.add_argument("--model", ...)    # optional

Q2. How do you create subcommands with argparse?
A2. Use add_subparsers():
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run")
    Then dispatch: handlers[args.command](args)

Q3. What is action='store_true' used for?
A3. Creates a boolean flag: absent → False, present → True.
    parser.add_argument("--verbose", action="store_true")
    # python script.py --verbose  → args.verbose == True
    # python script.py            → args.verbose == False

Q4. How does typer differ from argparse?
A4. typer uses type annotations + defaults to infer CLI structure — no
    add_argument() calls. Also provides: validation (min/max), shell
    completion, rich integration, and a built-in CliRunner for testing.

Q5. What is the difference between typer.Argument and typer.Option?
A5. Argument: positional (required unless default given).
    Option: keyword (--flag), optional with a default value.
    prompt: str = typer.Argument(...)               # positional
    model: str  = typer.Option("gpt-4o-mini")       # keyword flag

Q6. How do you implement config priority: CLI > env > file > defaults?
A6. Load in reverse priority order, merge upward:
    cfg = load_file_config()
    cfg.update(load_env_config())      # env wins over file
    cfg.update(parse_cli_args())       # CLI wins over env
    Commonly done with dataclasses + argparse Namespace merging.

Q7. What is is_eager=True in typer callbacks?
A7. It makes the callback run before other argument validation. Used for
    --version and --help flags so they work even when required args
    are missing.

Q8. How do you test argparse CLIs without running the full script?
A8. Extract parser creation into a function; pass test args directly:
    def build_parser(): ...
    args = build_parser().parse_args(["run", "Hello", "--model", "gpt-4o"])
    assert args.model == "gpt-4o"
    For typer: use typer.testing.CliRunner.

Q9. How do you make --tool repeatable in typer? (e.g., --tool search --tool calc)
A9. Use list[str] type annotation with Optional:
    tools: Optional[list[str]] = typer.Option(None, "--tool")
    Passing --tool search --tool calc gives tools=["search", "calc"].

Q10. What is fromfile_prefix_chars in argparse?
A10. Allows reading arguments from a text file instead of the command line.
     parser = ArgumentParser(fromfile_prefix_chars="@")
     python agent.py @config.txt
     config.txt contains one flag/value per line:
       --model
       gpt-4o
       --temperature
       0.9
"""

print(QA)

print("\n" + "═" * 60)
print("Day 43 — argparse & typer: Complete ✅")
print("═" * 60)
print("""
Files created:
  Day43_ArgParse_Typer/
    01_argparse_typer.py    ← this file (full guide)
    agent_cli.py            ← argparse production CLI
    llm_agent_cli.py        ← typer production CLI

Topics covered:
  Part A — argparse: positional, optional, flags, subcommands,
            groups, nargs, custom types, full CLI app
  Part B — typer: Option/Argument, callbacks, subgroups,
            Enum choices, prompts, progress bar, full CLI
  Part C — Config layering, CLI testing, Rich integration,
            pyproject.toml packaging
  Part D — 10 Interview Q&A
""")
