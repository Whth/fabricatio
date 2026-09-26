"""Base action of the staged novel pipeline: run one chain segment, then snapshot the whole tree.

Each stage runs one segment of the ``compose_novel`` chain through its mixed-in
capability, then persists a whole-tree snapshot of the novel context, so a wrong
result can be traced back to the stage that produced it. The stages follow the
chain's shape: stage names mirror the chain phase they wrap, and the lifecycle
hooks fire at their chain positions — the level's before-context hook brackets
the planning segments, the after-context and post-process hooks close each unit
out after its segments complete — so overriding a hook on a stage customizes the
staged run exactly like it customizes the programmatic chain.

The pipeline lives in three modules beside this one: :mod:`fabricatio_novel.actions.novel`
holds the plain stages, :mod:`fabricatio_novel.actions.rag` the retrieval stages and
:mod:`fabricatio_novel.actions.illustration` the dump stage that draws every scene.

The stages' names are declared once as :data:`StageName`: every stage class states its own name
from that vocabulary, the CLI offers exactly those names, and the snapshot directories a run is
resumed from are named after them.
"""

from abc import ABC
from pathlib import Path
from typing import Any, ClassVar, Literal

from fabricatio_core import logger
from fabricatio_core.models.action import Action

from fabricatio_novel.models.context.novel import NovelContext

__all__ = ["StageAction", "StageName"]

StageName = Literal[
    "01_init",
    "02_metadata",
    "03_bible",
    "04_characters",
    "05_chapter_plans",
    "06_story_plans",
    "07_scene_plans",
    "08_scenes",
    "09_novel",
]
"""The pipeline's stages, in run order: the name each stage snapshots under."""


class StageAction(Action, ABC):
    """Base action for staged novel phases: run the phase, then snapshot the whole tree."""

    dir_prefix: ClassVar[str] = "stage_"
    """Prefix of the snapshot directory a stage writes under the run's persist directory."""

    held_key: ClassVar[str] = "stages_done"
    """Init-context key listing the stages a resumed run already holds, in run order."""

    stage: ClassVar[StageName]
    """Stage name used to build the snapshot directory (e.g. ``02_metadata``)."""

    @classmethod
    def directory(cls, persist_dir: str | Path, stage: str) -> Path:
        """Return the snapshot directory of the stage called ``stage`` under a run's persist directory."""
        return Path(persist_dir) / f"{cls.dir_prefix}{stage}"

    def held(self, cxt: dict[str, Any]) -> bool:
        """Return whether a resumed run already holds this stage's work, leaving the stage out.

        A resumed run reloads the newest state it persisted and names every stage up to it, so the
        stages that put that state there do not run a second time; a stage left out keeps its
        snapshot as the run persisted it and its output key as the run's own context carries it.
        """
        return self.stage in cxt.get(self.held_key, ())

    async def snapshot(self, novel_ctx: NovelContext, cxt: dict[str, Any]) -> None:
        """Persist the whole novel context tree into the stage's snapshot directory."""
        persist_dir = cxt.get("persist_dir")
        if not persist_dir:
            return
        stage_dir = self.directory(persist_dir, self.stage)
        stage_dir.mkdir(parents=True, exist_ok=True)
        novel_ctx.persist(stage_dir)
        logger.debug(f"Persisted stage '{self.stage}' snapshot to {stage_dir}")
