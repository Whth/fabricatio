"""This module contains the capabilities for the character."""

from abc import ABC
from typing import List, Unpack, overload

from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs

from fabricatio_character.models.character import CharacterCard


class CharacterCompose(Propose, ABC):
    """This class contains the capabilities for the character."""

    @overload
    async def compose_characters(
        self, requirements: str, **kwargs: Unpack[ValidateKwargs[CharacterCard]]
    ) -> None | CharacterCard:
        """Fetch a single character matching the requirement string, or None."""

    @overload
    async def compose_characters(
        self, requirements: list[str], **kwargs: Unpack[ValidateKwargs[None]]
    ) -> List[CharacterCard | None]:
        """Fetch multiple characters by requirements; may include None for unmatched."""

    @overload
    async def compose_characters(
        self, requirements: list[str], **kwargs: Unpack[ValidateKwargs[CharacterCard]]
    ) -> List[CharacterCard]:
        """Fetch multiple characters; raises or filters to ensure all results are valid."""

    async def compose_characters(
        self, requirements: str | list[str], **kwargs: Unpack[ValidateKwargs[CharacterCard]]
    ) -> None | CharacterCard | List[CharacterCard | None] | List[CharacterCard]:
        """Delegate to propose() to resolve character(s) based on requirements."""
        return await self.propose(CharacterCard, requirements, **kwargs)
