"""Module mock_router.

This module provides utility functions for creating asynchronous mock objects that simulate
the behavior of a LiteLLM Router. It is primarily intended for use in testing scenarios where
actual network requests to language models are not desirable or necessary.
"""

from functools import wraps
from typing import Any
from unittest.mock import AsyncMock

import litellm
import orjson
from litellm import Router
from litellm.caching.caching_handler import CustomStreamWrapper
from litellm.types.utils import ModelResponse
from pydantic import BaseModel, JsonValue

from fabricatio_mock.utils import code_block, generic_block


def return_string(value: str) -> AsyncMock:
    """Creates and returns an asynchronous mock object for a Router instance that simulates a completion response with the provided string value.

    The returned AsyncMock can be used in testing scenarios to mimic the behavior of a real Router without making actual network requests.

    Args:
        value (str): The string value to be used as the mock response.

    Returns:
        AsyncMock: A mock Router object with a configured 'acompletion' method.
    """
    mock = AsyncMock(spec=Router)

    @wraps(Router.acompletion)
    async def _acomp_wrapper(*args: Any, **kwargs: Any) -> ModelResponse | CustomStreamWrapper:
        return litellm.mock_completion(*args, mock_response=value, **kwargs)

    mock.acompletion = _acomp_wrapper

    return mock


def return_generic_string(string: str, lang: str = "string") -> AsyncMock:
    """Wraps the given string into a generic code block using the specified language, then returns an AsyncMock object simulating a Router with this formatted response.

    Args:
        string (str): The input string to be wrapped into a code block.
        lang (str): The programming language identifier for the code block.

    Returns:
        AsyncMock: A mock Router object configured to return the formatted code block.
    """
    return return_string(generic_block(string, lang))


def return_code_string(code: str, lang: str) -> AsyncMock:
    """Generates a code-block-formatted string from the provided code and language, then returns an AsyncMock simulating a Router with this response.

    Args:
        code (str): The source code or content to be formatted as a code block.
        lang (str): The programming language identifier for syntax highlighting.

    Returns:
        AsyncMock: A mock Router object configured to return the formatted code string.
    """
    return return_string(code_block(code, lang))


def return_python_string(code: str) -> AsyncMock:
    """Returns an AsyncMock simulating a Router that responds with a Python code block.

    Args:
        code (str): The Python code to be included in the mock response.

    Returns:
        AsyncMock: A mock Router object configured to return the Python-formatted response.
    """
    return return_code_string(code, "python")


def return_json_string(json: str) -> AsyncMock:
    """Returns an AsyncMock simulating a Router that responds with a JSON code block.

    Args:
        json (str): The JSON content to be included in the mock response.

    Returns:
        AsyncMock: A mock Router object configured to return the JSON-formatted response.
    """
    return return_code_string(json, "json")


def return_json_array_string(array: list[JsonValue]) -> AsyncMock:
    """Converts the provided list into an indented JSON array string and returns an AsyncMock simulating a Router with this response.

    Args:
        array (list[JsonValue]): The list of JSON-compatible values to be serialized.

    Returns:
        AsyncMock: A mock Router object configured to return the indented JSON array string.
    """
    return return_json_string(orjson.dumps(array, option=orjson.OPT_INDENT_2).decode())


def return_model_json_string(model: BaseModel) -> AsyncMock:
    """Serializes the provided Pydantic model into a JSON string and returns an AsyncMock simulating a Router with this response.

    Args:
        model (BaseModel): The Pydantic model to be serialized and included in the response.

    Returns:
        AsyncMock: A mock Router object configured to return the model's JSON representation.
    """
    return return_json_string(orjson.dumps(model.model_dump(), option=orjson.OPT_INDENT_2).decode())
