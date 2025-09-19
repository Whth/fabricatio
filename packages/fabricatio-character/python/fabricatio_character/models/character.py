"""This module contains the models for the character."""

from typing import Annotated

from fabricatio_core.models.generic import SketchedAble, Named
from pydantic import Field


class CharacterCard(SketchedAble,Named):
    """A structured character profile for storytelling, role-playing, or AI narrative generation.

    Each field captures a core dimension of the character to ensure consistent and vivid portrayal.
    All fields are required and must contain at least one character.
    """

    name: Annotated[str, Field(min_length=1, examples=["Aragorn", "Agent K", "The Crimson Witch"])]
    """The character's identifying name (can be real name, alias, or title)."""

    role: Annotated[str, Field(min_length=1, examples=["Protagonist", "Villain", "Mentor", "Comic Relief", "Traitor"])]
    """The character’s narrative or functional role within the story."""

    look: Annotated[
        str,
        Field(
            min_length=1,
            examples=[
                "Tall and lean, wears a tattered trench coat, glowing cybernetic eye, always smirking.",
                "Short, muscular, covered in ritual tattoos, always barefoot.",
            ],
        ),
    ]
    """Visual appearance including clothing, physique, distinguishing features, and style."""

    act: Annotated[
        str,
        Field(
            min_length=1,
            examples=[
                "Speaks in riddles",
                "Nervously taps fingers when lying",
                "Charges into danger without hesitation",
            ],
        ),
    ]
    """Typical behaviors, mannerisms, speech patterns, or reactions under stress."""

    want: Annotated[
        str,
        Field(
            min_length=1,
            examples=[
                "Wants to reclaim their stolen throne",
                "Seeks redemption for past sins",
                "Desires freedom above all else",
            ],
        ),
    ]
    """The character’s core motivation or deepest goal driving their actions."""

    flaw: Annotated[
        str,
        Field(
            min_length=1,
            examples=["Overconfident to the point of recklessness", "Cannot forgive themselves", "Addicted to power"],
        ),
    ]
    """Critical weakness, moral failing, or psychological vulnerability that creates conflict."""

    note: Annotated[
        str,
        Field(
            min_length=1,
            examples=[
                "Secretly the protagonist’s half-sibling",
                "Afraid of water but hides it",
                "Will betray the team in Act 3",
            ],
        ),
    ]
    """Additional context, secrets, relationships, or production notes for writers or AI."""
