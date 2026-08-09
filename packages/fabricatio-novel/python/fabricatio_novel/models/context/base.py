from abc import ABC
from typing import final, Generator, Self

from pydantic import Field

from fabricatio_capabilities.models.generic import WordCount, PersistentAble
from fabricatio_character.models.character import CharacterCard, CharacterCardDiff
from fabricatio_core.models.generic import SketchedAble

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

    series_bible: SeriesBible = Field(default_factory=SeriesBible)
    """The novel's setting bible; threaded down from the novel context."""

    prefixed_content: str = ""
    """Everything composed before this element in the novel; injected by the parent before composition."""

    def set_language(self, language: str) -> Self:
        self.language = language
        return self

    def set_series_bible(self, series_bible: SeriesBible) -> Self:
        self.series_bible = series_bible
        return self

    def set_prefixed_content(self, prefixed_content: str) -> Self:
        self.prefixed_content = prefixed_content
        return self
