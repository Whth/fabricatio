"""This module contains the capabilities for the diff."""

from abc import ABC

from fabricatio_core.capabilities.usages import UseLLM


class Diff(UseLLM, ABC):
    """This class contains the capabilities for the diff."""

    async def diff(self, **kwargs) -> None: ...
