"""Fabricatio Checkpoint CLI tool for managing code checkpoints and workspaces."""

from fabricatio_core.utils import cfg

cfg(feats=["cli"])
from pathlib import Path
from typing import Annotated

from typer import Argument, Context, Option, Typer, echo

from fabricatio_checkpoint.inited_service import get_checkpoint_service

app = Typer(no_args_is_help=True)


@app.callback()
def main(
    ctx: Context,
    workspace: Annotated[
        Path,
        Option("--workspace", "-w", help="Path to the workspace.", exists=True, file_okay=False, resolve_path=True),
    ] = Path.cwd(),
) -> None:
    """Fabricatio Checkpoint CLI tool for managing code checkpoints and workspaces."""
    ctx.obj = {
        "workspace": workspace,
    }


@app.command()
def reset(ctx: Context, commit_id: str = Argument("HEAD", help="The commit id to reset to.")) -> None:
    """Reset the workspace to a specific commit."""
    echo(get_checkpoint_service().get_store(ctx.obj["workspace"]).reset(commit_id))


@app.command()
def save(ctx: Context, message: Annotated[str, Argument(help="The message of the commit.")] = "Change") -> None:
    """Save the workspace."""
    echo(get_checkpoint_service().get_store(ctx.obj["workspace"]).save(commit_msg=message))


@app.command()
def diff(ctx: Context) -> None:
    """Show the difference between the workspace and the last commit."""
    diff_result = get_checkpoint_service().get_store(ctx.obj["workspace"]).get_changed_files()
    echo("\n".join(diff_result))


@app.command()
def ls(ctx: Context) -> None:
    """List all commits of the workspace specified in the workspace argument."""
    cm_id_seq = get_checkpoint_service().get_store(ctx.obj["workspace"]).commits()
    echo("\n".join(cm_id_seq))


@app.command()
def workspaces() -> None:
    """List all workspaces."""
    ws_list = get_checkpoint_service().workspaces()

    echo("\n".join((w.as_posix() for w in ws_list)))
