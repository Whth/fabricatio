"""Pipeline channel model for a scene: its plan and the composed prose it writes."""

from typing import Self, final

from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.log import ContextEntry
from fabricatio_novel.models.plan import ScenePlan


class SceneContext(ContextBase[ScenePlan]):
    """A scene's composition channel: its plan and the composed prose it owns."""

    content: str = ""
    """The composed prose of this scene; the only context level that owns composed content."""

    def set_content(self, content: str) -> Self:
        """Set the scene's composed prose and return self."""
        self.content = content
        return self

    @final
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """Contribute the composed content; scene titles and descriptions are not injected."""
        if not self.content:
            return ()
        return (ContextEntry(kind="scene_content", title=self.title, body=self.content),)
