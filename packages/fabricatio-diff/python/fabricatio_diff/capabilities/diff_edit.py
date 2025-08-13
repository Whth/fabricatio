"""Module for handling diff-based editing operations."""

from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import ValidateKwargs

from fabricatio_diff.config import diff_config
from fabricatio_diff.models.diff import Diff
from fabricatio_diff.utils import ReplaceCapture, SearchCapture


class DiffEdit(UseLLM, ABC):
    """A class for performing diff-based edits using a language model.

    Inherits from UseLLM and ABC to enable language model usage and abstract base class functionality.
    """

    async def diff_edit(
        self,
        source: str,
        requirement: str,
        match_precision: float | None = None,
        **kwargs: Unpack[ValidateKwargs[Diff]],
    ) -> str | None:
        """Perform a diff edit operation on the provided source string based on the given requirement.

        Args:
            source (str): The original string to be edited.
            requirement (str): The requirement or target state that guides the edit.
            match_precision (float | None): The precision level for matching lines.
            **kwargs: Additional keyword arguments passed to the diff method.

        Returns:
            str | None: The edited string if a valid diff is applied; otherwise, None.
        """
        diff = await self.diff(source, requirement, **kwargs)
        if diff:
            return diff.apply(source, match_precision or diff_config.match_precision)
        logger.warn("Failed to generate a valid diff.")
        return None

    async def diff(self, source: str, requirement: str, **kwargs: Unpack[ValidateKwargs[Diff]]) -> Diff | None:
        """Generate a Diff object by querying the language model with a prompt template.

        Internally uses `_validator` to validate the response and construct a Diff instance.

        Args:
            source (str): The original string to compare.
            requirement (str): The desired changes or content to match.
            **kwargs: Validated keyword arguments specific to the Diff type.

        Returns:
            Diff | None: A Diff instance if validation succeeds; otherwise, None.
        """

        def _validator(resp: str) -> Diff | None:
            """Validate and extract search and replace strings from the LLM response.

            Args:
                resp (str): The raw string response from the language model.

            Returns:
                Diff | None: A Diff object containing the extracted search and replace strings,
                             or None if extraction fails.
            """
            sear = SearchCapture.capture(resp)
            repl = ReplaceCapture.capture(resp)
            return Diff(search=sear, replace=repl) if sear else None

        return await self.aask_validate(
            TEMPLATE_MANAGER.render_template(
                diff_config.diff_template,
                {"source": source, "requirement": requirement},
            ),
            _validator,
            **kwargs,
        )
