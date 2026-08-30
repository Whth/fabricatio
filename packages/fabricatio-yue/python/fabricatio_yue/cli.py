"""Command-line interface for Fabricatio Yue song composition."""

from fabricatio_core.utils import cfg

cfg(feats=["cli"])
from pathlib import Path

from typer import Option, Typer

app = Typer(
    name="yuek",
    help="Compose lyrics with Fabricatio!",
    epilog="For more information, visit: https://github.com/Whth/fabricatio",
    short_help="Fabricatio Yue CLI for song composition",
)


@app.command()
def compose(
    requirement: str = Option(..., "-r", "--requirement", help="Song requirement/prompt"),
    output: Path = Option(Path("song"), "-o", "--output", help="Output file folder"),
) -> None:
    """Compose a song based on your requirements."""
    from fabricatio_core import Event, Role, Task, WorkFlow
    from fabricatio_core.utils import ok

    from fabricatio_yue.actions.compose import Compose

    ns = "compose"
    Role.with_bio(name="composer").subscribe(
        Event.quick_instantiate(ns),
        WorkFlow(steps=(Compose().to_task_output(),)),
    ).dispatch()

    ok(
        Task(name="compose song")
        .update_init_context(
            req=requirement,
            output=output,
        )
        .delegate_blocking(ns),
        "Failed to compose song!",
    )


def main() -> None:
    """Entry point for the CLI application."""
    app()
