"""This module defines generic classes for models in the Fabricatio library, providing a foundation for various model functionalities."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Self, Type, Union, final

import ujson
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    SecretStr,
)

from fabricatio_core.fs.readers import safe_text_read
from fabricatio_core.journal import logger
from fabricatio_core.rust import CONFIG, TEMPLATE_MANAGER, blake3_hash, detect_language


class Base(BaseModel, ABC):
    """Base class for all models with Pydantic configuration.

    This class sets up the basic Pydantic configuration for all models in the Fabricatio library.
    The `model_config` uses `use_attribute_docstrings=True` to ensure field descriptions are
    pulled from the attribute's docstring instead of the default Pydantic behavior.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)


class Display(Base, ABC):
    """Class that provides formatted JSON representation utilities.

    Provides methods to generate both pretty-printed and compact JSON representations of the model.
    Used for debugging and logging purposes.
    """

    def display(self) -> str:
        """Generate pretty-printed JSON representation.

        Returns:
            str: JSON string with 1-level indentation for readability
        """
        return self.model_dump_json(indent=1, by_alias=True)

    def compact(self) -> str:
        """Generate compact JSON representation.

        Returns:
            str: Minified JSON string without whitespace
        """
        return self.model_dump_json(by_alias=True)

    @staticmethod
    def seq_display(seq: Iterable["Display"], compact: bool = False) -> str:
        """Generate formatted display for sequence of Display objects.

        Args:
            seq (Iterable[Display]): Sequence of objects to display
            compact (bool): Use compact format instead of pretty print

        Returns:
            str: Combined display output with boundary markers
        """
        return (
                "--- Start of Extra Info Sequence ---"
                + "\n".join(d.compact() if compact else d.display() for d in seq)
                + "--- End of Extra Info Sequence ---"
        )


class Named(Base, ABC):
    """Class that includes a name attribute.

    This class adds a name attribute to models, which is intended to be a unique identifier.
    """

    name: str
    """The name of this object,briefly and conclusively."""


class Described(Base, ABC):
    """Class that includes a description attribute.

    This class adds a description attribute to models, providing additional context or information.
    """

    description: str
    """A comprehensive description of this object, including its purpose, scope, and context.
    This should clearly explain what this object is about, why it exists, and in what situations
    it applies. The description should be detailed enough to provide full understanding of
    this object's intent and application."""


class Titled(Base, ABC):
    """Class that includes a title attribute."""

    title: str
    """The title of this object, make it professional and concise.No prefixed heading number should be included."""


class Language:
    """Class that provides a language attribute."""

    @property
    def language(self) -> str:
        """Get the language of the object."""
        if isinstance(self, Described) and self.description:
            return detect_language(self.description)
        if isinstance(self, Titled) and self.title:
            return detect_language(self.title)
        if isinstance(self, Named) and self.name:
            return detect_language(self.name)
        raise RuntimeError(f"Cannot determine language! class that not support language: {self.__class__.__name__}")


class WithBriefing(Named, Described, ABC):
    """Class that provides a briefing based on the name and description.

    This class combines the name and description attributes to provide a brief summary of the object.
    """

    @property
    def briefing(self) -> str:
        """Get the briefing of the object.

        Returns:
            str: The briefing of the object.
        """
        return f"{self.name}: {self.description}" if self.description else self.name


