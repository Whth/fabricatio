"""This module contains the models for the character."""

from typing import ClassVar, Dict, Self

from fabricatio_capabilities.models.generic import AsPrompt, PersistentAble
from fabricatio_character.config import character_config
from fabricatio_core.models.generic import Named, SketchedAble


class CharacterCard(SketchedAble, Named, AsPrompt, PersistentAble):
    """A structured character profile for storytelling, role-playing, or AI narrative generation.

    Each field captures a core dimension of the character to ensure consistent and vivid portrayal.
    All fields are required and must contain at least one character.
    """

    name: str
    """The character's identifying name (can be real name, alias, or title)."""

    role: str
    """The character’s narrative or functional role within the story."""

    look: str
    """Visual appearance including clothing, physique, distinguishing features, and style."""

    act: str
    """Typical behaviors, mannerisms, speech patterns, or reactions under stress."""

    want: str
    """The character’s core motivation or deepest goal driving their actions."""

    flaw: str
    """Critical weakness, moral failing, or psychological vulnerability that creates conflict."""

    rendering_template: ClassVar[str] = character_config.render_character_card_template

    def _as_prompt_inner(self) -> Dict[str, str]:
        return self.model_dump()

    def apply(self, diff: "CharacterCardDiff") -> Self:
        return self.model_copy(update=diff.model_dump(exclude_none=True))


class CharacterCardDiff(CharacterCard):
    """A partial character card used to express incremental updates to an existing character.

    Every field is optional; only the fields that are set will be applied.
    """

    name: str | None = None
    """The character's identifying name (can be real name, alias, or title)."""

    role: str | None = None
    """The character's narrative or functional role within the story."""

    look: str | None = None
    """Visual appearance including clothing, physique, distinguishing features, and style."""

    act: str | None = None
    """Typical behaviors, mannerisms, speech patterns, or reactions under stress."""

    want: str | None = None
    """The character's core motivation or deepest goal driving their actions."""

    flaw: str | None = None
    """Critical weakness, moral failing, or psychological vulnerability that creates conflict."""
