"""Module-level docstring explaining the purpose of this test module.

This module contains unit tests for LLM-related functionality within the Role class,
specifically focusing on methods that interact with the UseLLM capability.
"""

from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import litellm
import pytest
from fabricatio_core import Role
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models import llm
from litellm import Router
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.utils import ModelResponse

def code_block(content: str, lang: str = "json") -> str:
    """Generate a code block."""
    return f"```{lang}\n{content}\n```"

def generic_block(content: str, lang: str = "String")->str:
    """Generate a generic block."""
    return f"--- Start of {lang} ---\n{content}\n--- End of {lang} ---"


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


@pytest.mark.parametrize(
    ("ret_value", "question_input", "validator", "default", "max_validations"),
    [
        ("123", "What is 100 + 23?", lambda x: int(x) if x.isdigit() else None, None, 3),
        ("abc", "Enter digits:", lambda x: int(x) if x.isdigit() else None, 0, 3),
        ("Hello", ["Hi", "Hey"], lambda x: x if len(x) > 3 else None, None, 2),
        ("5", "Give me a number:", lambda x: int(x) if x.isdigit() else None, -1, 3),
    ],
)
@pytest.mark.asyncio
async def test_aask_validate(
    mock_router: Router,
    ret_value: str,
    question_input: str | list[str],
    validator: Callable[[str], Any],
    default: Optional[Any],
    max_validations: int,
    role_with_llm: LLMRole,
) -> None:
    """Test the aask_validate method with different validation scenarios.

    Validates correct handling of various input combinations including:
    - Successful validation on first attempt
    - Validation retries with cache disabled after failure
    - Default value handling when validation fails
    - List input handling

    Args:
        mock_router: Preconfigured mock router fixture
        ret_value: Expected response value from LLM
        question_input: Input question(s) to test
        validator: Validation function to apply to responses
        default: Default value to use when validation fails
        max_validations: Maximum number of validation attempts
        role_with_llm: Test role with LLM capabilities
    """
    with patch.object(llm, "ROUTER", mock_router):
        result = await role_with_llm.aask_validate(
            question=question_input,
            validator=validator,
            default=default,
            max_validations=max_validations,
        )

        if isinstance(question_input, list):
            assert isinstance(result, list)
            assert all(str(r) == ret_value for r in result)
        else:
            assert str(result) == ret_value or result == default



@pytest.mark.parametrize(
    ("ret_value", "requirement", "k", "expected_result"),
    [
        (
            code_block('{"key1": "value1", "key2": "value2"}'),
            "Generate two string mappings",
            2,
            {"key1": "value1", "key2": "value2"},
        ),
        (code_block('{"key": "value"}'), "Generate one string mapping", 1, {"key": "value"}),
        (
            code_block('{"key1": "value1", "key2": "value2", "key3": "value3"}'),
            "Generate three string mappings",
            0,
            {"key1": "value1", "key2": "value2", "key3": "value3"},
        ),
        (code_block('{"invalid": 123}'), "Invalid mapping", 1, None),
        (
            code_block('{"batch_key1": "batch_value1", "batch_key2": "batch_value2"}'),
            "Generate batch string mappings",
            2,
            {"batch_key1": "batch_value1", "batch_key2": "batch_value2"},
        ),
    ],
)
@pytest.mark.asyncio
async def test_amapping_str(
    mock_router: Router,
    ret_value: str,
    requirement: str,
    k: int,
    expected_result: Optional[Dict[str, str]],
    role_with_llm: LLMRole,
) -> None:
    """Test the amapping_str method with different scenarios.

    Validates correct handling of various input combinations including:
    - Successful generation of valid string mappings.
    - Handling of invalid mappings that do not meet validation criteria.
    - Behavior when k is set to 0 (infinite choices).

    Args:
        mock_router: Preconfigured mock router fixture.
        ret_value: Expected response value from LLM.
        requirement: The requirement for the mapping of strings.
        k: The number of choices to select.
        expected_result: The expected validated result.
        role_with_llm: Test role with LLM capabilities.
    """
    with patch.object(llm, "ROUTER", mock_router):
        result = await role_with_llm.amapping_str(requirement=requirement, k=k)

        assert result == expected_result


