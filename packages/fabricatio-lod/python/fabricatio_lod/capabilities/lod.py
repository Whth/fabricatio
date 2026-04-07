"""This module contains the capabilities for the lod."""

from abc import ABC

from fabricatio_core.capabilities.usages import UseLLM


class Lod(UseLLM, ABC):
    """This class contains the capabilities for the lod."""

    async def lod(self, **kwargs) -> None: ...
