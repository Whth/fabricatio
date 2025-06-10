"""Module containing the Lyricize capability for generating lyrics based on requirements."""

from typing import List, Optional, Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs

from fabricatio_yue.config import yue_config


class Lyricize(Propose):
    """A capability class for generating lyrics based on requirements.

    This class extends the Propose capability to provide lyric generation functionality.
    It supports both single requirement strings and batch processing of multiple requirements.
    Uses the configured lyricize template to generate contextually appropriate lyrics.
    """

    @overload
    async def lyricize(self, requirement: str, **kwargs: Unpack[ValidateKwargs[Optional[str]]]) -> str:
        """Generate lyrics based on a single requirement.

        Args:
            requirement: Single requirement string for lyric generation
            **kwargs: Additional validation kwargs

        Returns:
            Generated lyrics as a string
        """
        ...

    @overload
    async def lyricize(
        self, requirement: List[str], **kwargs: Unpack[ValidateKwargs[Optional[str]]]
    ) -> List[str | None]:
        """Generate lyrics based on multiple requirements.

        Args:
            requirement: List of requirement strings for lyric generation
            **kwargs: Additional validation kwargs

        Returns:
            List of generated lyrics strings or None values
        """
        ...

    async def lyricize(
        self, requirement: str | List[str], **kwargs: Unpack[ValidateKwargs[Optional[str]]]
    ) -> None | str | List[str | None]:
        """Generate lyrics based on requirements.

        Args:
            requirement: Single requirement string or list of requirements for lyric generation
            **kwargs: Additional validation kwargs

        Returns:
            Generated lyrics as string, list of strings, or None based on input type
        """
        if isinstance(requirement, str):
            # Single requirement - return single lyric string
            prompt = TEMPLATE_MANAGER.render_template(yue_config.lyricize_template, {"requirement": requirement})
            return await self.ageneric_string(prompt, **kwargs)

        if isinstance(requirement, list):
            # Multiple requirements - return list of lyric strings using batch render
            prompts = TEMPLATE_MANAGER.render_template(
                yue_config.lyricize_template, [{"requirement": req} for req in requirement]
            )

            return await self.ageneric_string(prompts, **kwargs)

        raise TypeError(f"Invalid requirement type: {type(requirement)}. Expected str or List[str].")
