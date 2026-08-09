from pathlib import Path
from typing import List, Self

from fabricatio_capabilities.models.generic import PersistentAble

from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.plan import NovelPlan
from fabricatio_novel.rust import NovelBuilder


class Novel(PersistentAble, NovelPlan):
    chapter: List[Chapter]

    @classmethod
    def from_context(cls, ctx: NovelContext) -> Self:
        return cls(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=ctx.expected_word_count,
            series_bible=ctx.series_bible,
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
