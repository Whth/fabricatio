"""This module contains the capabilities for the novel."""

from abc import ABC

from fabricatio_core.capabilities.usages import UseLLM


class NovelCompose(UseLLM, ABC):
    """This class contains the capabilities for the novel."""

    async def novel(self, **kwargs) -> None: ...
