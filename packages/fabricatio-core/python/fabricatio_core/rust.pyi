"""Python interface definitions for Rust-based functionality.

This module provides type stubs and documentation for Rust-implemented utilities,
including template rendering, cryptographic hashing, language detection, and
bibliography management. The actual implementations are provided by Rust modules.

Key Features:
- TemplateManager: Handles Handlebars template rendering and management.
- BibManager: Manages BibTeX bibliography parsing and querying.
- Cryptographic utilities: BLAKE3 hashing.
- Text utilities: Word boundary splitting and word counting.
"""

from enum import StrEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Self, Union, overload


class TemplateManager:
    """Template rendering engine using Handlebars templates.

    This manager handles template discovery, loading, and rendering
    through a wrapper around the handlebars-rust engine.

    See: https://crates.io/crates/handlebars
    """

    @property
    def template_count(self) -> int:
        """Returns the number of currently loaded templates."""

    def get_template_source(self, name: str) -> Optional[str]:
        """Get the filesystem path for a template.

        Args:
            name: Template name (without extension)

        Returns:
            Path to the template file if found, None otherwise
        """

    def discover_templates(self) -> None:
        """Scan template directories and load available templates.

        This refreshes the template cache, finding any new or modified templates.
        """

    @overload
    def render_template(self, name: str, data: Dict[str, Any]) -> str: ...

    @overload
    def render_template(self, name: str, data: List[Dict[str, Any]]) -> List[str]: ...

    def render_template(self, name: str, data: Dict[str, Any] | List[Dict[str, Any]]) -> str | List[str]:
        """Render a template with context data.

        Args:
            name: Template name (without extension)
            data: Context dictionary or list of dictionaries to provide variables to the template

        Returns:
            Rendered template content as string or list of strings

        Raises:
            RuntimeError: If template rendering fails
        """

    @overload
    def render_template_raw(self, template: str, data: Dict[str, Any]) -> str: ...

    @overload
    def render_template_raw(self, template: str, data: List[Dict[str, Any]]) -> List[str]: ...

    def render_template_raw(self, template: str, data: Dict[str, Any] | List[Dict[str, Any]]) -> str | List[str]:
        """Render a template with context data.

        Args:
            template: The template string
            data: Context dictionary or list of dictionaries to provide variables to the template

        Returns:
            Rendered template content as string or list of strings
        """


def blake3_hash(content: bytes) -> str:
    """Calculate the BLAKE3 cryptographic hash of data.

    Args:
        content: Bytes to be hashed

    Returns:
        Hex-encoded BLAKE3 hash string
    """


def split_word_bounds(string: str) -> List[str]:
    """Split the string into words based on word boundaries.

    Args:
        string: The input string to be split.

    Returns:
        A list of words extracted from the string.
    """


def split_sentence_bounds(string: str) -> List[str]:
    """Split the string into sentences based on sentence boundaries.

    Args:
        string: The input string to be split.

    Returns:
        A list of sentences extracted from the string.
    """


def split_into_chunks(string: str, max_chunk_size: int, max_overlapping_rate: float = 0.3) -> List[str]:
    """Split the string into chunks of a specified size.

    Args:
        string: The input string to be split.
        max_chunk_size: The maximum size of each chunk.
        max_overlapping_rate: The minimum overlapping rate between chunks.

    Returns:
        A list of chunks extracted from the string.
    """


def word_count(string: str) -> int:
    """Count the number of words in the string.

    Args:
        string: The input string to count words from.

    Returns:
        The number of words in the string.
    """


