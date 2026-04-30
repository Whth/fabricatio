"""Module mock_router.

This module provides utility functions for creating asynchronous mock objects that simulate
the behavior of a LiteLLM Router. It is primarily intended for use in testing scenarios where
actual network requests to language models are not desirable or necessary.
"""

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Literal, Optional
from unittest.mock import AsyncMock

import orjson
from fabricatio_core.rust import Router
from fabricatio_core.utils import ok
from pydantic import BaseModel, JsonValue

from fabricatio_mock.utils import code_block, generic_block


def return_string(*value: str, default: Optional[str] = None) -> Router:
    """Creates and returns an asynchronous mock object for a Router instance that simulates a completion response using the provided string values.

    The returned AsyncMock can be used in testing scenarios to mimic the behavior of a real Router without making actual network requests. The mock will return values sequentially from the provided *value* arguments, falling back to the default value when these are exhausted.

    Args:
        *value (str): Variable length list of string responses to be used as mock outputs.
        default (Optional[str]): Default value to use when no more values are available. If not provided, last value is used.

    Returns:
        Router: A mock Router object with a configured *acompletion* method.
    """
    if not value:
        raise ValueError("At least one value must be provided.")
    mock = AsyncMock(spec=Router)
    gen = iter(value)
    default = ok(default or value[-1])

    @wraps(Router.completion)
    async def _acomp_wrapper(*_: Any, **__: Any) -> str:
        return next(gen, default)

    mock.completion = _acomp_wrapper
    return mock


def return_generic_string(*strings: str, lang: str = "string", default: Optional[str] = None) -> Router:
    """Wraps given strings into generic code blocks, returning an AsyncMock simulating a Router.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *strings (str): Input strings to be wrapped into code blocks
        lang (str): Programming language identifier
        default (Optional[str]): Default value when no more strings available

    Returns:
        Router: Mock Router returning formatted code blocks
    """
    if not strings:
        raise ValueError("At least one string must be provided.")
    processed = [generic_block(s, lang) for s in strings]
    return return_string(*processed, default=default)


def return_code_string(*codes: str, lang: str, default: Optional[str] = None) -> Router:
    """Generates code-block-formatted strings, returning an AsyncMock simulating a Router.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *codes (str): Source code/content to format
        lang (str): Programming language identifier
        default (Optional[str]): Default value when no more codes available

    Returns:
        Router: Mock Router returning formatted code strings
    """
    if not codes:
        raise ValueError("At least one code must be provided.")
    processed = [code_block(c, lang) for c in codes]
    return return_string(*processed, default=default)


def return_python_string(*codes: str, default: Optional[str] = None) -> Router:
    """Returns AsyncMock simulating Router that responds with Python code blocks.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *codes (str): Python code to include in responses
        default (Optional[str]): Default value when no more codes available

    Returns:
        Router: Mock Router returning Python-formatted responses
    """
    return return_code_string(*codes, lang="python", default=default)


def return_json_string(*jsons: str, default: Optional[str] = None) -> Router:
    """Returns AsyncMock simulating Router that responds with JSON code blocks.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *jsons (str): JSON content to include in responses
        default (Optional[str]): Default value when no more JSONs available

    Returns:
        Router: Mock Router returning JSON-formatted responses
    """
    return return_code_string(*jsons, lang="json", default=default)


def return_json_obj_string(*objs: JsonValue, default: Optional[str] = None) -> Router:
    """Converts arrays to JSON array strings, returning AsyncMock simulating Router.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *objs (JsonValue): Array of JSON values
        default (Optional[str]): Default value when no more arrays available

    Returns:
        Router: Mock Router returning JSON array strings
    """
    if not objs:
        raise ValueError("At least one array must be provided.")
    processed = [orjson.dumps(obj, option=orjson.OPT_INDENT_2).decode() for obj in objs]
    return return_json_string(*processed, default=default)


def return_model_json_string(*models: BaseModel, default: Optional[str] = None) -> Router:
    """Serializes models to JSON strings, returning AsyncMock simulating Router.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *models (BaseModel): Pydantic models to serialize
        default (Optional[str]): Default value when no more models available

    Returns:
        Router: Mock Router returning model JSON representations
    """
    if not models:
        raise ValueError("At least one model must be provided.")
    processed = [orjson.dumps(model.model_dump(by_alias=True), option=orjson.OPT_INDENT_2).decode() for model in models]
    return return_json_string(*processed, default=default)


