"""Module-level docstring explaining the purpose of this test module.

This module contains unit tests for LLM-related functionality within the Role class,
specifically focusing on methods that interact with the UseLLM capability.
"""

from typing import Any, Optional
from unittest.mock import AsyncMock, patch

import litellm
import pytest
from fabricatio_core import Role
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models import llm
from litellm import Router
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.utils import ModelResponse


@pytest.fixture
def mock_router(ret_value: str) -> Router:
    """Fixture to create a mocked router with predefined response.

    Args:
        ret_value: The value to be returned by the mocked completion

    Returns:
        Configured AsyncMock router object
    """
    mock = AsyncMock(spec=Router)

    async def _acomp_wrapper(*args: Any, **kwargs: Any) -> ModelResponse | CustomStreamWrapper:
        return litellm.mock_completion(*args, mock_response=ret_value, **kwargs)

    mock.acompletion = _acomp_wrapper
    return mock


class LLMRole(Role, UseLLM):
    """Test class combining Role and UseLLM functionality.

    A concrete implementation of Role mixed with UseLLM capabilities
    for testing purposes.
    """

    pass


@pytest.fixture(autouse=True)
def role_with_llm() -> LLMRole:
    """Fixture providing an LLM-enabled role instance.

    Creates and returns an instance of LLMRole for testing.

    Returns:
        Ready-to-use LLMRole instance
    """
    return LLMRole()


@pytest.mark.parametrize("ret_value", ["Hi", "Hello"])
@pytest.mark.asyncio
async def test_router_completion(mock_router: Router, ret_value: str) -> None:
    """Test basic router completion functionality.

    Verifies that the router correctly handles completion requests
    and returns expected responses.

    Args:
        mock_router: Preconfigured mock router fixture
        ret_value: Expected response value
    """
    response = await mock_router.acompletion(model="openai/gpt-3.5-turbo", messages=[{"role": "user", "content": "Hi"}])
    assert response.choices[0].message.content == ret_value


@pytest.mark.parametrize("ret_value", ["Hi", "Hello"])
@pytest.mark.asyncio
async def test_aquery(mock_router: Router, ret_value: str, role_with_llm: LLMRole) -> None:
    """Test asynchronous query functionality.

    Validates that the aquery method correctly interacts with the LLM
    through the router and processes responses.

    Args:
        mock_router: Preconfigured mock router fixture
        ret_value: Expected response value
        role_with_llm: Test role with LLM capabilities
    """
    with patch.object(llm, "ROUTER", mock_router):
        assert (
            await role_with_llm.aquery(model="openai/gpt-3.5-turbo", messages=[{"role": "user", "content": "Hi"}])
        ).choices[0].message.content == ret_value


@pytest.mark.parametrize("ret_value", ["Hi", "Hello"])
@pytest.mark.asyncio
async def test_aask(mock_router: Router, ret_value: str, role_with_llm: LLMRole) -> None:
    """Test asynchronous ask functionality.

    Ensures that simple question answering works as expected
    through the LLM interface.

    Args:
        mock_router: Preconfigured mock router fixture
        ret_value: Expected response value
        role_with_llm: Test role with LLM capabilities
    """
    with patch.object(llm, "ROUTER", mock_router):
        assert (await role_with_llm.aask(model="openai/gpt-3.5-turbo", question="Hi")) == ret_value


@pytest.mark.parametrize(
    ("ret_value", "question_input", "system_input"),
    [
        ("Hi", "Hello?", None),
        ("Hello", ["Hi", "Hey"], None),
        ("Response1", "Question", "System Message"),
        ("Response2", ["Q1", "Q2"], ["Sys1", "Sys2"]),
        ("Response3", ["Q1", "Q2"], "Shared System Message"),
        ("Response4", "Single Question", ["Sys1", "Sys2"]),
    ],
)
@pytest.mark.asyncio
async def test_aask_branches(
    mock_router: Router,
    ret_value: str,
    question_input: str | list[str],
    system_input: Optional[str | list[str]],
    role_with_llm: LLMRole,
) -> None:
    """Test different input branches of aask functionality.

    Validates correct handling of various input combinations including:
    - Single vs multiple questions
    - Single vs multiple system messages
    - Mixed input types

    Args:
        mock_router: Preconfigured mock router fixture
        ret_value: Expected response value
        question_input: Input question(s) to test
        system_input: System message(s) to use
        role_with_llm: Test role with LLM capabilities
    """
    with patch.object(llm, "ROUTER", mock_router):
        result = await role_with_llm.aask(
            question=question_input,
            system_message=system_input,
        )

        if isinstance(question_input, list):
            assert isinstance(result, list)
            assert all(isinstance(item, str) for item in result)
            assert len(result) == len(question_input)
            assert all(ret_value == r for r in result)
        elif isinstance(system_input, list):
            assert isinstance(result, list)
            assert all(isinstance(item, str) for item in result)
            assert len(result) == len(system_input)
            assert all(ret_value == r for r in result)
        else:
            assert isinstance(result, str)
            assert result == ret_value