class LLMConfig:
    """LLM configuration structure.

    Contains parameters for configuring Language Learning Models.
    """

    api_endpoint: Optional[str]
    """API endpoint URL for the LLM service."""

    api_key: Optional[SecretStr]
    """Authentication key for the LLM service."""

    timeout: Optional[int]
    """Maximum time in seconds to wait for a response."""

    max_retries: Optional[int]
    """Number of retry attempts for failed requests."""

    model: Optional[str]
    """Name of the LLM model to use."""

    temperature: Optional[float]
    """Controls randomness in response generation (0.0-2.0)."""

    stop_sign: Optional[List[str]]
    """Sequence(s) that signal the LLM to stop generating tokens."""

    top_p: Optional[float]
    """Controls diversity via nucleus sampling (0.0-1.0)."""

    generation_count: Optional[int]
    """Number of completions to generate for each prompt."""

    stream: Optional[bool]
    """When true, responses are streamed as they're generated."""

    max_tokens: Optional[int]
    """Maximum number of tokens to generate in the response."""

    rpm: Optional[int]
    """Rate limit in requests per minute."""

    tpm: Optional[int]
    """Rate limit in tokens per minute."""

    presence_penalty: Optional[float]
    """Penalizes new tokens based on their presence in text so far (-2.0-2.0)."""

    frequency_penalty: Optional[float]
    """Penalizes new tokens based on their frequency in text so far (-2.0-2.0)."""


class EmbeddingConfig:
    """Embedding configuration structure."""

    model: Optional[str]
    """The embedding model name."""

    dimensions: Optional[int]
    """The dimensions of the embedding."""

    timeout: Optional[int]
    """The timeout of the embedding model in seconds."""

    max_sequence_length: Optional[int]
    """The maximum sequence length of the embedding model."""

    caching: Optional[bool]
    """Whether to cache the embedding."""

    api_endpoint: Optional[str]
    """The API endpoint URL."""

    api_key: Optional[SecretStr]
    """The API key."""


class RagConfig:
    """RAG (Retrieval Augmented Generation) configuration structure."""

    milvus_uri: Optional[str]
    """The URI of the Milvus server."""

    milvus_timeout: Optional[float]
    """The timeout of the Milvus server in seconds."""

    milvus_token: Optional[SecretStr]
    """The token for Milvus authentication."""

    milvus_dimensions: Optional[int]
    """The dimensions for Milvus vectors."""


class DebugConfig:
    """Debug configuration structure."""

    log_level: Optional[str]
    """The logging level to use."""


class TemplateManagerConfig:
    """Template manager configuration structure."""

    template_dir: List[Path]
    """The directories containing the templates."""

    active_loading: Optional[bool]
    """Whether to enable active loading of templates."""

    template_suffix: Optional[str]
    """The suffix of the templates."""


class TemplateConfig:
    """Template configuration structure."""

    digest_template: str
    """The name of the consume template which will be used to consume a requirement to a task."""

    dispatch_task_template: str
    """The name of the dispatch task template which will be used to dispatch a task."""
    research_content_summary_template: str
    """The name of the research content summary template which will be used to generate a summary of research content."""

    create_json_obj_template: str
    """The name of the create json object template which will be used to create a json object."""

    draft_tool_usage_code_template: str
    """The name of the draft tool usage code template which will be used to draft tool usage code."""

    make_choice_template: str
    """The name of the make choice template which will be used to make a choice."""

    make_judgment_template: str
    """The name of the make judgment template which will be used to make a judgment."""

    dependencies_template: str
    """The name of the dependencies template which will be used to manage dependencies."""

    task_briefing_template: str
    """The name of the task briefing template which will be used to brief a task."""

    rate_fine_grind_template: str
    """The name of the rate fine grind template which will be used to rate fine grind."""

    draft_rating_manual_template: str
    """The name of the draft rating manual template which will be used to draft rating manual."""

    draft_rating_criteria_template: str
    """The name of the draft rating criteria template which will be used to draft rating criteria."""

    extract_reasons_from_examples_template: str
    """The name of the extract reasons from examples template which will be used to extract reasons from examples."""

    extract_criteria_from_reasons_template: str
    """The name of the extract criteria from reasons template which will be used to extract criteria from reasons."""

    draft_rating_weights_klee_template: str
    """The name of the draft rating weights klee template which will be used to draft rating weights with Klee method."""

    retrieved_display_template: str
    """The name of the retrieved display template which will be used to display retrieved documents."""

    liststr_template: str
    """The name of the liststr template which will be used to display a list of strings."""

    refined_query_template: str
    """The name of the refined query template which will be used to refine a query."""

    pathstr_template: str
    """The name of the pathstr template which will be used to acquire a path of strings."""

    review_string_template: str
    """The name of the review string template which will be used to review a string."""

    generic_string_template: str
    """The name of the generic string template which will be used to review a string."""

    co_validation_template: str
    """The name of the co-validation template which will be used to co-validate a string."""

    as_prompt_template: str
    """The name of the as prompt template which will be used to convert a string to a prompt."""

    check_string_template: str
    """The name of the check string template which will be used to check a string."""

    ruleset_requirement_breakdown_template: str
    """The name of the ruleset requirement breakdown template which will be used to breakdown a ruleset requirement."""

    fix_troubled_obj_template: str
    """The name of the fix troubled object template which will be used to fix a troubled object."""

    fix_troubled_string_template: str
    """The name of the fix troubled string template which will be used to fix a troubled string."""

    rule_requirement_template: str
    """The name of the rule requirement template which will be used to generate a rule requirement."""

    extract_template: str
    """The name of the extract template which will be used to extract model from string."""

    chap_summary_template: str
    """The name of the chap summary template which will be used to generate a chapter summary."""


