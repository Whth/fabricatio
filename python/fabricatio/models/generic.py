"""This module defines generic classes for models in the Fabricatio library."""

from abc import abstractmethod
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Self, Union, final

import orjson
from fabricatio._rust import blake3_hash
from fabricatio._rust_instances import template_manager
from fabricatio.config import configs
from fabricatio.fs.readers import magika, safe_text_read
from fabricatio.journal import logger
from fabricatio.parser import JsonCapture
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    SecretStr,
)


class Base(BaseModel):
    """Base class for all models with Pydantic configuration."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class Display(Base):
    """Class that provides a method to display the model in a formatted JSON string."""

    def display(self) -> str:
        """Display the model in a formatted JSON string.

        Returns:
            str: The formatted JSON string of the model.
        """
        return self.model_dump_json(indent=1)


class Named(Base):
    """Class that includes a name attribute."""

    name: str = Field(frozen=True)
    """The name of the object."""


class Described(Base):
    """Class that includes a description attribute."""

    description: str = Field(default="", frozen=True)
    """The description of the object."""


class WithBriefing(Named, Described):
    """Class that provides a briefing based on the name and description."""

    @property
    def briefing(self) -> str:
        """Get the briefing of the object.

        Returns:
            str: The briefing of the object.
        """
        return f"{self.name}: {self.description}" if self.description else self.name


class WithFormatedJsonSchema(Base):
    """Class that provides a formatted JSON schema of the model."""

    @classmethod
    def formated_json_schema(cls) -> str:
        """Get the JSON schema of the model in a formatted string.

        Returns:
            str: The JSON schema of the model in a formatted string.
        """
        return orjson.dumps(
            cls.model_json_schema(),
            option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
        ).decode()


class CreateJsonObjPrompt(WithFormatedJsonSchema):
    """Class that provides a prompt for creating a JSON object."""

    @classmethod
    def create_json_prompt(cls, requirement: str) -> str:
        """Create the prompt for creating a JSON object with given requirement.

        Args:
            requirement (str): The requirement for the JSON object.

        Returns:
            str: The prompt for creating a JSON object with given requirement.
        """
        return template_manager.render_template(
            configs.templates.create_json_obj_template,
            {"requirement": requirement, "json_schema": cls.formated_json_schema()},
        )


class InstantiateFromString(Base):
    """Class that provides a method to instantiate the class from a string."""

    @classmethod
    def instantiate_from_string(cls, string: str) -> Self | None:
        """Instantiate the class from a string.

        Args:
            string (str): The string to instantiate the class from.

        Returns:
            Self | None: The instance of the class or None if the string is not valid.
        """
        return JsonCapture.convert_with(string, cls.model_validate_json)


class ProposedAble(CreateJsonObjPrompt, InstantiateFromString):
    """Class that provides a method to propose a JSON object based on the requirement."""

    pass


class FinalizedDumpAble(Base):
    """Class that provides a method to finalize the dump of the object."""

    @abstractmethod
    def finalized_dump(self) -> str:
        """Finalize the dump of the object.

        Returns:
            str: The finalized dump of the object.
        """

    def finalized_dump_to(self, path: str | Path) -> Self:
        """Finalize the dump of the object to a file.

        Args:
            path (str | Path): The path to save the finalized dump.

        Returns:
            Self: The current instance of the object.
        """
        Path(path).write_text(self.finalized_dump(), encoding="utf-8")
        return self


class WithDependency(Base):
    """Class that manages file dependencies."""

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
        return template_manager.render_template(
            configs.templates.dependencies_template,
            {
                (pth := Path(p)).name: {
                    "path": pth.as_posix(),
                    "exists": pth.exists(),
                    "description": (identity := magika.identify_path(pth)).output.description,
                    "size": f"{pth.stat().st_size / (1024 * 1024) if pth.exists() and pth.is_file() else 0:.3f} MB",
                    "content": (text := safe_text_read(pth)),
                    "lines": len(text.splitlines()),
                    "language": identity.output.ct_label,
                    "checksum": blake3_hash(pth.read_bytes()) if pth.exists() and pth.is_file() else "unknown",
                }
                for p in self.dependencies
            },
        )


class PrepareVectorization(Base):
    """Class that prepares the vectorization of the model."""

    @abstractmethod
    def _prepare_vectorization_inner(self) -> str:
        """Prepare the vectorization of the model."""

    def prepare_vectorization(self, max_length: Optional[int] = None) -> str:
        """Prepare the vectorization of the model.

        Returns:
            str: The prepared vectorization of the model.
        """
        max_length = max_length or configs.embedding.max_sequence_length
        chunk = self._prepare_vectorization_inner()
        if len(chunk) > max_length:
            logger.error(err := f"Chunk exceeds maximum sequence length {max_length}.")
            raise ValueError(err)

        return chunk


class ScopedConfig(Base):
    """Class that manages a scoped configuration."""

    llm_api_endpoint: Optional[HttpUrl] = None
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

    embedding_api_endpoint: Optional[HttpUrl] = None
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

    milvus_uri: Optional[HttpUrl] = Field(default=None)
    """The URI of the Milvus server."""
    milvus_token: Optional[SecretStr] = Field(default=None)
    """The token for the Milvus server."""
    milvus_timeout: Optional[PositiveFloat] = Field(default=None)
    """The timeout for the Milvus server."""
    milvus_dimensions: Optional[PositiveInt] = Field(default=None)
    """The dimensions of the Milvus server."""

    @final
    def fallback_to(self, other: "ScopedConfig") -> Self:
        """Fallback to another instance's attribute values if the current instance's attributes are None.

        Args:
            other (LLMUsage): Another instance from which to copy attribute values.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        # Iterate over the attribute names and copy values from 'other' to 'self' where applicable
        # noinspection PydanticTypeChecker,PyTypeChecker
        for attr_name in ScopedConfig.model_fields:
            # Copy the attribute value from 'other' to 'self' only if 'self' has None and 'other' has a non-None value
            if getattr(self, attr_name) is None and (attr := getattr(other, attr_name)) is not None:
                setattr(self, attr_name, attr)

        # Return the current instance to allow for method chaining
        return self

    @final
    def hold_to(self, others: Union["ScopedConfig", Iterable["ScopedConfig"]]) -> Self:
        """Hold to another instance's attribute values if the current instance's attributes are None.

        Args:
            others (LLMUsage | Iterable[LLMUsage]): Another instance or iterable of instances from which to copy attribute values.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        if not isinstance(others, Iterable):
            others = [others]
        for other in others:
            # noinspection PyTypeChecker,PydanticTypeChecker
            for attr_name in ScopedConfig.model_fields:
                if (attr := getattr(self, attr_name)) is not None and getattr(other, attr_name) is None:
                    setattr(other, attr_name, attr)
