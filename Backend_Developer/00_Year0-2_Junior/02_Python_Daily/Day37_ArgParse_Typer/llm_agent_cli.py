#!/usr/bin/env python3
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
        typer.echo(f"## Response\n\n{response_text}\n")
    else:
        typer.echo(response_text)

    if save:
        save.write_text(response_text)
        typer.secho(f"Saved → {save}", fg=typer.colors.GREEN)

    typer.secho(f"\n⏱  {elapsed:.2f}s", dim=True)


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
                    typer.secho("\nFAIL — stopping (--fail-fast)", fg=typer.colors.RED)
                    break

    total = passed + failed
    colour = typer.colors.GREEN if failed == 0 else typer.colors.YELLOW
    typer.secho(f"\nResults: {passed}/{total} passed ({passed/total:.1%})", fg=colour)
    raise typer.Exit(code=0 if failed == 0 else 1)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()

# Usage:
#   python llm_agent_cli.py run prompt "Hello world" --model gpt-4o --stream
#   python llm_agent_cli.py run batch prompts.txt --output-dir out/
#   python llm_agent_cli.py eval suite evals.json --concurrency 5 --fail-fast
#   python llm_agent_cli.py --version
