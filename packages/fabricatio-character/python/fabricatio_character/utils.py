"""Utilities for character cards."""

from fabricatio_character.models.character import CharacterCard


def dump_card(*card: CharacterCard) -> str:
    """Dump character cards."""
    return "\n".join(c.as_prompt() for c in card)
