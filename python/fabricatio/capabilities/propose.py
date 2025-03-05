"""A module for the task capabilities of the Fabricatio library."""

from typing import List, Type, Unpack, overload

from fabricatio.models.generic import ProposedAble
from fabricatio.models.kwargs_types import GenerateKwargs
from fabricatio.models.usages import LLMUsage


class Propose[M: ProposedAble](LLMUsage):
    """A class that proposes an Obj based on a prompt."""

    @overload
    async def propose(
        self,
        cls: Type[M],
        prompt: List[str],
        **kwargs: Unpack[GenerateKwargs],
    ) -> List[M]: ...

    @overload
    async def propose(
        self,
        cls: Type[M],
        prompt: str,
        **kwargs: Unpack[GenerateKwargs],
    ) -> M: ...

    async def propose(
        self,
        cls: Type[M],
        prompt: List[str] | str,
        **kwargs: Unpack[GenerateKwargs],
    ) -> List[M] | M:
        """Asynchronously proposes a task based on a given prompt and parameters.

        Parameters:
            cls: The class type of the task to be proposed.
            prompt: The prompt text for proposing a task, which is a string that must be provided.
            **kwargs: The keyword arguments for the LLM (Large Language Model) usage.

        Returns:
            A Task object based on the proposal result.
        """
        if isinstance(prompt, str):
            return await self.aask_validate(
                question=cls.create_json_prompt(prompt),
                validator=cls.instantiate_from_string,
                **kwargs,
            )
        return await self.aask_validate_batch(
            questions=[cls.create_json_prompt(p) for p in prompt],
            validator=cls.instantiate_from_string,
            **kwargs,
        )
