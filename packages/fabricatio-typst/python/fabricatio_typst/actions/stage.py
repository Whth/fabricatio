"""Base action of the staged article pipeline: run one chain segment, then snapshot the whole tree.

Each stage runs one segment of the ``compose_article`` chain through its mixed-in
capability, then persists a whole-tree snapshot of the article context, so a wrong
result can be traced back to the stage that produced it. The stages follow the chain's
shape: stage names mirror the chain phase they wrap, and the lifecycle hooks fire at
their chain positions — the level's before-context hook brackets the planning segments,
the after-context and post-process hooks close each unit out after its segments
complete — so overriding a hook on a stage customizes the staged run exactly like it
customizes the programmatic chain.

The pipeline lives in two modules beside this one: :mod:`fabricatio_typst.actions.article`
holds the plain stages and :mod:`fabricatio_typst.actions.rag` the retrieval stage that
writes every subsection against the reference corpus.

The stages' names are declared once as :data:`StageName`: every stage class states its own
name from that vocabulary, and the snapshot directories name themselves after them.
"""

from abc import ABC
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import ClassVar, Literal, Unpack

from fabricatio_core import logger
from fabricatio_core.models.action import Action
from fabricatio_core.models.kwargs_types import LLMKwargs

from fabricatio_typst.models.context.article import ArticleContext

__all__ = ["StageAction", "StageName"]

StageName = Literal[
    "01_init",
    "02_proposal",
    "03_article",
    "04_chapter_plans",
    "05_section_plans",
    "06_subsection_plans",
    "07_content",
    "08_article",
]
"""The snapshotting stages of the pipeline, in run order: the name each stage writes its snapshot under."""


class StageAction(Action, ABC):
    """Base action for staged article phases: run one composition phase, then snapshot the tree.

    A stage declares the phase it wraps, the agent variant its calls ride unless the run
    names a group (``send_to_slot``), and where it snapshots from (``stage``). Everything
    else — the tree walks, the hooks, the assembly — belongs to the composition capability
    the stage mixes in.
    """

    dir_prefix: ClassVar[str] = "stage_"
    """Prefix of the snapshot directory a stage writes under the run's persist directory."""

    stage: ClassVar[StageName]
    """Stage name used to build the snapshot directory (e.g. ``02_proposal``)."""

    send_to_slot: ClassVar[str | None]
    """The agent variant this stage's LLM calls ride when the run names no group.

    Planning stages ride ``PLAN`` so the structured plans follow the plan model; the
    writing and assembling stages ride ``TASK``. Every stage states its own slot.
    """

    @classmethod
    def directory(cls, persist_dir: str | Path, stage: str) -> Path:
        """Return the snapshot directory of the stage called ``stage`` under a run's persist directory."""
        return Path(persist_dir) / f"{cls.dir_prefix}{stage}"

    def routed(self, send_to: str | None) -> str | None:
        """Resolve the group this stage's calls ride: the run's own group, or this stage's slot."""
        return send_to or self.send_to_slot

    async def run_phase[R](
        self,
        ctx: ArticleContext,
        phase: Callable[..., Awaitable[R]],
        *,
        send_to: str | None,
        persist_dir: str | Path | None,
        **kwargs: Unpack[LLMKwargs],
    ) -> R:
        """Run one composition phase over ``ctx``, then snapshot the whole tree either way.

        The phase rides :meth:`routed`, and the extra task-context keys travel on to the
        phase's LLM calls.
        """
        completed = await phase(ctx, send_to=self.routed(send_to), **kwargs)
        await self.snapshot(ctx, persist_dir)
        return completed

    async def snapshot(self, ctx: ArticleContext, persist_dir: str | Path | None) -> None:
        """Persist the whole article context tree into the stage's snapshot directory.

        A run whose task carries no persist directory keeps nothing on disk: the stage
        still runs and its output still travels through the task context, so the
        pipeline stays usable as a plain in-memory chain.
        """
        if not persist_dir:
            return
        stage_dir = self.directory(persist_dir, self.stage)
        stage_dir.mkdir(parents=True, exist_ok=True)
        ctx.persist(stage_dir)
        logger.debug(f"Persisted stage '{self.stage}' snapshot to {stage_dir}")
