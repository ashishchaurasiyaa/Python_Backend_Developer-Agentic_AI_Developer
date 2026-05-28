# CLI Frameworks — Click, Typer, Rich, Questionary

## Quick Concepts

**WHAT:**
- **argparse** = stdlib CLI parser (verbose)
- **Click** = Decorator-based CLI (Pallets project, mature)
- **Typer** = Type hint based CLI (built on Click, modern)
- **Rich** = Beautiful terminal output (colors, tables, progress)
- **Questionary** = Interactive prompts
- **tqdm** = Progress bars

**WHY good CLIs matter:**
- Developer productivity tool
- Database migrations
- Deployment scripts
- Admin utilities

**HOW frameworks compare:**

| Framework | Style | Complexity | Modern? |
|---|---|---|---|
| argparse | Imperative | Medium | Stdlib |
| Click | Decorators | Low | Mature |
| Typer | Type hints | Lowest | ⭐ Modern |
| Fire | Auto from class | Lowest | Google |

---

## Interview Questions & Answers

### Q1: Click — basic CLI?

**Answer:**

**HOW — Simple Click CLI:**

```python
# pip install click

import click

@click.command()
@click.option("--name", default="World", help="Who to greet")
@click.option("--count", default=1, type=int)
@click.option("--verbose", is_flag=True)
def hello(name, count, verbose):
    """Simple greeting CLI."""
    for _ in range(count):
        if verbose:
            click.echo(f"Hello, {name}! (verbose mode)")
        else:
            click.echo(f"Hello, {name}!")

if __name__ == "__main__":
    hello()


# Usage:
# python script.py --name Alice --count 3
# python script.py --help
```

**HOW — Subcommands (groups):**

```python
import click

@click.group()
def cli():
    """My app CLI."""
    pass

@cli.command()
@click.argument("name")
def create(name):
    """Create user."""
    click.echo(f"Creating {name}")

@cli.command()
@click.argument("name")
def delete(name):
    """Delete user."""
    if click.confirm(f"Delete {name}?"):
        click.echo("Deleted")

@cli.command()
def list():
    """List all users."""
    click.echo("Users: ...")


if __name__ == "__main__":
    cli()


# Usage:
# python script.py create alice
# python script.py delete alice
# python script.py list
```

---

### Q2: Typer — modern Click alternative?

**Answer:**

**WHAT:** Click but with type hints (auto-derives options).

**WHY:**
- Less boilerplate than Click
- Type-safe
- Auto help from docstrings
- Built on Click (compatible)

**HOW:**

```python
# pip install typer

import typer
from typing import Optional

app = typer.Typer()


@app.command()
def hello(
    name: str = "World",        # ⭐ Type from annotation
    count: int = 1,
    verbose: bool = False,
):
    """Simple greeting CLI."""
    for _ in range(count):
        message = f"Hello, {name}!"
        if verbose:
            message += " (verbose)"
        typer.echo(message)


@app.command()
def goodbye(name: str):
    """Say goodbye."""
    typer.echo(f"Goodbye, {name}!")


if __name__ == "__main__":
    app()


# Usage:
# python script.py hello --name Alice --count 3 --verbose
# python script.py goodbye Bob
# python script.py --help  (auto-generated)
```

**HOW — Advanced Typer:**

```python
import typer
from enum import Enum
from pathlib import Path
from typing import Optional

app = typer.Typer(help="My Awesome CLI")


class Color(str, Enum):
    red = "red"
    green = "green"
    blue = "blue"


@app.command()
def process(
    input_file: Path = typer.Argument(..., help="File to process"),
    output_file: Path = typer.Option("output.txt", "--output", "-o"),
    color: Color = typer.Option(Color.red, "--color", "-c"),
    debug: bool = typer.Option(False, "--debug", "-d"),
    api_key: str = typer.Option(..., envvar="API_KEY", help="From env var"),
):
    """Process input file."""
    if not input_file.exists():
        typer.secho(f"Error: {input_file} not found", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho(f"Processing in {color.value}", fg=color.value)
    # ...


if __name__ == "__main__":
    app()
```

**HOW — Multi-command app:**

