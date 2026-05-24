"""This module contains the capabilities for the comfyui."""
from abc import ABC
from fabricatio_core.capabilities.usages import UseLLM


class Comfyui(UseLLM, ABC):
    """This class contains the capabilities for the comfyui."""

    async def comfyui(self, **kwargs): ...
