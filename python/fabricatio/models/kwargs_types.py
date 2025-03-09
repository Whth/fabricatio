"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import Any, List, NotRequired, Set, TypedDict

from litellm.caching.caching import CacheMode
from litellm.types.caching import CachingSupportedCallTypes
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt


class CollectionSimpleConfigKwargs(TypedDict):
    """Configuration parameters for a vector collection.

    These arguments are typically used when configuring connections to vector databases.
    """

    dimension: NotRequired[int]
    timeout: NotRequired[float]


class FetchKwargs(TypedDict):
    """Arguments for fetching data from vector collections.

    Controls how data is retrieved from vector databases, including filtering
    and result limiting parameters.
    """

    collection_name: NotRequired[str]
    similarity_threshold: NotRequired[float]
    result_per_query: NotRequired[int]


class EmbeddingKwargs(TypedDict):
    """Configuration parameters for text embedding operations.

    These settings control the behavior of embedding models that convert text
    to vector representations.
    """

    model: NotRequired[str]
    dimensions: NotRequired[int]
    timeout: NotRequired[PositiveInt]
    caching: NotRequired[bool]


class LLMKwargs(TypedDict):
    """Configuration parameters for language model inference.

    These arguments control the behavior of large language model calls,
    including generation parameters and caching options.
    """

    model: NotRequired[str]
    temperature: NotRequired[NonNegativeFloat]
    stop: NotRequired[str | List[str]]
    top_p: NotRequired[NonNegativeFloat]
    max_tokens: NotRequired[PositiveInt]
    stream: NotRequired[bool]
    timeout: NotRequired[PositiveInt]
    max_retries: NotRequired[PositiveInt]
    no_cache: NotRequired[bool]  # If use cache in this call
    no_store: NotRequired[bool]  # If store the response of this call to cache
    cache_ttl: NotRequired[int]  # how long the stored cache is alive, in seconds
    s_maxage: NotRequired[int]  # max accepted age of cached response, in seconds


class ValidateKwargs[T](LLMKwargs):
    """Arguments for content validation operations.

    Extends LLMKwargs with additional parameters specific to validation tasks,
    such as limiting the number of validation attempts.
    """

    default: NotRequired[T]
    max_validations: NotRequired[PositiveInt]


class GenerateKwargs(ValidateKwargs):
    """Arguments for content generation operations.

    Extends ValidateKwargs with parameters specific to text generation,
    including system prompt configuration.
    """

    system_message: NotRequired[str]


class ReviewKwargs(GenerateKwargs):
    """Arguments for content review operations.

    Extends GenerateKwargs with parameters for evaluating content against
    specific topics and review criteria.
    """

    topic: str
    criteria: NotRequired[Set[str]]


class ChooseKwargs(GenerateKwargs):
    """Arguments for selection operations.

    Extends GenerateKwargs with parameters for selecting among options,
    such as the number of items to choose.
    """

    k: NotRequired[NonNegativeInt]


class CacheKwargs(TypedDict, total=False):
    """Configuration parameters for the caching system.

    These arguments control the behavior of various caching backends,
    including in-memory, Redis, S3, and vector database caching options.
    """

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
