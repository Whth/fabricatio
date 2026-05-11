"""Chapter plan model bundling draft, script, and word count per chapter."""

from typing import List, Self

from fabricatio_capabilities.models.generic import WordCount

from fabricatio_novel.models.novel import ChapterDraft, NovelDraft
from fabricatio_novel.models.scripting import Script
from fabricatio_novel.utils import formated_title


class ChapterPlan(WordCount):
    """A per-chapter plan combining the draft outline, generated script, and target word count."""

    chapter_index: int
    """Zero-based index of this chapter within the novel."""

    draft: ChapterDraft
    """The chapter draft containing title, synopsis, and weight."""

    script: Script
    """The narrative script outlining scenes for this chapter."""

    @classmethod
    def from_draft(cls, draft: NovelDraft, scripts: List[Script | None]) -> List[Self]:
        """Build chapter plans by pairing each chapter draft with its script."""
        return [cls.with_try_script(d, s, wc, i) for ((i, wc, d), s) in zip(draft.iter_chap(), scripts, strict=True)]

    @property
    def formatted_chapter_title(self) -> str:
        """Return the display title as 'Ch-{idx}: {title}'."""
        return formated_title(self.chapter_index, self.draft.title)

    @classmethod
    def new(cls, draft: ChapterDraft, script: Script, expected_word_count: int, chapter_index: int) -> Self:
        """Create a new chapter plan."""
        return cls(draft=draft, script=script, expected_word_count=expected_word_count, chapter_index=chapter_index)

    @classmethod
    def with_try_script(
        cls, draft: ChapterDraft, script: None | Script, expected_word_count: int, chapter_index: int
    ) -> Self:
        """Create a plan, falling back to a raw-synopsis script when script is None."""
        return cls.new(
            draft=draft,
            script=script if script else Script.with_raw_synosis(draft.synopsis),
            expected_word_count=expected_word_count,
            chapter_index=chapter_index,
        )
