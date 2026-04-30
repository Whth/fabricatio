"""Utility module for generating code and generic blocks.

Provides functions to generate fenced code blocks and generic content blocks.
"""

from contextlib import contextmanager
from typing import Generator, List, Type
from unittest.mock import patch

from fabricatio_core import Role, rust
from fabricatio_core.rust import ProviderType, Router


def code_block(content: str, lang: str = "json") -> str:
    """Generate a code block."""
    return f"```{lang}\n{content}\n```"


def generic_block(content: str, lang: str = "String") -> str:
    """Generate a generic block."""
    return f"--- Start of {lang} ---\n{content}\n--- End of {lang} ---"


@contextmanager
def install_router(router: Router) -> Generator[None, None, None]:
    """Install a router."""
    with patch.object(rust, "ROUTER", router):
        yield


def setup_dummy_responses(*responses: str, group: str = "openai/gpt-3.5-turbo") -> None:
    """Configure the singleton router with dummy responses for testing.

    Mutates the singleton ROUTER in-place. The DummyModel uses LIFO (Vec::pop),
    so responses are reversed to preserve FIFO semantics.

    Args:
        *responses: Pre-formatted response strings (e.g. code_block, generic_block).
        group: Route group name. Defaults to match LLMTestRole.llm_send_to.
    """
    rust.ROUTER.add_provider(ProviderType.Dummy)
    rust.ROUTER.add_or_update_dummy_completion_model(group, "dummy/test-model", list(reversed(responses)))


@contextmanager
def install_router_usage(*responses: str, group: str = "openai/gpt-3.5-turbo") -> Generator[None, None, None]:
    """Configure the singleton router with dummy responses for testing.

    Mutates the singleton ROUTER in-place. The DummyModel uses LIFO (Vec::pop),
    so responses are reversed to preserve FIFO semantics.

    Args:
        *responses: Pre-formatted response strings (e.g. code_block, generic_block).
        group: Route group name. Defaults to match LLMTestRole.llm_send_to.
    """
    setup_dummy_responses(*responses, group=group)
    yield


def make_roles(names: List[str], role_cls: Type[Role] = Role) -> List[Role]:
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
