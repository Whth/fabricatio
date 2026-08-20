"""Output model for a composed novel: plan fields, materialized chapters and EPUB export."""

from pathlib import Path
from typing import List, Self

from fabricatio_capabilities.models.generic import PersistentAble

from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.plan import NovelPlan
from fabricatio_novel.models.series_book import SeriesBible
from fabricatio_novel.rust import NovelBuilder


class Novel(PersistentAble, NovelPlan):
    """A composed novel: its plan fields and the chapters it contains."""

    chapter: List[Chapter]

    @property
    def exact_word_count(self) -> int:
        """Sum the exact word counts of every chapter in this novel."""
        return sum(c.exact_word_count for c in self.chapter)

    @classmethod
    def from_context(cls, ctx: NovelContext) -> Self:
        """Materialize a novel from its novel context, materializing each chapter recursively."""
        return cls(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=ctx.expected_word_count,
            series_bible=ctx.series_bible or SeriesBible(),
            chapter=[Chapter.from_context(cc) for cc in ctx.chapter_context],
        )

    def dump_epub(
        self,
        path: str | Path,
        css: str | None = None,
        font: str | Path | None = None,
        font_family: str | None = None,
        cover: str | Path | None = None,
    ) -> Path:
        """Export the novel to an EPUB file at the given path.

        Optionally embeds a font and cover, then returns the written path.
        """
        builder = (
            NovelBuilder()
            .new_novel()
            .set_title(self.title)
            .set_description(self.description)
            .add_css(css or "p { text-indent: 2em; margin: 1em 0; line-height: 1.5; text-align: justify; }")
        )
        if font:
            family = font_family or Path(font).stem
            builder.add_font(family, Path(font))
            builder.add_css(f"body {{ font-family: '{family}'; }}")
        if cover:
            source = Path(cover)
            builder.add_cover_image(f"cover{source.suffix}", source)
        for chapter in self.chapter:
            builder.add_chapter(chapter.title, chapter.to_xhtml())
        builder.export(Path(path))
        return Path(path)
