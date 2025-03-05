"""A module for the task capabilities of the Fabricatio library."""

from typing import Type, Unpack

from fabricatio.models.generic import ProposedAble
from fabricatio.models.kwargs_types import GenerateKwargs
from fabricatio.models.usages import LLMUsage


class Propose(LLMUsage):
    """A class that proposes an Obj based on a prompt."""

    async def propose[C: ProposedAble](
        self,
        cls: Type[C],
        prompt: str,
        **kwargs: Unpack[GenerateKwargs],
    ) -> C:
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
