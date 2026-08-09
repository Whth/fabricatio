from typing import List, Self

from fabricatio_core import TEMPLATE_MANAGER

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.story import Story
from fabricatio_novel.rust import text_to_xhtml_paragraphs


class Chapter(ChapterPlan):
    story: List[Story]

    @classmethod
    def from_context(cls, ctx: ChapterContext) -> Self:
        return cls(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=ctx.expected_word_count,
            story=[Story.from_context(sc) for sc in ctx.story_context],
        )

    def to_xhtml(self) -> str:
        sections = [f"<h1>{self.title}</h1>"]
        for story in self.story:
            sections.append(f"<h2>{story.title}</h2>")
            for scene in story.scenes:
                sections.append(f"<h3>{scene.title}</h3>")
                sections.append(text_to_xhtml_paragraphs(scene.content))
        return TEMPLATE_MANAGER.render_template(
            novel_config.render_chapter_xhtml_template,
            {"title": self.title, "content": "\n".join(sections)},
        )
