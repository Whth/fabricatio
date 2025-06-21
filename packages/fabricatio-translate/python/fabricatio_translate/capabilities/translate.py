"""Translate capability for translating text using LLM.

This module provides the Translate class, which utilizes the UseLLM base class to provide
translation functionality. It renders a translation template and executes it via the
LLM infrastructure.
"""

import asyncio
from typing import List, Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import split_into_chunks
from fabricatio_core.utils import ok

from fabricatio_translate.config import translate_config


def fill_empty(source: List[str], translated: List[str] | List[str | None] | None) -> List[str]:
    """Fill empty translations."""
    if translated is None:
        logger.warning("No translations provided, returning source text.")
        return source

    return [t or s for s, t in zip(source, translated, strict=True)]


class Translate(UseLLM):
    """A translation class that uses LLM for translating text.

    This class leverages the UseLLM base class to perform translations by rendering
    a translation template and executing it using the LLM infrastructure.
    """

    @overload
    async def translate(
        self,
        text: str,
        target_language: str,
        specification: str = "",
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> None | str: ...

    @overload
    async def translate(
        self,
        text: List[str],
        target_language: str,
        specification: str = "",
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> None | List[str] | List[str | None]: ...

    async def translate(
        self,
        text: str | List[str],
        target_language: str,
        specification: str = "",
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> None | str | List[str] | List[str | None]:
        """Translate the provided text into the target language.

        Args:
            text (str | List[str]): The input text or list of texts to be translated.
            target_language (str): The language into which the text should be translated.
            specification (str): The translation specification.
            **kwargs (Unpack[ValidateKwargs[str]]): Additional keyword arguments for customization.

        Returns:
            None | str | List[str] | List[str | None]: Translated text(s), with possible None values
            if translation fails for any item in the list.
        """
        return await self.ageneric_string(
            TEMPLATE_MANAGER.render_template(
                translate_config.translate_template,
                [{"text": t, "target_language": target_language, "specification": specification} for t in text]
                if isinstance(text, list)
                else {"text": text, "target_language": target_language, "specification": specification},
            ),
            **kwargs,
        )

    @overload
    async def translate_chunked(
        self,
        text: str,
        target_language: str,
        chunk_size: int = 6000,
        specification: str = "",
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> None | str: ...

    @overload
    async def translate_chunked(
        self,
        text: List[str],
        target_language: str,
        chunk_size: int = 6000,
        specification: str = "",
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> None | List[str] | List[str | None]: ...

    async def translate_chunked(
        self,
        text: str | List[str],
        target_language: str,
        chunk_size: int = 6000,
        specification: str = "",
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> None | str | List[str] | List[str | None]:
        """Translate the provided text into the target language in a chunked manner.

        Args:
            text: The input text or list of texts to be translated.
            target_language: The target language for translation.
            chunk_size: Maximum size of each text chunk.
            specification: Additional translation instructions.
            **kwargs: Additional arguments for the translation.

        Returns:
            Translated text(s) in the same format as input (str or List[str]).
            Returns None if translation fails.

        Warnings:
            the chunk_size is in unit of words, not characters.
        """
        # Convert single string to list for uniform processing
        was_str = isinstance(text, str)
        texts = [text] if was_str else text
        chunked_seq: List[List[str]] = [split_into_chunks(t, chunk_size, max_overlapping_rate=0.0) for t in texts]

        chunk_translations = ok(
            await asyncio.gather(
                *[
                    self.translate(
                        c,
                        target_language,
                        specification,
                        **kwargs,
                    )
                    for c in chunked_seq
                ]
            ),
            "Failed to translate chunked text.",
        )

        results = [
            "".join(fill_empty(chunked, trans)) for chunked, trans in zip(chunked_seq, chunk_translations, strict=True)
        ]

        # Return in same format as input
        return results[0] if was_str else results