```python
import typer

app = typer.Typer()
users_app = typer.Typer()
posts_app = typer.Typer()

app.add_typer(users_app, name="users")
app.add_typer(posts_app, name="posts")


@users_app.command("create")
def users_create(name: str):
    typer.echo(f"Creating user {name}")


@users_app.command("delete")
def users_delete(name: str):
    typer.echo(f"Deleting user {name}")


@posts_app.command("create")
def posts_create(title: str):
    typer.echo(f"Creating post: {title}")


# Usage:
# myapp users create alice
# myapp users delete alice
# myapp posts create "Hello"
```

---

### Q3: Rich — beautiful terminal output?

**Answer:**

**WHAT:** Rich text and formatting for terminal.

**HOW — Basic Rich:**

```python
# pip install rich

from rich.console import Console
from rich.table import Table
from rich.progress import track
from rich import print

console = Console()

# Colors and styles
console.print("Hello", style="bold red")
console.print("[green]Success[/green] [yellow]Warning[/yellow] [red]Error[/red]")

# Print rich objects
print({"key": "value", "list": [1, 2, 3]})  # Pretty dict
```

**HOW — Tables:**

```python
from rich.table import Table

table = Table(title="Users")
table.add_column("ID", style="cyan", no_wrap=True)
table.add_column("Name", style="magenta")
table.add_column("Email", style="green")

table.add_row("1", "Alice", "alice@example.com")
table.add_row("2", "Bob", "bob@example.com")
table.add_row("3", "Carol", "carol@example.com")

console.print(table)
```

**HOW — Progress bars:**

```python
from rich.progress import track, Progress, SpinnerColumn, TextColumn
import time

# Simple
for i in track(range(100), description="Processing..."):
    time.sleep(0.05)


# Advanced
with Progress() as progress:
    task1 = progress.add_task("[red]Downloading...", total=1000)
    task2 = progress.add_task("[green]Processing...", total=1000)

    while not progress.finished:
        progress.update(task1, advance=10)
        progress.update(task2, advance=5)
        time.sleep(0.1)
```

**HOW — Status spinner:**

```python
from rich.status import Status
import time

with console.status("[bold green]Loading data...", spinner="dots") as status:
    time.sleep(2)
    status.update("[bold blue]Processing...")
    time.sleep(2)
    status.update("[bold yellow]Saving...")
    time.sleep(1)
```

**HOW — Panels and Markdown:**

```python
from rich.panel import Panel
from rich.markdown import Markdown

console.print(Panel("Hello!", title="Greeting", border_style="blue"))

md = """
# Title
- Bullet 1
- Bullet 2

**Bold text** and *italic*.

```python
def hello():
    print("Hi")
```
"""
console.print(Markdown(md))
```

**HOW — Live updates:**

```python
from rich.live import Live
from rich.table import Table
import time

def generate_table(value):
    table = Table()
    table.add_column("Status")
    table.add_column("Value")
    table.add_row("Counter", str(value))
    return table


with Live(generate_table(0), refresh_per_second=4) as live:
    for i in range(20):
        time.sleep(0.5)
        live.update(generate_table(i))
```

---

### Q4: Typer + Rich — beautiful CLIs?

**Answer:**

**HOW — Integrated:**

```python
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import track
import time

app = typer.Typer(rich_markup_mode="rich")
console = Console()


@app.command()
def list_users():
    """List all [bold]users[/bold]."""
    table = Table(title="[bold cyan]Users[/bold cyan]")
    table.add_column("ID")
    table.add_column("Name", style="green")

    for i, name in enumerate(["Alice", "Bob", "Carol"]):
        table.add_row(str(i), name)

    console.print(table)


@app.command()
def process_files(
    count: int = typer.Argument(..., help="Number of files"),
):
    """Process [yellow]N[/yellow] files."""
    for _ in track(range(count), description="Processing..."):
        time.sleep(0.05)
    console.print("[bold green]✓ Done![/bold green]")


@app.command()
def error_example():
    """Show error."""
    console.print("[bold red]Error:[/bold red] Something failed!", style="red")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
```

---

### Q5: Questionary — interactive prompts?

**Answer:**

**WHAT:** Beautiful interactive prompts.