class RoutingConfig:
    """Routing configuration structure for controlling request dispatching behavior."""

    max_parallel_requests: Optional[int]
    """The maximum number of parallel requests. None means not checked."""

    allowed_fails: Optional[int]
    """The number of allowed fails before the routing is considered failed."""

    retry_after: int
    """Minimum time to wait before retrying a failed request."""

    cooldown_time: Optional[int]
    """Time to cooldown a deployment after failure in seconds."""


class GeneralConfig:
    """General configuration structure for application-wide settings."""

    confirm_on_ops: bool
    """Whether to confirm operations before executing them."""

    use_json_repair: bool
    """Whether to automatically repair malformed JSON."""


class ToolBoxConfig:
    """Configuration for toolbox functionality."""

    tool_module_name: str
    """The name of the module containing the toolbox."""

    data_module_name: str
    """The name of the module containing the data."""


class PymitterConfig:
    """Pymitter configuration structure for controlling event emission and listener behavior."""

    delimiter: str
    """The delimiter used to separate the event name into segments."""

    new_listener_event: bool
    """If set, a newListener event is emitted when a new listener is added."""

    max_listeners: int
    """The maximum number of listeners per event. -1 means unlimited."""


class Config:
    """Configuration structure containing all system components."""

    embedding: EmbeddingConfig
    """Embedding configuration."""

    llm: LLMConfig
    """LLM configuration."""

    debug: DebugConfig
    """Debug configuration."""

    rag: RagConfig
    """RAG configuration."""

    templates: TemplateConfig
    """Template configuration."""

    template_manager: TemplateManagerConfig
    """Template manager configuration."""

    routing: RoutingConfig
    """Routing configuration."""

    general: GeneralConfig
    """General configuration."""

    toolbox: ToolBoxConfig
    """Toolbox configuration."""

    pymitter: PymitterConfig
    """Pymitter configuration."""


CONFIG: Config


class SecretStr:
    """A string that should not be exposed."""

    def __init__(self, source: str) -> None: ...

    def get_secret_value(self) -> str:
        """Expose the secret string."""


TEMPLATE_MANAGER: TemplateManager


