"""This module contains the capabilities for the webui."""
from abc import ABC
from fabricatio_core.capabilities.usages import UseLLM


class Webui(UseLLM, ABC):
    """This class contains the capabilities for the webui."""

    async def webui(self, **kwargs): ...
