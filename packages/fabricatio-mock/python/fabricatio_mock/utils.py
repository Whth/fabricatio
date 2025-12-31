"""Utility module for generating code and generic blocks.

Provides functions to generate fenced code blocks and generic content blocks.
"""

from contextlib import contextmanager
from typing import Generator, Type, List
from unittest.mock import patch

from fabricatio_core import Role
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


def make_roles( names: List[str],role_cls:Type[Role]=Role) -> List[Role]:
    """Create a list of Role objects from a list of names.

    Args:
        names (List[str]): A list of names for the roles.
        role_cls (Type[Role]): The Role class to instantiate.

    Returns:
        List[Role]: A list of Role objects with the given names.
    """
    return [role_cls(name=name, description="test") for name in names]


def make_n_roles(n: int, role_cls: Type[Role] = Role) -> List[Role]:
    """Create a list of Role objects with a given number of names.

    Args:
        n (int): The number of names.
        role_cls (Type[Role]): The Role class to instantiate.

    Returns:
        List[Role]: A list of Role objects with the given number of names.
    """
    return [role_cls(name=f"Role {i}", description="test") for i in range(1, n + 1)]
