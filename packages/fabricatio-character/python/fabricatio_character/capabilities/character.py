"""This module contains the capabilities for the character."""

from abc import ABC
from typing import List, Unpack, overload

from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import TASK

from fabricatio_character.models.character import CharacterCard


class CharacterCompose(Propose, ABC):
    """This class contains the capabilities for the character."""

    @overload
    async def compose_characters(
        self,
        requirements: str,
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[CharacterCard]],
    ) -> CharacterCard | None: ...

    @overload
    async def compose_characters(
        self,
        requirements: list[str],
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> List[CharacterCard | None]: ...

    @overload
    async def compose_characters(
        self,
        requirements: list[str],
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[CharacterCard]],
    ) -> List[CharacterCard]: ...

    @overload
    async def compose_characters(
        self,
        requirements: str | list[str],
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[CharacterCard]],
    ) -> CharacterCard | List[CharacterCard | None] | List[CharacterCard] | None: ...

    async def compose_characters(
        self,
        requirements: str | list[str],
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[CharacterCard]],
    ) -> CharacterCard | List[CharacterCard | None] | List[CharacterCard] | None:
        """Delegate to propose() to resolve character(s) based on requirements.

        Args:
            requirements: A single requirement string or list of requirement strings.
            send_to: Routing group for LLM calls (TASK/SMOL/TINY/SLOW/PLAN).
            **kwargs: Passed through to propose().

        Returns:
            Resolved CharacterCard(s).
        """
        return await self.propose(CharacterCard, requirements, send_to=send_to, **kwargs)
