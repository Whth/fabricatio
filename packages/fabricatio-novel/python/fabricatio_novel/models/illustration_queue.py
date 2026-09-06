"""The pending-illustration work list compiled from a finished novel context.

:attr:`IllustrateScenes.illustrate_novel_phase
<fabricatio_novel.capabilities.illustration.IllustrateScenes.illustrate_novel_phase>`
delegates the chapter -> story -> scene walk to :class:`SceneIllustrationQueue`:
every scene still awaiting its illustration becomes one frozen
:class:`PendingIllustration` entry carrying its ``(chapter, scene)`` key, title,
rendered proposal requirement, and the render target inside the run's
``images/`` directory.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Self

from fabricatio_core import TEMPLATE_MANAGER

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.utils import scene_image_name

__all__ = ["PendingIllustration", "SceneIllustrationQueue"]


@dataclass(frozen=True)
class PendingIllustration:
    """One scene awaiting illustration: its key, title, requirement, and render target."""

    key: tuple[int, int]
    """``(chapter_index, scene_index)`` of the scene; indices match the EPUB exporter naming."""

    scene_title: str
    """Title of the scene, used in per-scene skip warnings."""

    requirement: str
    """Rendered proposal requirement fed to the image-prompt proposal."""

    target: Path
    """Path of the PNG the render must write, inside the run's ``images/`` directory."""


@dataclass(frozen=True)
class SceneIllustrationQueue:
    """The ordered work list for one illustration pass over a finished context."""

    entries: tuple[PendingIllustration, ...]
    """Pending scenes in walk order (chapter -> story -> scene)."""

    images_dir: Path
    """The run's ``images/`` output directory, created at construction."""

    @classmethod
    def from_context(
        cls,
        novel_ctx: NovelContext,
        *,
        persist_dir: str | Path,
        constraint: str,
    ) -> Self:
        """Walk the context tree and queue every scene still awaiting its illustration.

        Creates the run's ``images/`` directory, applies the
        ``[ext.novel] illustration_skip_existing`` filter against each scene's
        canonical PNG name, and renders each proposal requirement — the scene's
        running prefix included, so the proposal sees everything composed before
        it — from ``[ext.novel] scene_illustration_prompt_template``.

        Args:
            novel_ctx: The composed novel context whose scenes get queued.
            persist_dir: Run directory receiving the ``images/`` output subdirectory.
            constraint: Global style/content constraint merged into every requirement.

        Returns:
            The compiled queue; empty ``entries`` when every scene is already illustrated.
        """
        images_dir = Path(persist_dir) / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        entries: list[PendingIllustration] = []
        for ci, chapter in enumerate(novel_ctx.iter_prefixed_contexts(), 1):
            for scene_idx, story, scene in chapter.iter_scenes():
                target = images_dir.joinpath(scene_image_name(ci, scene_idx))
                if novel_config.illustration_skip_existing and target.is_file():
                    continue
                requirement = TEMPLATE_MANAGER.render_template(
                    novel_config.scene_illustration_prompt_template,
                    {
                        "novel_title": novel_ctx.title,
                        "chapter_title": chapter.title,
                        "story_title": story.title,
                        "scene_title": scene.title,
                        "scene_description": scene.description,
                        "novel_so_far": scene.prefix_log.render(),
                        "scene_content": scene.content,
                        "cast": scene.scene_plan.cast if scene.scene_plan else [],
                        "illustration_constraint": constraint,
                    },
                )
                entries.append(PendingIllustration((ci, scene_idx), scene.title, requirement, target))
        return cls(entries=tuple(entries), images_dir=images_dir)