class WithDependency(Base, ABC):
    """Class that manages file dependencies.

    This class includes methods to manage file dependencies required for reading or writing.
    """

    dependencies: List[str] = Field(default_factory=list)
    """The file dependencies which is needed to read or write to meet a specific requirement, a list of file paths."""

    def add_dependency[P: str | Path](self, dependency: P | List[P]) -> Self:
        """Add a file dependency to the task.

        Args:
            dependency (str | Path | List[str | Path]): The file dependency to add to the task.

        Returns:
            Self: The current instance of the task.
        """
        if not isinstance(dependency, list):
            dependency = [dependency]
        self.dependencies.extend(Path(d).as_posix() for d in dependency)
        return self

    def remove_dependency[P: str | Path](self, dependency: P | List[P]) -> Self:
        """Remove a file dependency from the task.

        Args:
            dependency (str | Path | List[str | Path]): The file dependency to remove from the task.

        Returns:
            Self: The current instance of the task.
        """
        if not isinstance(dependency, list):
            dependency = [dependency]
        for d in dependency:
            self.dependencies.remove(Path(d).as_posix())
        return self

    def clear_dependencies(self) -> Self:
        """Clear all file dependencies from the task.

        Returns:
            Self: The current instance of the task.
        """
        self.dependencies.clear()
        return self

    def override_dependencies[P: str | Path](self, dependencies: List[P] | P) -> Self:
        """Override the file dependencies of the task.

        Args:
            dependencies (List[str | Path] | str | Path): The file dependencies to override the task's dependencies.

        Returns:
            Self: The current instance of the task.
        """
        return self.clear_dependencies().add_dependency(dependencies)

    def pop_dependence[T](self, idx: int = -1, reader: Callable[[str], T] = safe_text_read) -> T:
        """Pop the file dependencies from the task.

        Returns:
            str: The popped file dependency
        """
        return reader(self.dependencies.pop(idx))

    @property
    def dependencies_prompt(self) -> str:
        """Generate a prompt for the task based on the file dependencies.

        Returns:
            str: The generated prompt for the task.
        """
        from fabricatio_core.fs import MAGIKA

        return TEMPLATE_MANAGER.render_template(
            CONFIG.templates.dependencies_template,
            {
                (pth := Path(p)).name: {
                    "path": pth.as_posix(),
                    "exists": pth.exists(),
                    "description": (identity := MAGIKA.identify_path(pth)).output.description,
                    "size": f"{pth.stat().st_size / (1024 * 1024) if pth.exists() and pth.is_file() else 0:.3f} MB",
                    "content": (text := safe_text_read(pth)),
                    "lines": len(text.splitlines()),
                    "language": identity.output.ct_label,
                    "checksum": blake3_hash(pth.read_bytes()) if pth.exists() and pth.is_file() else "unknown",
                }
                for p in self.dependencies
            },
        )


class Vectorizable(ABC):
    """Class that prepares the vectorization of the model.

    This class includes methods to prepare the model for vectorization, ensuring it fits within a specified token length.
    """

    @abstractmethod
    def _prepare_vectorization_inner(self) -> str:
        """Prepare the model for vectorization."""

    @final
    def prepare_vectorization(self, max_length: Optional[int] = None) -> str:
        """Prepare the vectorization of the model.

        Args:
            max_length (Optional[int]): The maximum token length for the vectorization. Defaults to the configuration.

        Returns:
            str: The prepared vectorization of the model.

        Raises:
            ValueError: If the chunk exceeds the maximum sequence length.
        """
        from litellm.utils import token_counter

        max_length = max_length or CONFIG.embedding.max_sequence_length
        chunk = self._prepare_vectorization_inner()
        if max_length and (length := token_counter(text=chunk)) > max_length:
            raise ValueError(f"Chunk exceeds maximum sequence length {max_length}, got {length}, see \n{chunk}")

        return chunk


