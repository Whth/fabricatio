"""Output model for a composed novel: plan fields, materialized chapters and EPUB export."""

from pathlib import Path
from typing import Self

from fabricatio_capabilities.models.generic import PersistentAble
from pydantic import Field

from fabricatio_novel.export import DEFAULT_EPUB_CSS
from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.plan import NovelPlan
from fabricatio_novel.models.series_book import SeriesBible
from fabricatio_novel.rust import NovelBuilder


class Novel(PersistentAble, NovelPlan):
    """A composed novel: its plan fields and the chapters it contains."""

    chapter: list[Chapter]

    series_bible: SeriesBible = Field(default_factory=SeriesBible)
    """The setting bible this novel was composed under, adopted from the context; the plan never carries one."""

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
            writing_constraints=list(ctx.writing_constraints),
            writing_styles=list(ctx.writing_styles),
            series_bible=ctx.series_bible or SeriesBible(),
            chapter=[Chapter.from_context(cc) for cc in ctx.child_contexts],
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

        Delegates per-chapter resource registration and body rendering to
        :meth:`Chapter.write_epub`; scenes inject their own figures and image
        resources via :meth:`Scene.write_epub`. Optionally embeds a font
        and cover, then returns the written path.
        """
        builder = (
            NovelBuilder()
            .new_novel()
            .set_title(self.title)
            .set_description(self.description)
            .add_css(css or DEFAULT_EPUB_CSS)
        )
        if font:
            family = font_family or Path(font).stem
            builder.add_font(family, Path(font))
            builder.add_css(f"body {{ font-family: '{family}'; }}")
        if cover:
            source = Path(cover)
            builder.add_cover_image(f"cover{source.suffix}", source)
        for chapter_index, chapter in enumerate(self.chapter, start=1):
            chapter.write_epub(builder, chapter_index)
        builder.export(Path(path))
        return Path(path)

    def dump_texts(self, dir_path: str | Path) -> Path:
        """Export each chapter as a plain-text file named by its zero-padded index.

        Writes ``01.txt``, ``02.txt`` … into the directory (created as needed); the padding
        widens past 99 chapters so filenames keep sorting correctly. Returns the directory.
        """
        out = Path(dir_path)
        out.mkdir(parents=True, exist_ok=True)
        width = max(2, len(str(len(self.chapter))))
        for index, chapter in enumerate(self.chapter, start=1):
            (out / f"{index:0{width}d}.txt").write_text(chapter.to_text(), encoding="utf-8")
        return out