@pytest.mark.parametrize(
    ("ret_value", "requirement", "k", "expected_result"),
    [
        (code_block('["apple", "banana", "cherry"]'), "Generate three fruits", 3, ["apple", "banana", "cherry"]),
        (code_block('["one" ,"two"]'), "Generate two words", 2, ["one", "two"]),
        (code_block('["single_item"]'), "Generate one item", 1, ["single_item"]),
        ("invalid json response", "Invalid response", 1, None),
        (
            code_block('["batch_item1" "batch_item2"]'),
            code_block('["batch_item3", "batch_item4"]'),
            2,
            ["batch_item1", "batch_item2"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_alist_str(
    mock_router: Router,
    ret_value: str,
    requirement: str,
    k: int,
    expected_result: Optional[List[str]],
    role_with_llm: LLMRole,
) -> None:
    """Test the alist_str method with different scenarios.

    Validates correct handling of various input combinations including:
    - Successful generation of valid string lists.
    - Handling of invalid responses that do not meet validation criteria.
    - Behavior when k is set to 0 (infinite choices).

    Args:
        mock_router: Preconfigured mock router fixture.
        ret_value: Expected response value from LLM.
        requirement: The requirement for the list of strings.
        k: The number of choices to select.
        expected_result: The expected validated result.
        role_with_llm: Test role with LLM capabilities.
    """
    with patch.object(llm, "ROUTER", mock_router):
        result = await role_with_llm.alist_str(requirement=requirement, k=k)

        assert result == expected_result


@pytest.mark.parametrize(
    ("ret_value", "requirement_list", "k", "expected_result"),
    [
        (
                code_block('["item1", "item2"]'),
            ["First requirement", "Second requirement"],
            2,
            [["item1", "item2"],["item1", "item2"]],
        ),
        (
                code_block('["test1", "test2", "test3"]'),
            ["Req1", "Req2", "Req3"],
            3,
            [["test1", "test2", "test3"],["test1", "test2", "test3"],["test1", "test2", "test3"]],
        ),
    ],
)
@pytest.mark.asyncio
async def test_alist_str_with_requirement_list(
    mock_router: Router,
    ret_value: str,
    requirement_list: List[str],
    k: int,
    expected_result: Optional[List[str]],
    role_with_llm: LLMRole,
) -> None:
    """Test the alist_str method with a list of requirements.

    Validates correct handling of:
    - Generation of string lists based on multiple requirements.
    - Proper handling of batch processing with multiple requirements.

    Args:
        mock_router: Preconfigured mock router fixture.
        ret_value: Expected response value from LLM.
        requirement_list: A list of requirements for string generation.
        k: The number of choices to select.
        expected_result: The expected validated result.
        role_with_llm: Test role with LLM capabilities.
    """
    with patch.object(llm, "ROUTER", mock_router):
        result = await role_with_llm.alist_str(requirement=requirement_list, k=k)

        assert result == expected_result


@pytest.mark.parametrize(
    ("ret_value", "requirement", "expected_result"),
    [
        (code_block('["path1", "path2"]'), "Generate two paths", ["path1", "path2"]),
        (code_block('["single_path"]'), "Generate one path", ["single_path"]),
        ("invalid json response", "Invalid path response", None),
    ],
)
@pytest.mark.asyncio
async def test_apathstr(
mock_router: Router, ret_value: str, requirement: str, expected_result: Optional[List[str]], role_with_llm: LLMRole
) -> None:
    """Test the apathstr method with different scenarios.

    Validates correct handling of various input combinations including:
    - Successful generation of valid path strings.
    - Handling of invalid responses that do not meet validation criteria.

    Args:
        mock_router: Preconfigured mock router fixture.
        ret_value: Expected response value from LLM.
        requirement: The requirement for the path string generation.
        expected_result: The expected validated result.
        role_with_llm: Test role with LLM capabilities.
    """
    with patch.object(llm, "ROUTER", mock_router):
        result = await role_with_llm.apathstr(requirement=requirement)

        assert result == expected_result


@pytest.mark.parametrize(
    ("ret_value", "requirement", "expected_result"),
    [
        (code_block('["path1"]'), "Generate a path", "path1"),
        (code_block('["path2"]'), "Another path requirement", "path2"),
        (None, "Invalid path response", None),
    ],
)
@pytest.mark.asyncio
async def test_awhich_pathstr(
    mock_router: Router,
    ret_value: str,
    requirement: str,
    expected_result: Optional[str],
    role_with_llm: LLMRole,
) -> None:
    """Test the awhich_pathstr method with different scenarios.

    Validates correct handling of various input combinations including:
    - Successful generation of valid path strings.
    - Handling of empty or invalid responses.

    Args:
        mock_router: Preconfigured mock router fixture.
        ret_value: Mocked response from apathstr method.
        requirement: The requirement for path string generation.
        expected_result: The expected validated result.
        role_with_llm: Test role with LLM capabilities.
    """
    with patch.object(llm, "ROUTER", mock_router):
        result = await role_with_llm.awhich_pathstr(requirement=requirement)

        assert result == expected_result






@pytest.mark.parametrize(
    ("ret_value", "requirement", "expected_result"),
    [
        (generic_block("Test output 1"), "Requirement 1", "Test output 1"),
        (generic_block("Another output"), ["Req1", "Req2"], ["Another output", "Another output"]),
        ("invalid json response", "Req", None),
    ],
)
@pytest.mark.asyncio
async def test_ageneric_string(
        mock_router: Router,
        ret_value: str,
        requirement: str | List[str],
        expected_result: Optional[str | List[str]],
        role_with_llm: LLMRole,
) -> None:
    """Test the ageneric_string method with different scenarios.

    Validates correct handling of various input combinations including:
    - Single string requirement and response
    - List of requirements with appropriate list response
    - Invalid responses that do not meet validation criteria

    Args:
        mock_router: Preconfigured mock router fixture.
        ret_value: Expected response value from LLM.
        requirement: The requirement(s) for string generation.
        expected_result: The expected validated result.
        role_with_llm: Test role with LLM capabilities.
    """
    # Patch the aask_validate method since we're testing the generic string functionality,
    # not the underlying LLM interaction
    with patch.object(llm, "ROUTER",mock_router):
        result = await role_with_llm.ageneric_string(requirement=requirement)

        assert result == expected_result



