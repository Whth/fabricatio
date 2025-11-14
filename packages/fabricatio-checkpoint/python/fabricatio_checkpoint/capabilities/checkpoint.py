"""This module contains the capabilities for the checkpoint."""
from abc import ABC
from fabricatio_core.capabilities.usages import UseLLM


class Checkpoint(UseLLM, ABC):
    """This class contains the capabilities for the checkpoint."""

    async def checkpoint(self, **kwargs): ...
