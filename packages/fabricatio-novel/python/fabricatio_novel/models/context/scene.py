"""Pipeline channel model for a scene: its plan and the composed prose it writes."""

from typing import Self, final

from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.log import ContextEntry, EntryKind
from fabricatio_novel.models.plan import ScenePlan


class SceneContext(ContextBase[ScenePlan]):
    """A scene's composition channel: its plan and the composed prose it owns."""

    content: str = ""
    """The composed prose of this scene; the only context level that owns composed content."""

    def set_content(self, content: str) -> Self:
        """Set the scene's composed prose and return self."""
        self.content = content
        return self

    def is_chapter_opening(self) -> bool:
        """Whether this scene starts its chapter, no prose of that chapter existing above it.

        Everything above the scene is the earlier chapters and then this chapter's
        own heading, with whatever was seeded alongside (the setting bible, retrieved
        references) carrying no prose of its own. So the chapter has already started
        exactly when the newest composed block above the scene is prose; when the
        newest one is the chapter's heading, the prompt has to say that this scene
        opens the chapter — its instruction to continue the text above would
        otherwise point at a heading and the chapters before it.
        """
        written = [
            entry.kind
            for entry in self.prefix_log.entries
            if entry.kind.is_chapter_header() or entry.kind.is_scene_content()
        ]
        return not written or written[-1].is_chapter_header()

    @final
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """Contribute the composed content; scene titles and descriptions are not injected."""
        if not self.content:
            return ()
        return (ContextEntry(kind=EntryKind.SCENE_CONTENT, title=self.title, body=self.content),)