@dataclass
class Value[M: BaseModel | str]:
    """Value class for mocking responses."""

    source: M
    """The source data to be used for mocking. Can be a BaseModel instance"""
    type: Literal["model", "json", "python", "raw", "generic"]
    """Specifies the type of the source data, which determines how the data will be processed when converted to a string representation."""

    convertor: Optional[Callable[[M], str]] = None

    def to_string(self) -> str:
        """Converts the source data to a string representation based on its type.

        Returns:
            str: The processed string representation of the source data.

        Raises:
            ValueError: If the type is invalid or unsupported.
        """
        if self.type == "model" and isinstance(self.source, BaseModel):
            return orjson.dumps(self.source.model_dump(by_alias=True), option=orjson.OPT_INDENT_2).decode()
        if self.type == "json":
            return orjson.dumps(self.source, option=orjson.OPT_INDENT_2).decode()
        if self.type == "python" and isinstance(self.source, str):
            return code_block(self.source, "python")
        if self.type == "generic" and isinstance(self.source, str):
            return generic_block(self.source, "string")
        if self.convertor:
            return self.convertor(self.source)
        raise ValueError(f"Invalid type: {self.type}")


def return_mixed_string(*values: Value, default: Optional[str] = None) -> Router:
    """Generates a mock Router that returns a string based on the provided values.

    Supports multiple values - will return them sequentially. If no values remain, returns default.

    Args:
        *values (Value): Values to be processed and returned as strings
        default (Optional[str]): Default value when no more values available

    Returns:
        Router: A mock Router that returns a string based on the provided values
    """
    return return_string(*[value.to_string() for value in values], default=default)


def _pad_responses(*value: str, default: Optional[str] = None) -> list[str]:
    """Build a padded response list for DummyModel.

    DummyModel errors when its queue is exhausted. Pad with extra copies of the
    default value to cover retries (max_validations) and batch calls.
    """
    if not value:
        raise ValueError("At least one value must be provided.")
    default_val = ok(default or value[-1])
    return list(value) + [default_val] * 10


def return_router_usage(*value: str, default: Optional[str] = None) -> list[str]:
    """Build padded response strings for install_router_usage.

    Like return_string but returns a list of pre-formatted strings
    for use with install_router_usage(). DummyModel handles the LIFO→FIFO
    reversal inside setup_dummy_responses.

    Args:
        *value (str): Response strings to return sequentially.
        default (Optional[str]): Default value when responses exhausted.

    Returns:
        list[str]: Padded response strings ready for install_router_usage.
    """
    return _pad_responses(*value, default=default)


def return_generic_router_usage(*strings: str, lang: str = "string", default: Optional[str] = None) -> list[str]:
    """Build generic-block-formatted responses for install_router_usage.

    Args:
        *strings (str): Content strings to wrap in generic blocks.
        lang (str): Block type identifier.
        default (Optional[str]): Default value when exhausted.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    if not strings:
        raise ValueError("At least one string must be provided.")
    processed = [generic_block(s, lang) for s in strings]
    return _pad_responses(*processed, default=default)


def return_code_router_usage(*codes: str, lang: str, default: Optional[str] = None) -> list[str]:
    """Build code-block-formatted responses for install_router_usage.

    Args:
        *codes (str): Source code strings to wrap in code blocks.
        lang (str): Programming language identifier.
        default (Optional[str]): Default value when exhausted.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    if not codes:
        raise ValueError("At least one code must be provided.")
    processed = [code_block(c, lang) for c in codes]
    return _pad_responses(*processed, default=default)


def return_python_router_usage(*codes: str, default: Optional[str] = None) -> list[str]:
    """Build Python-code-block responses for install_router_usage.

    Args:
        *codes (str): Python code strings.
        default (Optional[str]): Default value when exhausted.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    return return_code_router_usage(*codes, lang="python", default=default)


def return_json_router_usage(*jsons: str, default: Optional[str] = None) -> list[str]:
    """Build JSON-code-block responses for install_router_usage.

    Args:
        *jsons (str): JSON content strings.
        default (Optional[str]): Default value when exhausted.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    return return_code_router_usage(*jsons, lang="json", default=default)


def return_json_obj_router_usage(*objs: JsonValue, default: Optional[str] = None) -> list[str]:
    """Build serialized-JSON responses for install_router_usage.

    Args:
        *objs (JsonValue): Objects to serialize as JSON.
        default (Optional[str]): Default value when exhausted.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    if not objs:
        raise ValueError("At least one array must be provided.")
    processed = [orjson.dumps(obj, option=orjson.OPT_INDENT_2).decode() for obj in objs]
    return return_json_router_usage(*processed, default=default)


def return_model_json_router_usage(*models: BaseModel, default: Optional[str] = None) -> list[str]:
    """Build serialized-Pydantic-model responses for install_router_usage.

    Args:
        *models (BaseModel): Pydantic models to serialize.
        default (Optional[str]): Default value when exhausted.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    if not models:
        raise ValueError("At least one model must be provided.")
    processed = [orjson.dumps(model.model_dump(by_alias=True), option=orjson.OPT_INDENT_2).decode() for model in models]
    return return_json_router_usage(*processed, default=default)


def return_mixed_router_usage(*values: Value, default: Optional[str] = None) -> list[str]:
    """Build mixed-type responses for install_router_usage.

    Args:
        *values (Value): Values to process and return as strings.
        default (Optional[str]): Default value when exhausted.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    return _pad_responses(*[value.to_string() for value in values], default=default)
