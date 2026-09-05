"""Output model for a composed novel: plan fields, materialized chapters and EPUB export."""

from pathlib import Path
from typing import Self

from fabricatio_capabilities.models.generic import PersistentAble
from fabricatio_core import logger
from pydantic import Field

from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.illustration import IllustratedScene
from fabricatio_novel.models.plan import NovelPlan
from fabricatio_novel.models.series_book import SeriesBible
from fabricatio_novel.rust import NovelBuilder
from fabricatio_novel.utils import scene_image_name

_ILLUSTRATION_CSS = (
    "figure.illustration { text-indent: 0; margin: 1em auto; text-align: center; } "
    "figure.illustration img { max-width: 100%; }"
)


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

        Registers every illustrated scene's PNG as an EPUB image resource and
        embeds the matching ``<figure>`` in the chapter body. Optionally embeds
        a font and cover, then returns the written path.
        """
        builder = (
            NovelBuilder()
            .new_novel()
            .set_title(self.title)
            .set_description(self.description)
            .add_css(
                css
                or f"p {{ text-indent: 2em; margin: 1em 0; line-height: 1.5; text-align: justify; }} {_ILLUSTRATION_CSS}"
            )
        )
        if font:
            family = font_family or Path(font).stem
            builder.add_font(family, Path(font))
            builder.add_css(f"body {{ font-family: '{family}'; }}")
        if cover:
            source = Path(cover)
            builder.add_cover_image(f"cover{source.suffix}", source)
        for chapter_index, chapter in enumerate(self.chapter, start=1):
            scene_index = 0
            for story in chapter.story:
                for scene in story.scenes:
                    scene_index += 1
                    if not isinstance(scene, IllustratedScene) or not scene.illustration_image:
                        continue
                    source = Path(scene.illustration_image)
                    if source.is_file():
                        builder.add_resource(scene_image_name(chapter_index, scene_index), source)
                    else:
                        logger.warn(
                            f"Illustration file missing for scene {scene_index} of chapter {chapter_index}: {source}"
                        )
            builder.add_chapter(chapter.title, chapter.to_xhtml(chapter_index))
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
