"""Resuming a persisted run: pick the restart stage from the stage snapshots a run holds.

A resumed run drives the workflow it always drove -- the stages the run already holds are the
ones that leave themselves out -- so the restart point only states which stage runs first, which
persisted tree it continues from, and which stages are already done.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Self

from fabricatio_core.models.action import WorkFlow

from fabricatio_novel.actions.stage import StageAction
from fabricatio_novel.models.context.novel import NovelContext, RagNovelContext

__all__ = ["ResumeError", "ResumePoint"]


class ResumeError(ValueError):
    """Raised when a run cannot be resumed at the requested stage."""


@dataclass(frozen=True, slots=True)
class ResumePoint:
    """Where a resumed run restarts: the stage it starts at, the tree it continues from, and the stages it leaves out.

    A run resumes from a snapshot, never from scratch: the named stage must be one the workflow
    runs and the run must hold a snapshot of an earlier stage, so a mistyped stage or a missing
    state fails before the run spends a single call instead of silently writing the novel again.
    """

    stage: str
    """The stage the run starts at; it runs, the stages before it are left out."""
    context: NovelContext
    """The tree of the newest snapshot taken before that stage."""
    done: tuple[str, ...]
    """The stages the run already holds, in run order."""

    @classmethod
    def of(cls, workflow: WorkFlow, run_dir: Path, stage: str | None = None) -> Self:
        """Resolve where ``run_dir`` restarts: the state it continues from and the stages to leave out.

        ``stage`` names the stage to restart at, with or without the ``stage_`` directory prefix,
        and defaults to the stage after the newest one the run holds -- the newest stage itself
        when the run reached the last one.

        Raises:
            ResumeError: The workflow runs no such stage, the run holds no snapshot before it, a
                snapshot does not read as a novel context, or the run holds no snapshot at all.
        """
        names = cls._stages(workflow)
        if stage is None:
            restart, context = cls._continued(names, run_dir)
        else:
            restart = cls._known(names, stage)
            context = cls._before(names, restart, run_dir)
        return cls(stage=restart, context=context, done=tuple(names[: names.index(restart)]))

    @staticmethod
    def _stages(workflow: WorkFlow) -> list[str]:
        """The stages ``workflow`` persists, in run order."""
        return [action.stage for action in workflow.iter_actions() if isinstance(action, StageAction)]

    @staticmethod
    def _known(names: list[str], stage: str) -> str:
        """The stage name ``stage`` spells, with or without the snapshot directory prefix."""
        name = stage.removeprefix(StageAction.dir_prefix).strip()
        if name not in names:
            raise ResumeError(f"the run has no stage '{stage}'; its stages are: {', '.join(names)}")
        return name

    @classmethod
    def _continued(cls, names: list[str], run_dir: Path) -> tuple[str, NovelContext]:
        """The stage a run continues at -- the one after its newest snapshot -- with the tree that snapshot carries."""
        for index, name in reversed(list(enumerate(names))):
            context = cls._read(StageAction.directory(run_dir, name))
            if context is not None:
                return (names[index + 1] if index + 1 < len(names) else name), context
        raise ResumeError(f"'{run_dir}' holds no stage snapshot to resume from")

    @classmethod
    def _before(cls, names: list[str], restart: str, run_dir: Path) -> NovelContext:
        """The newest tree the run persisted before ``restart``."""
        before = names[: names.index(restart)]
        for name in reversed(before):
            context = cls._read(StageAction.directory(run_dir, name))
            if context is not None:
                return context
        held = ", ".join(name for name in names if cls._read(StageAction.directory(run_dir, name)) is not None)
        raise ResumeError(
            f"'{run_dir}' holds no snapshot before stage '{restart}'; it holds: {held or 'no stage snapshot'}"
        )

    @staticmethod
    def _read(stage_dir: Path) -> NovelContext | None:
        """Read the newest snapshot a stage directory holds, or ``None`` when it holds none.

        A sealed run's snapshot loads as :class:`RagNovelContext` and a plain one as
        :class:`NovelContext`, so the returned class states which command continues the run.

        Raises:
            ResumeError: The directory holds a snapshot that does not read as a novel context.
        """
        try:
            context = RagNovelContext.from_latest_persistent(stage_dir)
            return context if context is not None else NovelContext.from_latest_persistent(stage_dir)
        except (ValueError, OSError) as exc:
            raise ResumeError(f"the snapshot in '{stage_dir}' does not read as a novel context: {exc}") from exc
