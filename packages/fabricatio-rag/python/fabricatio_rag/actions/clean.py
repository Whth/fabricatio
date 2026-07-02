"""Text cleaning actions using LLM-guided hashline edits."""

from abc import ABC
from typing import Any, ClassVar

from fabricatio_core.models.action import Action

from fabricatio_rag.capabilities.clean import CleanText


class CleanAction(Action, CleanText, ABC):
    """Clean text(s) until they satisfy a given guideline."""

    ctx_override: ClassVar[bool] = True

    async def _execute(
        self,
        clean_guideline: str,
        text: str | list[str],
        *_: Any,
        **cxt,
    ) -> str | list[str]:
        return await self.clean(clean_guideline, text)
