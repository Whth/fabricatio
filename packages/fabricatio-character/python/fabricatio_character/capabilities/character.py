"""This module contains the capabilities for the character."""

from abc import ABC
from typing import List, Unpack
from typing import overload

from fabricatio_character.models.character import CharacterCard
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs


class CharacterCompose(Propose, ABC):
    """This class contains the capabilities for the character."""

    @overload
    async def characters(self, requirements: str,
                         **kwargs: Unpack[ValidateKwargs[CharacterCard]]) -> None | CharacterCard:
        ...

    @overload
    async def characters(self, requirements: list[str], **kwargs: Unpack[ValidateKwargs[None]]) -> List[
        CharacterCard | None]:
        ...
    @overload
    async def characters(self, requirements: list[str], **kwargs: Unpack[ValidateKwargs[CharacterCard]]) -> List[
        CharacterCard ]:
        ...
    async def characters(self, requirements: str | list[str],
                         **kwargs: Unpack[ValidateKwargs[CharacterCard]]) -> None | CharacterCard | List[
        CharacterCard | None]|List[
        CharacterCard ]:
        return await self.propose(CharacterCard, requirements, **kwargs)

