"""Module mock_router.

This module provides utility functions for creating asynchronous mock objects that simulate
the behavior of a LiteLLM Router. It is primarily intended for use in testing scenarios where
actual network requests to language models are not desirable or necessary.
"""

from functools import wraps
from typing import Any, Optional
from unittest.mock import AsyncMock

import litellm
import orjson
from fabricatio_core.utils import ok
from litellm import Router
from litellm.caching.caching_handler import CustomStreamWrapper
from litellm.types.utils import ModelResponse
from pydantic import BaseModel, JsonValue

from fabricatio_mock.utils import code_block, generic_block


def return_string(*value: str, default: Optional[str] = None) -> AsyncMock:
    """Creates and returns an asynchronous mock object for a Router instance that simulates a completion response using the provided string values.

    The returned AsyncMock can be used in testing scenarios to mimic the behavior of a real Router without making actual network requests. The mock will return values sequentially from the provided *value* arguments, falling back to the default value when these are exhausted.

    Args:
        *value (str): Variable length list of string responses to be used as mock outputs.
        default (Optional[str]): Default value to use when no more values are available. If not provided, last value is used.

    Returns:
        AsyncMock: A mock Router object with a configured *acompletion* method.
    """
    if not value:
        raise ValueError("At least one value must be provided.")
    mock = AsyncMock(spec=Router)
    gen = iter(value)
    default = ok(default or value[-1])

    @wraps(Router.acompletion)
    async def _acomp_wrapper(*args: Any, **kwargs: Any) -> ModelResponse | CustomStreamWrapper:
        cur_value = next(gen, default)
        return litellm.mock_completion(*args, mock_response=cur_value, **kwargs)

    mock.acompletion = _acomp_wrapper
    return mock


def return_generic_string(*strings: str, lang: str = "string", default: Optional[str] = None) -> AsyncMock:
    """Wraps given strings into generic code blocks, returning an AsyncMock simulating a Router.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *strings (str): Input strings to be wrapped into code blocks
        lang (str): Programming language identifier
        default (Optional[str]): Default value when no more strings available

    Returns:
        AsyncMock: Mock Router returning formatted code blocks
    """
    if not strings:
        raise ValueError("At least one string must be provided.")
    processed = [generic_block(s, lang) for s in strings]
    return return_string(*processed, default=default)


def return_code_string(*codes: str, lang: str, default: Optional[str] = None) -> AsyncMock:
    """Generates code-block-formatted strings, returning an AsyncMock simulating a Router.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *codes (str): Source code/content to format
        lang (str): Programming language identifier
        default (Optional[str]): Default value when no more codes available

    Returns:
        AsyncMock: Mock Router returning formatted code strings
    """
    if not codes:
        raise ValueError("At least one code must be provided.")
    processed = [code_block(c, lang) for c in codes]
    return return_string(*processed, default=default)


def return_python_string(*codes: str, default: Optional[str] = None) -> AsyncMock:
    """Returns AsyncMock simulating Router that responds with Python code blocks.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *codes (str): Python code to include in responses
        default (Optional[str]): Default value when no more codes available

    Returns:
        AsyncMock: Mock Router returning Python-formatted responses
    """
    return return_code_string(*codes, lang="python", default=default)


def return_json_string(*jsons: str, default: Optional[str] = None) -> AsyncMock:
    """Returns AsyncMock simulating Router that responds with JSON code blocks.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *jsons (str): JSON content to include in responses
        default (Optional[str]): Default value when no more JSONs available

    Returns:
        AsyncMock: Mock Router returning JSON-formatted responses
    """
    return return_code_string(*jsons, lang="json", default=default)


def return_json_obj_string(*objs: JsonValue, default: Optional[str] = None) -> AsyncMock:
    """Converts arrays to JSON array strings, returning AsyncMock simulating Router.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *objs (JsonValue): Array of JSON values
        default (Optional[str]): Default value when no more arrays available

    Returns:
        AsyncMock: Mock Router returning JSON array strings
    """
    if not objs:
        raise ValueError("At least one array must be provided.")
    processed = [orjson.dumps(obj, option=orjson.OPT_INDENT_2).decode() for obj in objs]
    return return_json_string(*processed, default=default)


def return_model_json_string(*models: BaseModel, default: Optional[str] = None) -> AsyncMock:
    """Serializes models to JSON strings, returning AsyncMock simulating Router.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *models (BaseModel): Pydantic models to serialize
        default (Optional[str]): Default value when no more models available

    Returns:
        AsyncMock: Mock Router returning model JSON representations
    """
    if not models:
        raise ValueError("At least one model must be provided.")
    processed = [orjson.dumps(model.model_dump(by_alias=True), option=orjson.OPT_INDENT_2).decode() for model in models]
    return return_json_string(*processed, default=default)
