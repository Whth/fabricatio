"""Module mock_router.

This module provides utility functions for creating asynchronous mock objects that simulate
the behavior of a LiteLLM Router. It is primarily intended for use in testing scenarios where
actual network requests to language models are not desirable or necessary.
"""

from dataclasses import dataclass
from typing import Callable, Literal, Optional

import orjson
from fabricatio_core.utils import ok
from pydantic import BaseModel, JsonValue

from fabricatio_mock.utils import code_block, generic_block


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


def pad_responses(*value: str, default: Optional[str] = None, padding: int = 10) -> list[str]:
    """Build a padded response list for DummyModel.

    DummyModel errors when its queue is exhausted. Pad with extra copies of the
    default value to cover retries (max_validations) and batch calls.

    Args:
        *value (str): Response strings.
        default (Optional[str]): Value used for padding. Defaults to the last value.
        padding (int): Number of extra copies appended. Defaults to 10.

    Returns:
        list[str]: value followed by `padding` copies of the default.
    """
    if not value:
        raise ValueError("At least one value must be provided.")
    default_val = ok(default or value[-1])
    return list(value) + [default_val] * padding


def return_router_usage(*value: str, default: Optional[str] = None, padding: int = 10) -> list[str]:
    """Build padded response strings for install_router_usage.

    Like return_string but returns a list of pre-formatted strings
    for use with install_router_usage(). DummyModel handles the LIFO→FIFO
    reversal inside setup_dummy_responses.

    Args:
        *value (str): Response strings to return sequentially.
        default (Optional[str]): Default value when responses exhausted.
        padding (int): Number of extra copies appended. Defaults to 10.

    Returns:
        list[str]: Padded response strings ready for install_router_usage.
    """
    return pad_responses(*value, default=default, padding=padding)


def return_generic_router_usage(
    *strings: str, lang: str = "string", default: Optional[str] = None, padding: int = 10
) -> list[str]:
    """Build generic-block-formatted responses for install_router_usage.

    Args:
        *strings (str): Content strings to wrap in generic blocks.
        lang (str): Block type identifier.
        default (Optional[str]): Default value when exhausted.
        padding (int): Number of extra copies appended. Defaults to 10.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    if not strings:
        raise ValueError("At least one string must be provided.")
    processed = [generic_block(s, lang) for s in strings]
    return pad_responses(*processed, default=default, padding=padding)


def return_code_router_usage(*codes: str, lang: str, default: Optional[str] = None, padding: int = 10) -> list[str]:
    """Build code-block-formatted responses for install_router_usage.

    Args:
        *codes (str): Source code strings to wrap in code blocks.
        lang (str): Programming language identifier.
        default (Optional[str]): Default value when exhausted.
        padding (int): Number of extra copies appended. Defaults to 10.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    if not codes:
        raise ValueError("At least one code must be provided.")
    processed = [code_block(c, lang) for c in codes]
    return pad_responses(*processed, default=default, padding=padding)


def return_python_router_usage(*codes: str, default: Optional[str] = None, padding: int = 10) -> list[str]:
    """Build Python-code-block responses for install_router_usage.

    Args:
        *codes (str): Python code strings.
        default (Optional[str]): Default value when exhausted.
        padding (int): Number of extra copies appended. Defaults to 10.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    return return_code_router_usage(*codes, lang="python", default=default, padding=padding)


def return_json_router_usage(*jsons: str, default: Optional[str] = None, padding: int = 10) -> list[str]:
    """Build JSON-code-block responses for install_router_usage.

    Args:
        *jsons (str): JSON content strings.
        default (Optional[str]): Default value when exhausted.
        padding (int): Number of extra copies appended. Defaults to 10.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    return return_code_router_usage(*jsons, lang="json", default=default, padding=padding)


def return_json_obj_router_usage(*objs: JsonValue, default: Optional[str] = None, padding: int = 10) -> list[str]:
    """Build serialized-JSON responses for install_router_usage.

    Args:
        *objs (JsonValue): Objects to serialize as JSON.
        default (Optional[str]): Default value when exhausted.
        padding (int): Number of extra copies appended. Defaults to 10.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    if not objs:
        raise ValueError("At least one array must be provided.")
    processed = [orjson.dumps(obj, option=orjson.OPT_INDENT_2).decode() for obj in objs]
    return return_json_router_usage(*processed, default=default, padding=padding)


def return_model_json_router_usage(*models: BaseModel, default: Optional[str] = None, padding: int = 10) -> list[str]:
    """Build serialized-Pydantic-model responses for install_router_usage.

    Args:
        *models (BaseModel): Pydantic models to serialize.
        default (Optional[str]): Default value when exhausted.
        padding (int): Number of extra copies appended. Defaults to 10.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    if not models:
        raise ValueError("At least one model must be provided.")
    processed = [orjson.dumps(model.model_dump(by_alias=True), option=orjson.OPT_INDENT_2).decode() for model in models]
    return return_json_router_usage(*processed, default=default, padding=padding)


def return_mixed_router_usage(*values: Value, default: Optional[str] = None, padding: int = 10) -> list[str]:
    """Build mixed-type responses for install_router_usage.

    Args:
        *values (Value): Values to process and return as strings.
        default (Optional[str]): Default value when exhausted.
        padding (int): Number of extra copies appended. Defaults to 10.

    Returns:
        list[str]: Formatted and padded response strings.
    """
    return pad_responses(*[value.to_string() for value in values], default=default, padding=padding)


def pad_embeddings(*embeddings: list[float], default: Optional[list[float]] = None, padding: int = 10) -> list[list[float]]:
    """Build a padded embeddings list for DummyModel.

    DummyModel errors when its queue is exhausted. Pad with extra copies of the
    default value to cover retries and batch calls.

    Args:
        *embeddings: Embedding vectors.
        default: Value used for padding. Defaults to the last embedding.
        padding: Number of extra copies appended. Defaults to 10.

    Returns:
        list[list[float]]: embeddings followed by padding copies of default.
    """
    if not embeddings:
        raise ValueError("At least one embedding must be provided.")
    default_val = ok(default or embeddings[-1])
    return list(embeddings) + [default_val] * padding


def pad_rankings(*rankings: tuple[int, float], default: Optional[tuple[int, float]] = None, padding: int = 10) -> list[tuple[int, float]]:
    """Build a padded rankings list for DummyModel.

    DummyModel errors when its queue is exhausted. Pad with extra copies of the
    default value to cover retries and batch calls.

    Args:
        *rankings: Ranking tuples of (index, score).
        default: Value used for padding. Defaults to the last ranking.
        padding: Number of extra copies appended. Defaults to 10.

    Returns:
        list[tuple[int, float]]: rankings followed by padding copies of default.
    """
    if not rankings:
        raise ValueError("At least one ranking must be provided.")
    default_val = ok(default or rankings[-1])
    return list(rankings) + [default_val] * padding
