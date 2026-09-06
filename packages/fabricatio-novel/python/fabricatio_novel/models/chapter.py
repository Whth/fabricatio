"""Output model for a composed chapter: the chapter plan plus its materialized stories."""

from typing import Self

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core import TEMPLATE_MANAGER

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scene import Scene
from fabricatio_novel.models.story import Story
from fabricatio_novel.rust import NovelBuilder


class Chapter(ChapterPlan, WordCount):
    """A composed chapter: its plan fields and the stories it contains."""

    story: list[Story]

    def scenes(self) -> list[Scene]:
        """Every scene of this chapter in narrative order, flattened across stories."""
        return [scene for story in self.story for scene in story.scenes]

    @property
    def exact_word_count(self) -> int:
        """Sum the exact word counts of every story in this chapter."""
        return sum(c.exact_word_count for c in self.story)

    @classmethod
    def from_context(cls, ctx: ChapterContext) -> Self:
        """Materialize a chapter from its chapter context, materializing each story recursively."""
        return cls(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=ctx.expected_word_count,
            writing_style=ctx.chapter_plan.writing_style if ctx.chapter_plan is not None else "",
            writing_constraint=ctx.writing_constraint,
            story=[Story.from_context(sc) for sc in ctx.story_context],
        )

    def to_text(self) -> str:
        """Render the chapter body as plain text: scene contents separated by blank lines."""
        return "\n\n".join(scene.content for scene in self.scenes())

    def to_xhtml(self, chapter_index: int = 0) -> str:
        """Render the chapter body as a full XHTML document.

        The chapter title is deliberately omitted: ``dump_epub`` already
        registers it once on the EPUB side via ``add_chapter(title, ...)``,
        so embedding it here would duplicate it in every chapter document.
        Scenes render their own body fragments via :meth:`Scene.to_xhtml`,
        so illustrated scenes append their figure inline; image resources
        are registered by :meth:`write_epub`.
        """
        sections = [
            scene.to_xhtml(chapter_index, scene_index) for scene_index, scene in enumerate(self.scenes(), start=1)
        ]
        return TEMPLATE_MANAGER.render_template(
            novel_config.render_chapter_xhtml_template,
            {"content": "\n".join(sections), "title": self.title},
        )

    def write_epub(self, builder: NovelBuilder, chapter_index: int) -> None:
        """Write this chapter into an EPUB under construction.

        Each scene registers its own image resources via
        :meth:`Scene.write_epub`; the rendered chapter body is appended last.
        """
        for scene_index, scene in enumerate(self.scenes(), start=1):
            scene.write_epub(builder, chapter_index, scene_index)
        builder.add_chapter(self.title, self.to_xhtml(chapter_index))
