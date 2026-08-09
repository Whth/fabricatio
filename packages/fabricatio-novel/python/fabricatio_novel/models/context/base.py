from abc import ABC
from typing import final, Generator, Self

from pydantic import Field

from fabricatio_capabilities.models.generic import WordCount, PersistentAble
from fabricatio_character.models.character import CharacterCard, CharacterCardDiff
from fabricatio_core.models.generic import SketchedAble


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

    def set_language(self, language: str) -> Self:
        self.language = language
        return self
