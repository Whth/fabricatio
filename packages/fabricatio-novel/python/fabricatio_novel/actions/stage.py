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
"""

from abc import ABC
from pathlib import Path
from typing import Any, ClassVar

from fabricatio_core import logger
from fabricatio_core.models.action import Action

from fabricatio_novel.models.context.novel import NovelContext

__all__ = ["StageAction"]


class StageAction(Action, ABC):
    """Base action for staged novel phases: run the phase, then snapshot the whole tree."""

    stage: ClassVar[str] = ""
    """Stage name used to build the snapshot directory (e.g. ``02_metadata``)."""

    async def snapshot(self, novel_ctx: NovelContext, cxt: dict[str, Any]) -> None:
        """Persist the whole novel context tree into the stage's snapshot directory."""
        persist_dir = cxt.get("persist_dir")
        if not persist_dir:
            return
        stage_dir = Path(persist_dir) / f"stage_{self.stage}"
        stage_dir.mkdir(parents=True, exist_ok=True)
        novel_ctx.persist(stage_dir)
        logger.debug(f"Persisted stage '{self.stage}' snapshot to {stage_dir}")
