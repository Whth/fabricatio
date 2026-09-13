"""Benchmark commands: score one run, diff it against a baseline, and print the run board.

``--json`` prints the measurements only: the ``*_display`` fields exist for the
report templates, so they are left out of the machine-readable form.
"""

from pathlib import Path

import typer

from fabricatio_novel.benchmark import (
    RunScorecard,
    TermProbes,
    compare,
    find_baseline,
    render_board,
    render_comparison,
    render_scorecard,
    score_run,
)
from fabricatio_novel.cli import bench_app


def _probes(path: Path | None) -> TermProbes | None:
    """Load the probe file a command was given; without one only corpus-independent metrics run."""
    if path is None:
        return None
    try:
        return TermProbes.load(path)
    except (OSError, ValueError) as exc:
        typer.secho(f"Cannot read probes {path}: {exc}", fg=typer.colors.RED, bold=True, err=True)
        raise typer.Exit(1) from exc


def _score(run_dir: Path, probes: TermProbes | None) -> RunScorecard:
    """Score a run directory, exiting with a readable message when it cannot be scored."""
    try:
        return score_run(run_dir, probes=probes)
    except (OSError, ValueError) as exc:
        typer.secho(f"Cannot score {run_dir}: {exc}", fg=typer.colors.RED, bold=True, err=True)
        raise typer.Exit(1) from exc


@bench_app.command(name="score")
def score_command(
    run_dir: Path = typer.Argument(..., help="Run directory, e.g. novels/20260101-101010."),
    probes_path: Path | None = typer.Option(
        None,
        "--probes",
        help="JSON file of gated/watch/alias term lists the run is measured against.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Print the scorecard as JSON."),
) -> None:
    """Measure one run and print its scorecard; reads artifacts only and calls no LLM."""
    card = _score(run_dir, _probes(probes_path))
    typer.echo(card.model_dump_json(indent=2, exclude_computed_fields=True) if as_json else render_scorecard(card))


@bench_app.command(name="compare")
def compare_command(
    run_dir: Path = typer.Argument(..., help="Candidate run directory."),
    against: Path | None = typer.Option(
        None, "--against", help="Baseline run directory; defaults to the newest comparable run beside the candidate."
    ),
    probes_path: Path | None = typer.Option(
        None,
        "--probes",
        help="JSON file of gated/watch/alias term lists both runs are measured against.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Print the comparison as JSON."),
) -> None:
    """Diff a run against a baseline run and name the regressions."""
    probes = _probes(probes_path)
    candidate = _score(run_dir, probes)
    baseline = _score(against, probes) if against is not None else find_baseline(candidate, probes=probes)
    if baseline is None:
        typer.secho(
            f"No earlier run next to {run_dir} to compare against.", fg=typer.colors.YELLOW, bold=True, err=True
        )
        raise typer.Exit(1)
    result = compare(baseline, candidate)
    typer.echo(result.model_dump_json(indent=2, exclude_computed_fields=True) if as_json else render_comparison(result))


@bench_app.command(name="board")
def board_command(
    persist_dir: Path = typer.Argument(Path("novels"), help="Directory holding the run subdirectories."),
    limit: int = typer.Option(10, "--limit", "-n", help="How many of the newest runs to score."),
    probes_path: Path | None = typer.Option(
        None,
        "--probes",
        help="JSON file of gated/watch/alias term lists every run is measured against.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Print the scorecards as JSON."),
) -> None:
    """Score the newest runs under a persist directory and print them newest first."""
    probes = _probes(probes_path)
    runs = sorted((path for path in persist_dir.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True)[
        :limit
    ]
    cards: list[RunScorecard] = []
    for run in runs:
        try:
            cards.append(score_run(run, probes=probes))
        except (OSError, ValueError) as exc:
            typer.secho(f"skipped {run.name}: {exc}", fg=typer.colors.YELLOW, err=True)
    if not cards:
        typer.secho(f"No scorable runs under {persist_dir}.", fg=typer.colors.RED, bold=True, err=True)
        raise typer.Exit(1)
    if as_json:
        typer.echo(
            "[" + ",\n".join(card.model_dump_json(indent=2, exclude_computed_fields=True) for card in cards) + "]"
        )
    else:
        typer.echo(render_board(cards[::-1]))
