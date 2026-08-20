"""Output model for a composed chapter: the chapter plan plus its materialized stories."""

from typing import List, Self

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core import TEMPLATE_MANAGER

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.story import Story
from fabricatio_novel.rust import text_to_xhtml_paragraphs


class Chapter(ChapterPlan, WordCount):
    """A composed chapter: its plan fields and the stories it contains."""

    story: List[Story]

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
            story=[Story.from_context(sc) for sc in ctx.story_context],
        )

    def to_xhtml(self) -> str:
        """Render the chapter body as a full XHTML document.

        The chapter title is deliberately omitted: ``dump_epub`` already
        registers it once on the EPUB side via ``add_chapter(title, ...)``,
        so embedding it here would duplicate it in every chapter document.
        """
        sections = []
        for story in self.story:
            for scene in story.scenes:
                sections.append(text_to_xhtml_paragraphs(scene.content))
        return TEMPLATE_MANAGER.render_template(
            novel_config.render_chapter_xhtml_template,
            {"content": "\n".join(sections), "title": self.title},
        )
