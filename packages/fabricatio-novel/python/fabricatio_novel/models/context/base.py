from abc import ABC
from typing import final, Generator, Self

from pydantic import Field

from fabricatio_capabilities.models.generic import WordCount, PersistentAble
from fabricatio_character.models.character import CharacterCard, CharacterCardDiff
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.utils import ok

from fabricatio_novel.models.series_book import SeriesBible


class CharactorTrace(SketchedAble):
    start: CharacterCard
    end: CharacterCard

    interpolates: list[CharacterCardDiff] = Field(default_factory=list)

    @final
    def iter_charactor_cards(self) -> Generator[CharacterCard, None, None]:
        """Iterate over the character cards along this trace, in evolution order.

        Yields the `start` card, then one card per interpolated diff applied
        to the previous state, and finally the `end` card.
        """
        card = self.start
        yield card
        for diff in self.interpolates:
            card = card.apply(diff)
            yield card
        yield self.end

    @final
    def intepl(self, diffs: list[CharacterCardDiff]) -> Self:
        self.interpolates = diffs
        return self


class ContextBase(WordCount, PersistentAble, ABC):
    charactor_trace: list[CharactorTrace] = Field(default_factory=list)

    language: str = ""
    """Written language; run-wide constant, set progressively during context creation."""

    series_bible: SeriesBible | None = None
    """The novel's setting bible; uninitialized until set or broadcast down from the novel context."""

    prefixed_content: str = ""
    """Everything composed before this element in the novel; injected by the parent before composition."""

    def set_language(self, language: str) -> Self:
        self.language = language
        return self

    def set_series_bible(self, series_bible: SeriesBible | None) -> Self:
        self.series_bible = series_bible
        return self

    def access_settings_bible(self) -> SeriesBible:
        """Return the initialized settings bible.

        Raises:
            ValueError: if the settings bible was never initialized on this context.
        """
        return ok(self.series_bible, f"Settings bible is not initialized on {self.__class__.__name__}")

    def iter_child_contexts(self) -> Generator["ContextBase", None, None]:
        """Yield this context's child contexts, in composition order; leaf contexts yield nothing."""
        yield from ()

    def broadcast_settings_bible(self) -> Self:
        """Push this context's settings bible onto every child context."""
        for child in self.iter_child_contexts():
            child.set_series_bible(self.series_bible)
        return self

    def set_prefixed_content(self, prefixed_content: str) -> Self:
        self.prefixed_content = prefixed_content
        return self
