"""A module for the task capabilities of the Fabricatio library."""

from abc import ABC
from typing import List, Optional, Type, Unpack, overload

from fabricatio_core.models.generic import ProposedAble
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.models.usages import LLMUsage


class Propose(LLMUsage, ABC):
    """A class that proposes an Obj based on a prompt."""

    @overload
    async def propose[M: ProposedAble](
        self,
        cls: Type[M],
        prompt: List[str],
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> List[Optional[M]]: ...

    @overload
    async def propose[M: ProposedAble](
        self,
        cls: Type[M],
        prompt: List[str],
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> List[M]: ...

    @overload
    async def propose[M: ProposedAble](
        self,
        cls: Type[M],
        prompt: str,
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> Optional[M]: ...

    @overload
    async def propose[M: ProposedAble](
        self,
        cls: Type[M],
        prompt: str,
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> M: ...

    async def propose[M: ProposedAble](
        self,
        cls: Type[M],
        prompt: List[str] | str,
        **kwargs: Unpack[ValidateKwargs[Optional[M]]],
    ) -> Optional[M] | List[Optional[M]] | M | List[M]:
        """Asynchronously proposes a task based on a given prompt and parameters.

        Parameters:
            cls: The class type of the task to be proposed.
            prompt: The prompt text for proposing a task, which is a string that must be provided.
            **kwargs: The keyword arguments for the LLM (Large Language Model) usage.

        Returns:
            A Task object based on the proposal result.
        """
        return await self.aask_validate(
            question=cls.create_json_prompt(prompt),
            validator=cls.instantiate_from_string,
            **kwargs,
        )
