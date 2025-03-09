"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import Any, List, NotRequired, Set, TypedDict

from litellm.caching.caching import CacheMode
from litellm.types.caching import CachingSupportedCallTypes
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt


class CollectionSimpleConfigKwargs(TypedDict):
    """A type representing the configuration for a collection."""

    dimension: NotRequired[int]
    timeout: NotRequired[float]


class FetchKwargs(TypedDict):
    """A type representing the keyword arguments for the fetch method."""

    collection_name: NotRequired[str]
    similarity_threshold: NotRequired[float]
    result_per_query: NotRequired[int]


class EmbeddingKwargs(TypedDict):
    """A type representing the keyword arguments for the embedding method."""

    model: NotRequired[str]
    dimensions: NotRequired[int]
    timeout: NotRequired[PositiveInt]
    caching: NotRequired[bool]


class LLMKwargs(TypedDict):
    """A type representing the keyword arguments for the LLM (Large Language Model) usage."""

    model: NotRequired[str]
    temperature: NotRequired[NonNegativeFloat]
    stop: NotRequired[str | List[str]]
    top_p: NotRequired[NonNegativeFloat]
    max_tokens: NotRequired[PositiveInt]
    stream: NotRequired[bool]
    timeout: NotRequired[PositiveInt]
    max_retries: NotRequired[PositiveInt]


class ValidateKwargs(LLMKwargs):
    """A type representing the keyword arguments for the validate method."""

    max_validations: NotRequired[PositiveInt]


class GenerateKwargs(ValidateKwargs):
    """A type representing the keyword arguments for the generate method."""

    system_message: NotRequired[str]


class ReviewKwargs(GenerateKwargs):
    """A type representing the keyword arguments for the review method."""

    topic: str
    criteria: NotRequired[Set[str]]


class ChooseKwargs(GenerateKwargs):
    """A type representing the keyword arguments for the choose method."""

    k: NotRequired[NonNegativeInt]


class CacheKwargs(TypedDict, total=False):
    """A type representing the keyword arguments for the cache method."""

    mode: NotRequired[CacheMode]  # when default_on cache is always on, when default_off cache is opt in
    host: NotRequired[str]
    port: NotRequired[str]
    password: NotRequired[str]
    namespace: NotRequired[str]
    ttl: NotRequired[float]
    default_in_memory_ttl: NotRequired[float]
    default_in_redis_ttl: NotRequired[float]
    similarity_threshold: NotRequired[float]
    supported_call_types: NotRequired[List[CachingSupportedCallTypes]]
    # s3 Bucket, boto3 configuration
    s3_bucket_name: NotRequired[str]
    s3_region_name: NotRequired[str]
    s3_api_version: NotRequired[str]
    s3_use_ssl: NotRequired[bool]
    s3_verify: NotRequired[bool | str]
    s3_endpoint_url: NotRequired[str]
    s3_aws_access_key_id: NotRequired[str]
    s3_aws_secret_access_key: NotRequired[str]
    s3_aws_session_token: NotRequired[str]
    s3_config: NotRequired[Any]
    s3_path: NotRequired[str]
    redis_semantic_cache_use_async: bool
    redis_semantic_cache_embedding_model: str
    redis_flush_size: NotRequired[int]
    redis_startup_nodes: NotRequired[List]
    disk_cache_dir: Any
    qdrant_api_base: NotRequired[str]
    qdrant_api_key: NotRequired[str]
    qdrant_collection_name: NotRequired[str]
    qdrant_quantization_config: NotRequired[str]
    qdrant_semantic_cache_embedding_model: str
