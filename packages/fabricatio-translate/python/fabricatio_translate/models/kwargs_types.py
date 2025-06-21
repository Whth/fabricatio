"""Type hints for TranslateKwargs.

This module defines the valid keyword arguments accepted by translation-related
functions and methods in Fabricatio Translate. These type hints help ensure proper
parameter validation and typing throughout the package.
"""

from fabricatio_core.models.kwargs_types import ValidateKwargs


class TranslateKwargs(ValidateKwargs[str], total=False):
    """Translate kwargs."""

    target_language: str
    specification: str


class TranslateChunkedKwargs(TranslateKwargs):
    """Translate kwargs."""

    chunk_size: int
