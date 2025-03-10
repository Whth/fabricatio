"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import Any, TypedDict

from litellm.caching.caching import CacheMode
from litellm.types.caching import CachingSupportedCallTypes


class CollectionSimpleConfigKwargs(TypedDict, total=False):
    """Configuration parameters for a vector collection.

    These arguments are typically used when configuring connections to vector databases.
    """

    dimension: int
    timeout: float


class FetchKwargs(TypedDict, total=False):
    """Arguments for fetching data from vector collections.

    Controls how data is retrieved from vector databases, including filtering
    and result limiting parameters.
    """

    collection_name: str
    similarity_threshold: float
    result_per_query: int


class EmbeddingKwargs(TypedDict, total=False):
    """Configuration parameters for text embedding operations.

    These settings control the behavior of embedding models that convert text
    to vector representations.
    """

    model: str
    dimensions: int
    timeout: int
    caching: bool


class LLMKwargs(TypedDict, total=False):
    """Configuration parameters for language model inference.

    These arguments control the behavior of large language model calls,
    including generation parameters and caching options.
    """

    model: str
    temperature: float
    stop: str | list[str]
    top_p: float
    max_tokens: int
    stream: bool
    timeout: int
    max_retries: int
    no_cache: bool  # if the req uses cache in this call
    no_store: bool  # If store the response of this call to cache
    cache_ttl: int  # how long the stored cache is alive, in seconds
    s_maxage: int  # max accepted age of cached response, in seconds


class GenerateKwargs(LLMKwargs, total=False):
    """Arguments for content generation operations.

    Extends LLMKwargs with additional parameters specific to generation tasks,
    such as the number of generated items and the system message.
    """

    system_message: str


class ValidateKwargs[T](GenerateKwargs, total=False):
    """Arguments for content validation operations.

    Extends LLMKwargs with additional parameters specific to validation tasks,
    such as limiting the number of validation attempts.
    """

    default: T
    max_validations: int


# noinspection PyTypedDict
class ReviewKwargs[T](ValidateKwargs[T], total=False):
    """Arguments for content review operations.

    Extends GenerateKwargs with parameters for evaluating content against
    specific topics and review criteria.
    """

    topic: str
    criteria: set[str]


# noinspection PyTypedDict
class ChooseKwargs[T](ValidateKwargs[T], total=False):
    """Arguments for selection operations.

    Extends GenerateKwargs with parameters for selecting among options,
    such as the number of items to choose.
    """

    k: int


class CacheKwargs(TypedDict, total=False):
    """Configuration parameters for the caching system.

    These arguments control the behavior of various caching backends,
    including in-memory, Redis, S3, and vector database caching options.
    """

    mode: CacheMode  # when default_on cache is always on, when default_off cache is opt in
    host: str
    port: str
    password: str
    namespace: str
    ttl: float
    default_in_memory_ttl: float
    default_in_redis_ttl: float
    similarity_threshold: float
    supported_call_types: list[CachingSupportedCallTypes]
    # s3 Bucket, boto3 configuration
    s3_bucket_name: str
    s3_region_name: str
    s3_api_version: str
    s3_use_ssl: bool
    s3_verify: bool | str
    s3_endpoint_url: str
    s3_aws_access_key_id: str
    s3_aws_secret_access_key: str
    s3_aws_session_token: str
    s3_config: Any
    s3_path: str
    redis_semantic_cache_use_async: bool
    redis_semantic_cache_embedding_model: str
    redis_flush_size: int
    redis_startup_nodes: list
    disk_cache_dir: Any
    qdrant_api_base: str
    qdrant_api_key: str
    qdrant_collection_name: str
    qdrant_quantization_config: str
    qdrant_semantic_cache_embedding_model: str
