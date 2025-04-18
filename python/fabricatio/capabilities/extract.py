"""A module that provide capabilities for extracting information from a given source to a model."""

from typing import List, Optional, Type, Unpack, overload

from fabricatio import TEMPLATE_MANAGER
from fabricatio.capabilities.propose import Propose
from fabricatio.config import configs
from fabricatio.models.generic import ProposedAble
from fabricatio.models.kwargs_types import ValidateKwargs


class Extract(Propose):
    """A class that extract information from a given source to a model."""

    @overload
    async def extract[M: ProposedAble](
        self,
        cls: Type[M],
        source: str,
        extract_requirement: Optional[str] = None,
        align_language: bool = True,
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> M: ...
    @overload
    async def extract[M: ProposedAble](
        self,
        cls: Type[M],
        source: str,
        extract_requirement: Optional[str] = None,
        align_language: bool = True,
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> Optional[M]: ...

    @overload
    async def extract[M: ProposedAble](
        self,
        cls: Type[M],
        source: List[str],
        extract_requirement: Optional[str] = None,
        align_language: bool = True,
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> List[M]: ...
    @overload
    async def extract[M: ProposedAble](
        self,
        cls: Type[M],
        source: List[str],
        extract_requirement: Optional[str] = None,
        align_language: bool = True,
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> List[Optional[M]]: ...
    async def extract[M: ProposedAble](
        self,
        cls: Type[M],
        source: List[str] | str,
        extract_requirement: Optional[str] = None,
        align_language: bool = True,
        **kwargs: Unpack[ValidateKwargs[Optional[M]]],
    ) -> M | List[M] | Optional[M] | List[Optional[M]]:
        """Extract information from a given source to a model."""
        return await self.propose(
            cls,
            prompt=TEMPLATE_MANAGER.render_template(
                configs.templates.extract_template,
                [{"source": s, "extract_requirement": extract_requirement} for s in source]
                if isinstance(source, list)
                else {"source": source, "extract_requirement": extract_requirement, "align_language": align_language},
            ),
            **kwargs,
        )