class ScopedConfig(Base, ABC):
    """Configuration holder with hierarchical fallback mechanism.

    Manages LLM, embedding, and vector database configurations with fallback logic.
    Allows configuration values to be overridden in a hierarchical manner.
    """

    llm_api_endpoint: Optional[str] = None
    """The OpenAI API endpoint."""

    llm_api_key: Optional[SecretStr] = None
    """The OpenAI API key."""

    llm_timeout: Optional[PositiveInt] = None
    """The timeout of the LLM model."""

    llm_max_retries: Optional[PositiveInt] = None
    """The maximum number of retries."""

    llm_model: Optional[str] = None
    """The LLM model name."""

    llm_temperature: Optional[NonNegativeFloat] = None
    """The temperature of the LLM model."""

    llm_stop_sign: Optional[str | List[str]] = None
    """The stop sign of the LLM model."""

    llm_top_p: Optional[NonNegativeFloat] = None
    """The top p of the LLM model."""

    llm_generation_count: Optional[PositiveInt] = None
    """The number of generations to generate."""

    llm_stream: Optional[bool] = None
    """Whether to stream the LLM model's response."""

    llm_max_tokens: Optional[PositiveInt] = None
    """The maximum number of tokens to generate."""

    llm_tpm: Optional[PositiveInt] = None
    """The tokens per minute of the LLM model."""

    llm_rpm: Optional[PositiveInt] = None
    """The requests per minute of the LLM model."""

    llm_presence_penalty: Optional[PositiveFloat] = None
    """The presence penalty of the LLM model."""

    llm_frequency_penalty: Optional[PositiveFloat] = None
    """The frequency penalty of the LLM model."""

    embedding_api_endpoint: Optional[str] = None
    """The OpenAI API endpoint."""

    embedding_api_key: Optional[SecretStr] = None
    """The OpenAI API key."""

    embedding_timeout: Optional[PositiveInt] = None
    """The timeout of the LLM model."""

    embedding_model: Optional[str] = None
    """The LLM model name."""

    embedding_max_sequence_length: Optional[PositiveInt] = None
    """The maximum sequence length."""

    embedding_dimensions: Optional[PositiveInt] = None
    """The dimensions of the embedding."""

    embedding_caching: Optional[bool] = False
    """Whether to cache the embedding result."""

    milvus_uri: Optional[str] = Field(default=None)
    """The URI of the Milvus server."""

    milvus_token: Optional[SecretStr] = Field(default=None)
    """The token for the Milvus server."""

    milvus_timeout: Optional[PositiveFloat] = Field(default=None)
    """The timeout for the Milvus server."""

    milvus_dimensions: Optional[PositiveInt] = Field(default=None)
    """The dimensions of the Milvus server."""

    @final
    def fallback_to(self, other: Union["ScopedConfig", Any]) -> Self:
        """Merge configuration values with fallback priority.

        Copies non-null values from 'other' to self where current values are None.

        Args:
            other (ScopedConfig): Configuration to fallback to

        Returns:
            Self: Current instance with merged values
        """
        if not isinstance(other, ScopedConfig):
            return self

        # Iterate over the attribute names and copy values from 'other' to 'self' where applicable
        # noinspection PydanticTypeChecker,PyTypeChecker
        for attr_name in ScopedConfig.model_fields:
            # Copy the attribute value from 'other' to 'self' only if 'self' has None and 'other' has a non-None value
            if getattr(self, attr_name) is None and (attr := getattr(other, attr_name)) is not None:
                setattr(self, attr_name, attr)

        # Return the current instance to allow for method chaining
        return self

    @final
    def hold_to(self, others: Union[Union["ScopedConfig", Any], Iterable[Union["ScopedConfig", Any]]]) -> Self:
        """Propagate non-null values to other configurations.

        Copies current non-null values to target configurations where they are None.

        Args:
            others (ScopedConfig|Iterable): Target configurations to update

        Returns:
            Self: Current instance unchanged
        """
        if not isinstance(others, Iterable):
            others = [others]

        for other in (o for o in others if isinstance(o, ScopedConfig)):
            # noinspection PyTypeChecker,PydanticTypeChecker
            for attr_name in ScopedConfig.model_fields:
                if (attr := getattr(self, attr_name)) is not None and getattr(other, attr_name) is None:
                    setattr(other, attr_name, attr)
        return self


