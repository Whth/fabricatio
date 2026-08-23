"""A module that provide capabilities for extracting information from a given source to a model."""

from abc import ABC
from typing import Unpack, overload

from fabricatio import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.generic import ProposedAble
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import TASK

from fabricatio_capabilities.config import capabilities_config


class Extract(Propose, ABC):
    """A class that extract information from a given source to a model."""

    @overload
    async def extract[M: ProposedAble](
        self,
        cls: type[M],
        source: str,
        extract_requirement: str | None = None,
        align_language: bool = True,
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> M: ...

    @overload
    async def extract[M: ProposedAble](
        self,
        cls: type[M],
        source: str,
        extract_requirement: str | None = None,
        align_language: bool = True,
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> M | None: ...

    @overload
    async def extract[M: ProposedAble](
        self,
        cls: type[M],
        source: list[str],
        extract_requirement: str | None = None,
        align_language: bool = True,
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> list[M]: ...

    @overload
    async def extract[M: ProposedAble](
        self,
        cls: type[M],
        source: list[str],
        extract_requirement: str | None = None,
        align_language: bool = True,
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> list[M | None]: ...

    async def extract[M: ProposedAble](
        self,
        cls: type[M],
        source: list[str] | str,
        extract_requirement: str | None = None,
        align_language: bool = True,
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[M | None]],
    ) -> M | list[M] | list[M | None] | None:
        """Extract information from a given source to a model.

        Args:
            cls (Type[M]): The model class to extract information into.
            source (List[str] | str): The source string(s) to extract from.
            extract_requirement (Optional[str]): What to extract; defaults to the class docstring.
            align_language (bool): Whether to align extraction language with the source. Defaults to True.
            send_to: Routing-group variant for the LLM call. Resolved against the agent variant
                registry (see `fabricatio_core.rust`). Defaults to `TASK`; pass `SMOL`/`TINY`/`PLAN`
                to steer to a different model tier.
            **kwargs (Unpack[ValidateKwargs[Optional[M]]]): Additional validation keyword arguments.
        """
        return await self.propose(
            cls,
            prompt=TEMPLATE_MANAGER.render_template(
                capabilities_config.extract_template,
                [{"source": s, "extract_requirement": extract_requirement} for s in source]
                if isinstance(source, list)
                else {"source": source, "extract_requirement": extract_requirement, "align_language": align_language},
            ),
            send_to=send_to,
            **kwargs,
        )
