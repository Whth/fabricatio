"""This module contains the models for the character."""

from typing import ClassVar, Dict, Self

from fabricatio_capabilities.models.generic import AsPrompt, PersistentAble
from fabricatio_core.models.generic import JSONList, Named, SketchedAble

from fabricatio_character.config import character_config


class CharacterCard(SketchedAble, Named, AsPrompt, PersistentAble):
    """A character as they currently are: a stable identity plus the mutable state of the moment.

    The identity fields (``name``, ``role``, ``want``) change slowly; the state fields
    (``look``, ``act``, ``flaw``, ``where``, ``condition``, ``mood``, ``goal``) describe
    how the character is right now and evolve as the story progresses. All fields are
    required and non-empty.
    """

    name: str
    """The character's identifying name (can be real name, alias, or title)."""

    role: str
    """The character's current narrative or functional role within the story."""

    look: str
    """How the character currently appears: clothing, physique, distinguishing features, wounds, disguise."""

    act: str
    """How the character currently behaves: mannerisms, speech patterns, reactions under stress."""

    want: str
    """The character's core motivation or deepest goal driving their actions (slow-changing)."""

    flaw: str
    """The character's current vulnerability: weakness, moral failing, or psychological pressure."""

    where: str
    """Where the character currently is and what surrounds them: location and immediate situation."""

    condition: str
    """The character's current physical state: health, energy, injuries, resources."""

    mood: str
    """The character's current emotional state."""

    goal: str
    """What the character is trying to achieve right now, as opposed to the deeper ``want``."""

    rendering_template: ClassVar[str] = character_config.render_character_card_template

    def _as_prompt_inner(self) -> Dict[str, str]:
        return self.model_dump()

    def apply(self, diff: "CharacterCardDiff") -> Self:
        """Apply a character card diff to this card.

        Returns:
            Self: A new card updated with the diff fields, excluding unset (``None``)
            values and the diff's ``reason`` field.
        """
        return self.model_copy(update=diff.model_dump(exclude_none=True, exclude={"reason"}))


class CharacterCardDiff(CharacterCard):
    """A partial character card used to express incremental updates to an existing character.

    Every field except ``reason`` is optional; only the fields that are
    set will be applied.
    """

    name: str | None = None
    """The character's identifying name (can be real name, alias, or title)."""

    role: str | None = None
    """The character's current narrative or functional role within the story."""

    look: str | None = None
    """How the character currently appears: clothing, physique, distinguishing features, wounds, disguise."""

    act: str | None = None
    """How the character currently behaves: mannerisms, speech patterns, reactions under stress."""

    want: str | None = None
    """The character's core motivation or deepest goal driving their actions (slow-changing)."""

    flaw: str | None = None
    """The character's current vulnerability: weakness, moral failing, or psychological pressure."""

    where: str | None = None
    """Where the character currently is and what surrounds them: location and immediate situation."""

    condition: str | None = None
    """The character's current physical state: health, energy, injuries, resources."""

    mood: str | None = None
    """The character's current emotional state."""

    goal: str | None = None
    """What the character is trying to achieve right now, as opposed to the deeper ``want``."""

    reason: str
    """Reason why the change happen"""


class CharacterCardDiffs(JSONList[CharacterCardDiff]):
    """A bare JSON array of character-card diffs as the LLM returns it."""


class CharacterCardSlices(JSONList[list[CharacterCardDiff]]):
    """A bare JSON array of per-child diff slices as the LLM returns it."""
