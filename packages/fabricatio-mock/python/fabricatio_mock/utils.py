"""Utility module for generating code and generic blocks.

Provides functions to generate fenced code blocks and generic content blocks.
"""

from contextlib import contextmanager
from typing import Generator
from unittest.mock import patch

from fabricatio_core.models import llm
from litellm import Router


def code_block(content: str, lang: str = "json") -> str:
    """Generate a code block."""
    return f"```{lang}\n{content}\n```"


def generic_block(content: str, lang: str = "String") -> str:
    """Generate a generic block."""
    return f"--- Start of {lang} ---\n{content}\n--- End of {lang} ---"


@contextmanager
def install_router(router: Router) -> Generator[None, None, None]:
    """Install a router."""
    with patch.object(llm, "ROUTER", router):
        yield
