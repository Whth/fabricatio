"""Output model for a composed scene: the scene plan plus its composed prose."""

from pathlib import Path
from typing import Self

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core import logger
from fabricatio_core.rust import word_count

from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.plan import ScenePlan
from fabricatio_novel.rust import NovelBuilder, text_to_xhtml_paragraphs


class Scene(ScenePlan, WordCount):
    """A composed scene: its plan fields and the written content."""

    content: str

    @property
    def exact_word_count(self) -> int:
        """Count the words in this scene's composed prose."""
        return word_count(self.content)

    def to_xhtml(self, chapter_index: int, scene_index: int) -> str:
        """Render this scene's contribution to the chapter body as XHTML paragraphs."""
        return text_to_xhtml_paragraphs(self.content)

    def epub_resources(self, chapter_index: int, scene_index: int) -> list[tuple[str, Path]]:
        """Return nothing: a plain scene registers no EPUB resources; subclasses override to opt in."""
        return []

    def write_epub(self, builder: NovelBuilder, chapter_index: int, scene_index: int) -> None:
        """Register this scene's EPUB resources in the container under construction."""
        for name, source in self.epub_resources(chapter_index, scene_index):
            if source.is_file():
                builder.add_resource(name, source)
            else:
                logger.warn(f"Resource file missing for scene {scene_index} of chapter {chapter_index}: {source}")

    @classmethod
    def from_context(cls, ctx: SceneContext) -> Self:
        """Materialize a scene from its scene context."""
        return cls(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=ctx.expected_word_count,
            content=ctx.content,
        )