class Patch[T](ProposedAble, ABC):
    """Base class for patches.

    This class provides a base implementation for patches that can be applied to other objects.
    """

    def apply(self, other: T) -> T:
        """Apply the patch to another instance.

        Args:
            other (T): The instance to apply the patch to.

        Returns:
            T: The instance with the patch applied.

        Raises:
            ValueError: If a field in the patch is not found in the target instance.
        """
        for field in self.__class__.model_fields:
            if not hasattr(other, field):
                raise ValueError(f"{field} not found in {other}, are you applying to the wrong type?")
            setattr(other, field, getattr(self, field))
        return other

    def as_kwargs(self) -> Dict[str, Any]:
        """Get the kwargs of the patch."""
        return self.model_dump()

    @staticmethod
    def ref_cls() -> Optional[Type[BaseModel]]:
        """Get the reference class of the model."""
        return None

    @classmethod
    def formated_json_schema(cls) -> str:
        """Get the JSON schema of the model in a formatted string.

        Returns:
            str: The JSON schema of the model in a formatted string.
        """
        my_schema = cls.model_json_schema(schema_generator=UnsortGenerate)

        ref_cls = cls.ref_cls()
        if ref_cls is not None:
            # copy the desc info of each corresponding fields from `ref_cls`
            for field_name in [f for f in cls.model_fields if f in ref_cls.model_fields]:
                my_schema["properties"][field_name]["description"] = (
                        ref_cls.model_fields[field_name].description or my_schema["properties"][field_name][
                    "description"]
                )
            my_schema["description"] = ref_cls.__doc__

        return ujson.dumps(my_schema, indent=2, ensure_ascii=False, sort_keys=False)


class SequencePatch[T](ProposedUpdateAble, ABC):
    """Base class for patches.

    This class provides a base implementation for patches that can be applied to sequences of objects.
    """

    tweaked: List[T]
    """Tweaked content list"""

    def update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance.

        Args:
            other (Self): The other instance to update from.

        Returns:
            Self: The current instance with updated attributes.
        """
        self.tweaked.clear()
        self.tweaked.extend(other.tweaked)
        return self

    @classmethod
    def default(cls) -> Self:
        """Defaults to empty list.

        Returns:
            Self: A new instance with an empty list of tweaks.
        """
        return cls(tweaked=[])


class PersistentAble(Base, ABC):
    """Class providing file persistence capabilities.

    Enables saving model instances to disk with timestamped filenames and loading from persisted files.
    Implements basic versioning through filename hashing and timestamping.
    """

    def persist(self, path: str | Path) -> Self:
        """Save model instance to disk with versioned filename.

        Args:
            path (str | Path): Target directory or file path. If directory, filename is auto-generated.

        Returns:
            Self: Current instance for method chaining

        Notes:
            - Filename format: <ClassName>_<YYYYMMDD_HHMMSS>_<6-char_hash>.json
            - Hash generated from JSON content ensures uniqueness
        """
        p = Path(path)
        out = self.model_dump_json(indent=1, by_alias=True)

        # Generate a timestamp in the format YYYYMMDD_HHMMSS
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generate the hash
        file_hash = blake3_hash(out.encode())[:6]

        # Construct the file name with timestamp and hash
        file_name = f"{self.__class__.__name__}_{timestamp}_{file_hash}.json"

        if p.is_dir():
            p.joinpath(file_name).write_text(out, encoding="utf-8")
        else:
            p.mkdir(exist_ok=True, parents=True)
            p.write_text(out, encoding="utf-8")

        logger.info(f"Persisted `{self.__class__.__name__}` to {p.as_posix()}")
        return self

    @classmethod
    def from_latest_persistent(cls, dir_path: str | Path) -> Optional[Self]:
        """Load most recent persisted instance from directory.

        Args:
            dir_path (str | Path): Directory containing persisted files

        Returns:
            Self: Most recently modified instance

        Raises:
            NotADirectoryError: If path is not a valid directory
            FileNotFoundError: If no matching files found
        """
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            return None

        pattern = f"{cls.__name__}_*.json"
        files = list(dir_path.glob(pattern))

        if not files:
            return None

        def _get_timestamp(file_path: Path) -> datetime:
            stem = file_path.stem
            parts = stem.split("_")
            return datetime.strptime(f"{parts[1]}_{parts[2]}", "%Y%m%d_%H%M%S")

        files.sort(key=lambda f: _get_timestamp(f), reverse=True)

        return cls.from_persistent(files.pop(0))

    @classmethod
    def from_persistent(cls, path: str | Path) -> Self:
        """Load an instance from a specific persisted file.

        Args:
            path (str | Path): Path to the JSON file.

        Returns:
            Self: The loaded instance from the file.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            ValueError: If the file content is invalid for the model.
        """
        return cls.model_validate_json(safe_text_read(path))
