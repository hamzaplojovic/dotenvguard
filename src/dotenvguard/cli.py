"""Command-line interface for dotenvguard."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from dotenvguard import __version__
from dotenvguard.core import (
    Status,
    ValidationResult,
    find_env_files,
    validate,
)

app = typer.Typer(
    name="dotenvguard",
    help="Validate .env files against .env.example.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()
err_console = Console(stderr=True)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"dotenvguard [bold]{__version__}[/bold]")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Validate .env files against .env.example."""


def _render_table(result: ValidationResult) -> None:
    """Render validation results as a rich table."""
    table = Table(title="dotenvguard", show_header=True, header_style="bold")
    table.add_column("Variable", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Default", style="dim")

    status_styles = {
        Status.OK: "[green]ok[/green]",
        Status.MISSING: "[red bold]MISSING[/red bold]",
        Status.EMPTY: "[yellow]empty[/yellow]",
        Status.EXTRA: "[dim]extra[/dim]",
    }

    for var in result.vars:
        default_display = var.default_value or "" if var.has_default else ""
        table.add_row(
            var.name,
            status_styles[var.status],
            default_display,
        )

    console.print()
    console.print(table)

    n_missing = len(result.missing)
    n_empty = len(result.empty)
    n_total = len(result.vars)

    if n_missing:
        count = "s" if n_missing != 1 else ""
        console.print(
            f"\n[red bold]{n_missing} missing[/red bold]"
            f" variable{count} out of {n_total} required",
        )
    elif n_empty:
        count = "s" if n_empty != 1 else ""
        console.print(
            f"\n[yellow]{n_empty} empty[/yellow]"
            f" variable{count} (set but blank)"
            f" out of {n_total}",
        )
    else:
        console.print(f"\n[green]All {n_total} variables present.[/green]")


@app.command()
def check(
    directory: Annotated[
        Path,
        typer.Argument(
            help="Directory containing .env and .env.example.",
            exists=True,
            file_okay=False,
            resolve_path=True,
        ),
    ] = ".",  # type: ignore[assignment]
    env_file: Annotated[
        Optional[Path],
        typer.Option(
            "--env",
            "-e",
            help="Path to .env file.",
        ),
    ] = None,
    example_file: Annotated[
        Optional[Path],
        typer.Option(
            "--example",
            "-x",
            help="Path to .env.example file.",
        ),
    ] = None,
    show_extra: Annotated[
        bool,
        typer.Option(
            "--extra",
            help="Show extra variables not in .env.example.",
        ),
    ] = False,
    no_empty_warning: Annotated[
        bool,
        typer.Option(
            "--no-empty-warning",
            help="Don't warn about empty values.",
        ),
    ] = False,
    output_json: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output results as JSON.",
        ),
    ] = False,
) -> None:
    """Validate .env against .env.example in a directory."""
    if env_file is None or example_file is None:
        found_env, found_example = find_env_files(directory)
        if env_file is None:
            env_file = found_env
        if example_file is None:
            example_file = found_example

    if example_file is None:
        err_console.print(
            "[red]No .env.example file found.[/red] "
            "Provide one with --example or create "
            ".env.example in the directory."
        )
        raise typer.Exit(code=1)

    if env_file is None:
        err_console.print(
            "[red]No .env file found.[/red] "
            "Provide one with --env or create "
            ".env in the directory."
        )
        raise typer.Exit(code=1)

    result = validate(
        env_path=env_file,
        example_path=example_file,
        warn_empty=not no_empty_warning,
        show_extra=show_extra,
    )

    if output_json:
        console.print_json(result.to_json())
    else:
        _render_table(result)

    if not result.ok:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
