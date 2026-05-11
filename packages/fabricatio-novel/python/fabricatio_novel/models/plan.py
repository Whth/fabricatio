from typing import Self

from fabricatio_capabilities.models.generic import WordCount

from fabricatio_novel.models.novel import ChapterDraft
from fabricatio_novel.models.scripting import Script
from fabricatio_novel.utils import formated_title


class ChapterPlan(WordCount):
    chapter_index: int
    draft: ChapterDraft
    script: Script

    @property
    def formatted_chapter_title(self) -> str:
        return formated_title(self.chapter_index, self.draft.title)

    @classmethod
    def new(cls, draft: ChapterDraft, script: Script, expected_word_count: int, chapter_index: int) -> Self:
        """Create a new chapter plan."""
        return cls(draft=draft, script=script, expected_word_count=expected_word_count, chapter_index=chapter_index)

    @classmethod
    def with_try_script(
        cls, draft: ChapterDraft, script: None | Script, expected_word_count: int, chapter_index: int
    ) -> Self:

        return cls.new(
            draft=draft,
            script=script if script else Script.with_raw_synosis(draft.synopsis),
            expected_word_count=expected_word_count,
            chapter_index=chapter_index,
        )