**HOW:**

```python
# pip install questionary

import questionary

# Text input
name = questionary.text("What is your name?").ask()

# Password
password = questionary.password("Enter password:").ask()

# Confirm
proceed = questionary.confirm("Continue?").ask()
if not proceed:
    exit()

# Single choice
color = questionary.select(
    "Pick a color:",
    choices=["Red", "Green", "Blue"]
).ask()

# Multi choice
tags = questionary.checkbox(
    "Select tags:",
    choices=["python", "web", "ai", "devops"]
).ask()

# Path
path = questionary.path("Select directory:").ask()

# Custom validation
age = questionary.text(
    "Your age:",
    validate=lambda x: x.isdigit() and int(x) > 0
).ask()


print(f"Name: {name}, Color: {color}, Tags: {tags}")
```

**HOW — Conditional flow:**

```python
import questionary

action = questionary.select(
    "What to do?",
    choices=["Create", "Update", "Delete"]
).ask()

if action == "Create":
    name = questionary.text("Name?").ask()
    email = questionary.text("Email?").ask()
    confirmed = questionary.confirm(f"Create {name}?").ask()

elif action == "Delete":
    items = get_items()
    selected = questionary.checkbox(
        "Select to delete:",
        choices=items
    ).ask()
```

---

### Q6: Async CLI commands?

**Answer:**

**HOW — Typer with async:**

```python
import typer
import asyncio
import httpx
from rich import print

app = typer.Typer()


async def fetch(url):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()


@app.command()
def get(url: str):
    """Fetch URL."""
    # ⭐ Run async in sync context
    result = asyncio.run(fetch(url))
    print(result)


@app.command()
def get_many(urls: list[str] = typer.Argument(...)):
    """Fetch multiple URLs."""
    async def main():
        async with httpx.AsyncClient() as client:
            responses = await asyncio.gather(*[
                client.get(url) for url in urls
            ])
            return [r.json() for r in responses]

    results = asyncio.run(main())
    print(results)


if __name__ == "__main__":
    app()
```

---

### Q7: tqdm — simple progress bars?

**Answer:**

**WHAT:** Simple progress bars.

**WHY tqdm vs Rich:**
- Simpler API
- Lightweight
- Notebook + terminal support
- Older but widely used

**HOW:**

```python
# pip install tqdm

from tqdm import tqdm
import time

# Wrap any iterable
for i in tqdm(range(100)):
    time.sleep(0.05)


# Manual control
pbar = tqdm(total=100)
for i in range(10):
    pbar.update(10)
    time.sleep(0.5)
pbar.close()


# Pandas integration
import pandas as pd
from tqdm import tqdm
tqdm.pandas()

df = pd.DataFrame({"x": range(10000)})
df["squared"] = df["x"].progress_apply(lambda x: x*x)  # ⭐ Progress bar!


# Async tqdm
from tqdm.asyncio import tqdm as atqdm

async def main():
    async for i in atqdm(async_iter):
        await process(i)
```

---

### Q8: Production CLI patterns?

**Answer:**

**HOW — Config file support:**

```python
import typer
from pathlib import Path
import yaml
import os

app = typer.Typer()


def load_config(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f)
    return {}


@app.command()
def deploy(
    config: Path = typer.Option(
        Path("~/.myapp/config.yaml").expanduser(),
        "--config", "-c",
        help="Config file"
    ),
    env: str = typer.Option("dev", envvar="DEPLOY_ENV"),  # ⭐ Env var
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """Deploy app."""
    settings = load_config(config)
    typer.echo(f"Deploying to {env}")

    if dry_run:
        typer.secho("(dry run, not actually deploying)", fg="yellow")
        return

    # Actual deploy
    ...
```

**HOW — Plugin architecture:**

```python
import typer
from importlib.metadata import entry_points

app = typer.Typer()

# Load plugins from setup.py / pyproject.toml entry points
for ep in entry_points(group="myapp.plugins"):
    plugin = ep.load()
    app.add_typer(plugin.app, name=ep.name)


# In plugin's pyproject.toml:
# [project.entry-points."myapp.plugins"]
# myplugin = "myplugin.cli"
```

