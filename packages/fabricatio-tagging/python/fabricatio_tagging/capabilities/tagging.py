"""Tagging capabilities module.

This module provides functionality for generating tags from text content
using AI models through the Tagging class.
"""

from asyncio import gather
from typing import List, overload

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import GenerateKwargs
from typing_extensions import Unpack

from fabricatio_tagging.config import tagging_config


class Tagging(Propose):
    """A class for generating tags from text content using AI models.

    This class extends the Propose capability to provide tagging functionality
    for both individual text strings and lists of text strings.
    """

    @overload
    async def tagging(
        self, text: str, requirement: str = "", k: int = 0, **kwargs: Unpack[GenerateKwargs]
    ) -> List[str] | None:
        """Generate tags for a single text string.

        Args:
            text: The input text to generate tags for.
            requirement: Additional requirements or constraints for tag generation.
            k: Maximum number of tags to generate (0 for no limit).
            **kwargs: Additional generation parameters.

        Returns:
            A list of generated tags or None if generation fails.
        """
        ...

    @overload
    async def tagging(
        self, text: List[str], requirement: str = "", k: int = 0, **kwargs: Unpack[GenerateKwargs]
    ) -> List[List[str]]:
        """Generate tags for multiple text strings.

        Args:
            text: A list of input texts to generate tags for.
            requirement: Additional requirements or constraints for tag generation.
            k: Maximum number of tags to generate per text (0 for no limit).
            **kwargs: Additional generation parameters.

        Returns:
            A list of tag lists, one for each input text.
        """
        ...

    async def tagging(
        self, text: str | List[str], requirement: str = "", k: int = 0, **kwargs: Unpack[GenerateKwargs]
    ) -> List[List[str]] | List[str] | None:
        """Generate tags for text content.

        This method can handle both single text strings and lists of text strings,
        generating appropriate tags based on the provided requirements.

        Args:
            text: The input text(s) to generate tags for. Can be a single string
                or a list of strings.
            requirement: Additional requirements or constraints for tag generation.
                Defaults to empty string.
            k: Maximum number of tags to generate (0 for no limit). Defaults to 0.
            **kwargs: Additional generation parameters passed to the underlying
                AI model.

        Returns:
            For single text input: A list of generated tags or None if generation fails.
            For multiple text input: A list of tag lists, one for each input text.

        Raises:
            TypeError: If text is neither a string nor a list of strings.
        """
        if isinstance(text, str):
            return await self.alist_str(
                TEMPLATE_MANAGER.render_template(
                    tagging_config.tagging_template, {"text": text, "requirement": requirement}
                ),
                k=k,
                **kwargs,
            )
        if isinstance(text, list):
            rendered = TEMPLATE_MANAGER.render_template(
                tagging_config.tagging_template, [{"text": t, "requirement": requirement} for t in text]
            )

            tags_seq = await gather(*[self.alist_str(r, k=k, **kwargs) for r in rendered])

            return [t or [] for t in tags_seq]

        raise TypeError("text must be str or List[str]")
