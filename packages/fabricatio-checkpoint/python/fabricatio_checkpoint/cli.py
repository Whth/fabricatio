"""Fabricatio Checkpoint CLI tool for managing code checkpoints and workspaces."""

from fabricatio_core.utils import cfg

cfg(feats=["cli"])
from pathlib import Path
from typing import Annotated

from typer import Argument, Context, Option, Typer

from fabricatio_checkpoint.inited_manager import SHADOW_REPO_MANAGER

app = Typer()


@app.callback()
def main(
    ctx: Context,
    workspace: Annotated[
        Path, Option("--workspace", "-w", help="Path to the workspace", exists=True, file_okay=False, resolve_path=True)
    ] = Path.cwd(),
) -> None:
    """Set the workspace for all commands."""
    ctx.obj = {
        "workspace": workspace,
    }


@app.command()
def reset(ctx: Context, commit_id: str = Argument("HEAD")) -> None:
    """Reset the workspace to a specific commit."""
    workspace: Path = ctx.obj["workspace"]
    SHADOW_REPO_MANAGER.reset(workspace, commit_id)


@app.command()
def ls(ctx: Context) -> None:
    """List all commits."""
    ctx.obj["workspace"]


@app.command()
def workspaces(cached_only: bool = Option(False, "-co", "--cached-only", help="Only list cached workspaces")) -> None:
    """List all workspaces."""
