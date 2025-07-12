"""This module contains the capabilities for the agent."""

from abc import ABC

from fabricatio_core.capabilities.usages import UseLLM


class Agent(UseLLM, ABC):
    """This class contains the capabilities for the agent."""

    async def agent(self, **kwargs) -> None: ...
