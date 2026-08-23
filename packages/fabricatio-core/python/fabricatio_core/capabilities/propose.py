"""A module for the task capabilities of the Fabricatio library."""

from abc import ABC
from typing import Unpack, overload

from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.generic import ProposedAble
from fabricatio_core.models.kwargs_types import ValidateKwargs


class Propose(UseLLM, ABC):
    """A class that proposes an Obj based on a prompt."""

    @overload
    async def propose[M: ProposedAble](
        self,
        cls: type[M],
        prompt: list[str],
        send_to: str | None = None,
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> list[M | None]: ...

    @overload
    async def propose[M: ProposedAble](
        self,
        cls: type[M],
        prompt: list[str],
        send_to: str | None = None,
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> list[M]: ...

    @overload
    async def propose[M: ProposedAble](
        self,
        cls: type[M],
        prompt: str,
        send_to: str | None = None,
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> M | None: ...

    @overload
    async def propose[M: ProposedAble](
        self,
        cls: type[M],
        prompt: str,
        send_to: str | None = None,
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> M: ...

    @overload
    async def propose[M: ProposedAble](
        self,
        cls: type[M],
        prompt: list[str] | str,
        send_to: str | None = None,
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> M | list[M | None] | list[M] | None: ...

    async def propose[M: ProposedAble](
        self,
        cls: type[M],
        prompt: list[str] | str,
        send_to: str | None = None,
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> M | list[M | None] | list[M] | None:
        """Asynchronously proposes a task based on a given prompt and parameters.

        Parameters:
            cls: The class type of the task to be proposed.
            prompt: The prompt text for proposing a task, which is a string that must be provided.
            send_to: the completion model group to use
            **kwargs: The keyword arguments for the LLM (Large Language Model) usage.

        Returns:
            A Task object based on the proposal result.
        """
        return await self.aask_validate(
            question=cls.create_json_prompt(prompt),
            validator=cls.instantiate_from_string,
            send_to=send_to,
            **kwargs,
        )
