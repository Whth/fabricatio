from pathlib import Path
from typing import List, Self

from fabricatio_capabilities.models.generic import PersistentAble

from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.plan import NovelPlan
from fabricatio_novel.rust import NovelBuilder


_EPUB_LANGUAGE_MAP = {
    "English": "en",
    "简体中文": "zh-Hans",
    "繁體中文": "zh-Hant",
    "中文": "zh",
    "日本語": "ja",
    "한국어": "ko",
    "Français": "fr",
    "Deutsch": "de",
    "Español": "es",
    "Italiano": "it",
    "Português": "pt",
    "Русский": "ru",
    "العربية": "ar",
    "हिन्दी": "hi",
}


def _bcp47(language: str) -> str:
    return _EPUB_LANGUAGE_MAP.get(language, language)


def _inject_language(epub_path: Path, language: str) -> None:
    """Rewrite content.opf to add the dc:language metadata entry (EPUB3 requires it)."""
    import zipfile

    with zipfile.ZipFile(epub_path) as zf:
        opf_name = next(n for n in zf.namelist() if n.endswith("content.opf"))
        opf = zf.read(opf_name).decode("utf-8")
    if "<dc:language>" in opf:
        return
    opf = opf.replace(
        "<dc:identifier",
        f"<dc:language>{_bcp47(language)}</dc:language>\n    <dc:identifier",
        1,
    )
    tmp = epub_path.with_name(epub_path.name + ".tmp")
    with zipfile.ZipFile(epub_path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == opf_name:
                data = opf.encode("utf-8")
            zout.writestr(item, data)
    tmp.replace(epub_path)


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
        language: str | None = None,
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
        if language:
            _inject_language(Path(path), language)
        return Path(path)