**HOW — Shell completion:**

```bash
# Typer auto-generates shell completion
python script.py --install-completion zsh
python script.py --install-completion bash
python script.py --install-completion fish
```

**HOW — Distributable CLI:**

```toml
# pyproject.toml
[project.scripts]
myapp = "myapp.cli:app"
```

```bash
# After pip install
pip install myapp
myapp --help  # ⭐ Works as command
```

---

### Q9: CLI testing?

**Answer:**

**HOW — Test Typer CLI:**

```python
from typer.testing import CliRunner
from myapp.cli import app

runner = CliRunner()


def test_hello():
    result = runner.invoke(app, ["hello", "--name", "Alice"])
    assert result.exit_code == 0
    assert "Hello, Alice!" in result.stdout


def test_error_exit_code():
    result = runner.invoke(app, ["invalid-command"])
    assert result.exit_code != 0


def test_with_input():
    # Simulate interactive input
    result = runner.invoke(app, ["delete"], input="alice\ny\n")
    assert "Deleted alice" in result.stdout
```

**HOW — Test Click CLI:**

```python
from click.testing import CliRunner
from myapp.cli import cli

def test_command():
    runner = CliRunner()
    result = runner.invoke(cli, ["hello", "--name", "Alice"])
    assert result.exit_code == 0
```

---

### Q10: Error handling + UX?

**Answer:**

**HOW — Good error messages:**

```python
import typer
from rich.console import Console

console = Console(stderr=True)


@app.command()
def deploy(env: str):
    if env not in ["dev", "staging", "prod"]:
        console.print(
            f"[bold red]Error:[/bold red] Invalid env '{env}'\n"
            f"Valid options: dev, staging, prod",
            highlight=False
        )
        raise typer.Exit(code=1)


# Or with traceback hiding
@app.command()
def risky():
    try:
        do_thing()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if typer.confirm("Show traceback?"):
            console.print_exception()
        raise typer.Exit(code=1)
```

**HOW — Confirmation for destructive ops:**

```python
@app.command()
def delete_all(
    force: bool = typer.Option(False, "--force", "-f"),
):
    if not force:
        confirmed = typer.confirm(
            "⚠️  This will delete ALL users. Continue?",
            default=False
        )
        if not confirmed:
            typer.echo("Aborted")
            raise typer.Exit()

    # Actually delete
```

**HOW — Verbose / quiet modes:**

```python
import logging
import typer

@app.command()
def main(
    verbose: int = typer.Option(0, "-v", count=True, help="Verbosity"),
    quiet: bool = typer.Option(False, "-q"),
):
    if quiet:
        logging.basicConfig(level=logging.ERROR)
    elif verbose == 1:
        logging.basicConfig(level=logging.INFO)
    elif verbose >= 2:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    # -v = INFO, -vv = DEBUG
```

---

## CLI Frameworks Cheatsheet

| Need | Use |
|---|---|
| Modern CLI | Typer |
| Mature CLI | Click |
| Quick CLI | Typer (less code) |
| Stdlib only | argparse |
| Beautiful output | Rich |
| Interactive prompts | Questionary |
| Progress bars | tqdm or Rich |
| Auto-CLI from class | Fire (Google) |

---

## Production CLI Checklist

```markdown
### Design
- [ ] Clear command structure
- [ ] Helpful --help messages
- [ ] Sensible defaults
- [ ] Both positional + option args

### UX
- [ ] Colored output (Rich)
- [ ] Progress bars for long ops
- [ ] Confirmation for destructive
- [ ] -v / -q for verbosity

### Errors
- [ ] Non-zero exit codes
- [ ] Errors to stderr
- [ ] Helpful error messages
- [ ] Show usage on misuse

### Configuration
- [ ] Config file support
- [ ] Environment variables
- [ ] Per-command options
- [ ] Sensible defaults

### Distribution
- [ ] [project.scripts] in pyproject.toml
- [ ] Shell completion
- [ ] CHANGELOG documented
- [ ] Single binary (PyInstaller optional)

### Testing
- [ ] CliRunner tests
- [ ] Exit codes tested
- [ ] Error paths tested
- [ ] Interactive flows tested
```
