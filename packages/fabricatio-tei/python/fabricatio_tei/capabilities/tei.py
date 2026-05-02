"""This module contains the capabilities for the tei."""

from abc import ABC

from fabricatio_core.capabilities.usages import UseLLM


class Tei(UseLLM, ABC):
    """This class contains the capabilities for the tei."""

    async def tei(self, **kwargs) -> None: ...