class Event:
    """Event class that represents a hierarchical event with segments.

    Events can be constructed from strings, lists of strings, or other Events.
    """

    segments: List[str]

    def __init__(self, segments: Optional[List[str]] = None) -> None:
        """Initialize a new Event with optional segments.

        Args:
            segments: Optional list of string segments
        """

    @staticmethod
    def instantiate_from(event: Union[str, Event, List[str]]) -> Event:
        """Create an Event from a string, list of strings, or another Event.

        Args:
            event: The source to create the Event from

        Returns:
            A new Event instance

        Raises:
            ValueError: If list elements are not strings
            TypeError: If event is an invalid type
        """

    @staticmethod
    def quick_instantiate(event: Union[str, Event, List[str]]) -> Event:
        """Create an Event and append wildcard and pending status.

        Args:
            event: The source to create the Event from

        Returns:
            A new Event instance with wildcard and pending status appended
        """

    def derive(self, event: Union[str, Event, List[str]]) -> Event:
        """Create a new Event by extending this one with another.

        Args:
            event: The Event to append

        Returns:
            A new Event that combines this Event with the provided one
        """

    def collapse(self) -> str:
        """Convert the Event to a delimited string.

        Returns:
            String representation with segments joined by delimiter
        """

    def fork(self) -> Event:
        """Create a copy of this Event.

        Returns:
            A new Event with the same segments
        """

    def push(self, segment: str) -> Self:
        """Add a segment to the Event.

        Args:
            segment: String segment to add

        Raises:
            ValueError: If segment is empty or contains the delimiter
        """

    def push_wildcard(self) -> Self:
        """Add a wildcard segment (*) to the Event."""

    def push_pending(self) -> Self:
        """Add a pending status segment to the Event."""

    def push_running(self) -> Self:
        """Add a running status segment to the Event."""

    def push_finished(self) -> Self:
        """Add a finished status segment to the Event."""

    def push_failed(self) -> Self:
        """Add a failed status segment to the Event."""

    def push_cancelled(self) -> Self:
        """Add a cancelled status segment to the Event."""

    def pop(self) -> Optional[str]:
        """Remove and return the last segment.

        Returns:
            The removed segment or None if the Event is empty
        """

    def clear(self) -> Self:
        """Remove all segments from the Event."""

    def concat(self, event: Union[str, Event, List[str]]) -> Self:
        """Append segments from another Event to this one.

        Args:
            event: The Event to append segments from
        """

    def __hash__(self) -> int: ...

    def __eq__(self, other: object) -> bool: ...

    def __ne__(self, other: object) -> bool: ...


class TaskStatus(StrEnum, str):
    """Enumeration of possible task statuses."""

    Pending: TaskStatus
    """Task is pending execution."""

    Running: TaskStatus
    """Task is currently running."""

    Finished: TaskStatus
    """Task has finished successfully."""

    Failed: TaskStatus
    """Task has failed."""

    Cancelled: TaskStatus
    """Task has been cancelled."""


def detect_language(string: str) -> str:
    """Detect the language of a given string."""


def is_chinese(string: str) -> bool:
    """Check if the given string is in Chinese."""


def is_english(string: str) -> bool:
    """Check if the given string is in English."""


def is_japanese(string: str) -> bool:
    """Check if the given string is in Japanese."""


def is_korean(string: str) -> bool:
    """Check if the given string is in Korean."""


def is_arabic(string: str) -> bool:
    """Check if the given string is in Arabic."""


def is_russian(string: str) -> bool:
    """Check if the given string is in Russian."""


def is_german(string: str) -> bool:
    """Check if the given string is in German."""


def is_french(string: str) -> bool:
    """Check if the given string is in French."""


def is_hindi(string: str) -> bool:
    """Check if the given string is in Hindi."""


def is_italian(string: str) -> bool:
    """Check if the given string is in Italian."""


def is_dutch(string: str) -> bool:
    """Check if the given string is in Dutch."""


def is_portuguese(string: str) -> bool:
    """Check if the given string is in Portuguese."""


def is_swedish(string: str) -> bool:
    """Check if the given string is in Swedish."""


def is_turkish(string: str) -> bool:
    """Check if the given string is in Turkish."""


def is_vietnamese(string: str) -> bool:
    """Check if the given string is in Vietnamese."""
