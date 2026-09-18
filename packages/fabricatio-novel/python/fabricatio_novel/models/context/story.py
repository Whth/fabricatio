"""Pipeline channel model for a story: its plan and the scene contexts it writes."""

from collections.abc import Generator
from typing import final

from fabricatio_novel.models.context.base import ParentContextBase
from fabricatio_novel.models.context.log import ContextEntry
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.plan import StoryPlan


class StoryContext(ParentContextBase[SceneContext, StoryPlan]):
    """A story's composition channel: its plan and the scene contexts it writes."""

    @final
    def iter_scene_content(self) -> Generator[str, None, None]:
        """Yield each scene's composed content, in story order."""
        for scene_ctx in self.child_contexts:
            if scene_ctx.content:
                yield scene_ctx.content

    @final
    def is_fully_written(self) -> bool:
        """Whether every scene of this story carries composed content; a story without scenes counts as written."""
        return all(scene_ctx.content for scene_ctx in self.child_contexts)

    @final
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """Forward the scenes' entries; the story's own title and description are not injected."""
        entries: list[ContextEntry] = []
        for child in self.iter_child_contexts():
            entries.extend(child.prefixed_entries())
        return tuple(entries)
