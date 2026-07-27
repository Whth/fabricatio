"""This module contains the models for the novel."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Self

from fabricatio_capabilities.models.generic import PersistentAble, WordCount
from fabricatio_character.models.character import CharacterCard
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.generic import SketchedAble, Titled
from fabricatio_core.rust import word_count
from pydantic import BaseModel, Field

from fabricatio_novel.config import novel_config
from fabricatio_novel.rust import text_to_xhtml_paragraphs

# ── Artifact format constants ──
CHAPTER_FILE_TEMPLATE = "chapter-{}.txt"
"""Filename template for chapter text files. ``str.format(chapter_index)`` to use."""

METADATA_FILE_NAME = "metadata.json"
"""Filename for the metadata JSON file."""


if TYPE_CHECKING:
    from fabricatio_novel.models.plan import ChapterPlan


class NovelExportChapterMeta(BaseModel):
    """Metadata entry for a single exported chapter."""

    index: int
    """Zero-based chapter index."""
    title: str
    """Chapter title."""
    file: str
    """Filename of the exported chapter text file."""


class NovelExportMeta(BaseModel):
    """Metadata for a Novel text export.

    Saved alongside the chapter text files as ``metadata.json``.
    """

    title: str
    """Novel title."""
    synopsis: str
    """Novel synopsis."""
    chapter_count: int
    """Number of chapters."""
    chapters: List[NovelExportChapterMeta]
    """Per-chapter metadata entries."""
    expected_word_count: int
    """Expected word count for the novel."""
    characters: List[CharacterCard] = Field(default_factory=list)
    """Character cards for this novel."""

    @classmethod
    def from_novel(cls, novel: "Novel") -> Self:
        """Build metadata from a Novel instance."""
        return cls(
            title=novel.title,
            synopsis=novel.synopsis,
            chapter_count=len(novel.chapters),
            chapters=[
                NovelExportChapterMeta(
                    index=ch.chapter_index,
                    title=ch.title,
                    file=CHAPTER_FILE_TEMPLATE.format(ch.chapter_index),
                )
                for ch in novel.chapters
            ],
            expected_word_count=novel.expected_word_count,
            characters=novel.characters,
        )

    @classmethod
    def from_file(cls, path: str | Path) -> Self:
        """Load metadata from a JSON file."""
        return cls.model_validate_json(Path(path).read_bytes())

    def save_to_file(self, path: str | Path) -> Path:
        """Write metadata to a JSON file.

        Returns the resolved path.
        """
        p = Path(path)
        p.write_text(self.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
        return p.resolve()

    @classmethod
    def from_artifacts(cls, artifacts_dir: str | Path) -> Self:
        """Load metadata from a previously exported artifacts directory.

        Expects a ``metadata.json`` file written by :meth:`dump_artifacts`
        inside *artifacts_dir*.

        Args:
            artifacts_dir: Directory containing exported novel artifacts.

        Returns:
            Parsed NovelExportMeta instance.
        """
        return cls.from_file(Path(artifacts_dir) / METADATA_FILE_NAME)


class Chapter(SketchedAble, PersistentAble, Titled, WordCount):
    """A chapter in a novel."""

    chapter_index: int
    """Zero-based index of this chapter within the novel."""

    content: str
    """Raw chapter text. May contain image references like ![prompt](path).
    Converted to XHTML paragraphs in to_xhtml()."""

    def to_xhtml(self) -> str:
        """Convert the chapter to XHTML format."""
        data: Dict[str, Any] = self.model_dump()
        data["content"] = text_to_xhtml_paragraphs(self.content)
        return TEMPLATE_MANAGER.render_template(novel_config.render_chapter_xhtml_template, data)

    @property
    def exact_word_count(self) -> int:
        """Calculate the exact word count of the chapter."""
        return word_count(self.content)

    @classmethod
    def with_raw_content(cls, raw: str, title: str, expected_word_count: int, chapter_index: int) -> Self:
        """Create a chapter from raw text. Content stored as-is; XHTML conversion deferred to to_xhtml()."""
        return cls(
            content=raw,
            title=title,
            expected_word_count=expected_word_count,
            chapter_index=chapter_index,
        )

    @classmethod
    def from_plan_and_raw_content(cls, chapter_plan: "ChapterPlan", raw: str) -> Self:
        """Create a chapter from a chapter plan and raw generated text."""
        return cls.with_raw_content(
            raw=raw,
            title=chapter_plan.draft.title,
            expected_word_count=chapter_plan.expected_word_count,
            chapter_index=chapter_plan.chapter_index,
        )


class Novel(SketchedAble, PersistentAble, Titled, WordCount):
    """A novel."""

    synopsis: str
    """A summary of the novel's plot."""
    chapters: List[Chapter]
    """List of chapters in the novel."""
    characters: List[CharacterCard] = Field(default_factory=list)
    """Character cards for this novel. Used by illustration pipeline to maintain visual consistency."""

    @property
    def exact_word_count(self) -> int:
        """Calculate the exact word count of the novel."""
        return sum(chapter.exact_word_count for chapter in self.chapters)

    @property
    def word_count_compliance_ratio(self) -> float:
        """Calculate the compliance ratio of the novel's word count."""
        return self.exact_word_count / self.expected_word_count

    def dump_artifacts(self, output_dir: str | Path) -> List[Path]:
        """Export each chapter as a UTF-8 text file, plus a metadata.json.

        Each chapter is saved as ``chapter-{index}.txt`` with the raw chapter content.

        A ``metadata.json`` file is written alongside containing the novel title,
        synopsis, chapter listing, and character cards (if set).

        Args:
            output_dir: Directory to write files into. Created if needed.

        Returns:
            Absolute paths to all written files, in chapter order plus metadata.
        """
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)

        result: List[Path] = []

        for chapter in self.chapters:
            path = output / CHAPTER_FILE_TEMPLATE.format(chapter.chapter_index)
            path.write_text(chapter.content, encoding="utf-8")
            result.append(path.resolve())

        meta = NovelExportMeta.from_novel(self)
        meta_path = meta.save_to_file(output / METADATA_FILE_NAME)
        result.append(meta_path)

        return result

    @classmethod
    def from_artifacts(cls, artifact_dir: str | Path) -> Self:
        """Reconstruct a Novel from a directory written by :meth:`dump_artifacts`.

        Reads ``metadata.json`` and each ``chapter-{index}.txt`` file from
        *artifact_dir* to rebuild the full Novel instance.

        Args:
            artifact_dir: Directory containing exported novel artifacts.

        Returns:
            Reconstructed Novel instance.
        """
        meta = NovelExportMeta.from_artifacts(artifact_dir)
        base = Path(artifact_dir)

        chapters: List[Chapter] = []
        for ch_meta in meta.chapters:
            raw = (base / ch_meta.file).read_text(encoding="utf-8")
            chapters.append(
                Chapter(
                    title=ch_meta.title,
                    content=raw,
                    chapter_index=ch_meta.index,
                    expected_word_count=word_count(raw),
                )
            )

        return cls(
            title=meta.title,
            synopsis=meta.synopsis,
            chapters=chapters,
            expected_word_count=meta.expected_word_count,
            characters=meta.characters,
        )
