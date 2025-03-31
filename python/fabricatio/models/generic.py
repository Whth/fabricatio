"""This module defines generic classes for models in the Fabricatio library, providing a foundation for various model functionalities."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Self, Union, final, overload

import orjson
import rtoml
from fabricatio.config import configs
from fabricatio.fs.readers import MAGIKA, safe_text_read
from fabricatio.journal import logger
from fabricatio.parser import JsonCapture
from fabricatio.rust import blake3_hash
from fabricatio.rust_instances import TEMPLATE_MANAGER
from fabricatio.utils import ok
from litellm.utils import token_counter
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    PrivateAttr,
    SecretStr,
)
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue


class Base(BaseModel):
    """Base class for all models with Pydantic configuration.

    This class sets up the basic Pydantic configuration for all models in the Fabricatio library.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)


class Display(Base):
    """Class that provides a method to display the model in a formatted JSON string.

    This class includes methods to display the model in both formatted and compact JSON strings.
    """

    def display(self) -> str:
        """Display the model in a formatted JSON string.

        Returns:
            str: The formatted JSON string of the model.
        """
        return self.model_dump_json(indent=1)

    def compact(self) -> str:
        """Display the model in a compact JSON string.

        Returns:
            str: The compact JSON string of the model.
        """
        return self.model_dump_json()

    @staticmethod
    def seq_display(seq: Iterable["Display"], compact: bool = False) -> str:
        """Display a sequence of Display objects in a formatted JSON string.

        Args:
            seq (Iterable[Display]): The sequence of Display objects to display.
            compact (bool): Whether to display the sequence in a compact format. Defaults to False.

        Returns:
            str: The formatted JSON string of the sequence.
        """
        return "\n".join(d.compact() if compact else d.display() for d in seq)


class Named(Base):
    """Class that includes a name attribute.

    This class adds a name attribute to models, which is intended to be a unique identifier.
    """

    name: str
    """The name of the object."""


class Described(Base):
    """Class that includes a description attribute.

    This class adds a description attribute to models, providing additional context or information.
    """

    description: str
    """The description of the object."""


class AsPrompt(Base):
    """Class that provides a method to generate a prompt from the model.

    This class includes a method to generate a prompt based on the model's attributes.
    """

    @final
    def as_prompt(self) -> str:
        """Generate a prompt from the model.

        Returns:
            str: The generated prompt.
        """
        return TEMPLATE_MANAGER.render_template(
            configs.templates.as_prompt_template,
            self._as_prompt_inner(),
        )

    @abstractmethod
    def _as_prompt_inner(self) -> Dict[str, str]:
        """Generate the inner part of the prompt.

        This method should be implemented by subclasses to provide the specific data for the prompt.

        Returns:
            Dict[str, str]: The data for the prompt.
        """


class WithRef[T](Base):
    """Class that provides a reference to another object.

    This class manages a reference to another object, allowing for easy access and updates.
    """

    _reference: Optional[T] = PrivateAttr(None)

    @property
    def referenced(self) -> T:
        """Get the referenced object.

        Returns:
            T: The referenced object.

        Raises:
            ValueError: If the reference is not set.
        """
        return ok(
            self._reference, f"`{self.__class__.__name__}`'s `_reference` field is None. Have you called `update_ref`?"
        )

    @overload
    def update_ref[S: WithRef](self: S, reference: T) -> S: ...
    @overload
    def update_ref[S: WithRef](self: S, reference: "WithRef[T]") -> S: ...
    @overload
    def update_ref[S: WithRef](self: S, reference: None = None) -> S: ...
    def update_ref[S: WithRef](self: S, reference: Union[T, "WithRef[T]", None] = None) -> S:  # noqa: PYI019
        """Update the reference of the object.

        Args:
            reference (Union[T, WithRef[T], None]): The new reference to set.

        Returns:
            S: The current instance with the updated reference.
        """
        if isinstance(reference, self.__class__):
            self._reference = reference.referenced
        else:
            self._reference = reference  # pyright: ignore [reportAttributeAccessIssue]
        return self

    def derive[S: WithRef](self: S, reference: Any) -> S:  # noqa: PYI019
        """Derive a new object from the current object.

        Args:
            reference (Any): The reference for the new object.

        Returns:
            S: A new instance derived from the current object with the provided reference.
        """
        new = self.model_copy()
        new._reference = reference
        return new


class PersistentAble(Base):
    """Class that provides a method to persist the object.

    This class includes methods to persist the object to a file or directory.
    """

    def persist(self, path: str | Path) -> Self:
        """Persist the object to a file or directory.

        Args:
            path (str | Path): The path to save the object.

        Returns:
            Self: The current instance of the object.
        """
        p = Path(path)
        out = self.model_dump_json()

        # Generate a timestamp in the format YYYYMMDD_HHMMSS
        timestamp = datetime.now().strftime("%Y%m%d")

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
    def from_persistent(cls, path: str | Path) -> Self:
        """Load the object from a file.

        Args:
            path (str | Path): The path to load the object from.

        Returns:
            Self: The current instance of the object.
        """
        return cls.model_validate_json(safe_text_read(path))


class ModelHash(Base):
    """Class that provides a hash value for the object.

    This class includes a method to calculate a hash value for the object based on its JSON representation.
    """

    def __hash__(self) -> int:
        """Calculates a hash value for the object based on its model_dump_json representation.

        Returns:
            int: The hash value of the object.
        """
        return hash(self.model_dump_json())


class UpdateFrom(Base):
    """Class that provides a method to update the object from another object.

    This class includes methods to update the current object with the attributes of another object.
    """

    def update_pre_check(self, other: Self) -> Self:
        """Pre-check for updating the object from another object.

        Args:
            other (Self): The other object to update from.

        Returns:
            Self: The current instance after pre-check.

        Raises:
            TypeError: If the other object is not of the same type.
        """
        if not isinstance(other, self.__class__):
            raise TypeError(f"Cannot update from a non-{self.__class__.__name__} instance.")

        return self

    @abstractmethod
    def update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance.

        This method should be implemented by subclasses to provide the specific update logic.

        Args:
            other (Self): The other instance to update from.

        Returns:
            Self: The current instance with updated attributes.
        """

    @final
    def update_from(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance.

        Args:
            other (Self): The other instance to update from.

        Returns:
            Self: The current instance with updated attributes.
        """
        return self.update_pre_check(other).update_from_inner(other)


class ResolveUpdateConflict(Base):
    """Class that provides a method to update the object from another object.

    This class includes a method to resolve conflicts when updating the object from another object.
    """

    @abstractmethod
    def resolve_update_conflict(self, other: Self) -> str:
        """Resolve the update conflict between two objects.

        Args:
            other (Self): The other object to resolve the update conflict with.

        Returns:
            str: The resolved update conflict.
        """


class Introspect(Base):
    """Class that provides a method to introspect the object.

    This class includes a method to perform internal introspection of the object.
    """

    @abstractmethod
    def introspect(self) -> str:
        """Internal introspection of the object.

        Returns:
            str: The internal introspection of the object.
        """


class WithBriefing(Named, Described):
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


class UnsortGenerate(GenerateJsonSchema):
    """Class that provides a reverse JSON schema of the model.

    This class overrides the sorting behavior of the JSON schema generation to maintain the original order.
    """

    def sort(self, value: JsonSchemaValue, parent_key: str | None = None) -> JsonSchemaValue:
        """Not sort.

        Args:
            value (JsonSchemaValue): The JSON schema value to sort.
            parent_key (str | None): The parent key of the JSON schema value.

        Returns:
            JsonSchemaValue: The JSON schema value without sorting.
        """
        return value


class WithFormatedJsonSchema(Base):
    """Class that provides a formatted JSON schema of the model.

    This class includes a method to generate a formatted JSON schema of the model.
    """

    @classmethod
    def formated_json_schema(cls) -> str:
        """Get the JSON schema of the model in a formatted string.

        Returns:
            str: The JSON schema of the model in a formatted string.
        """
        return orjson.dumps(
            cls.model_json_schema(schema_generator=UnsortGenerate),
            option=orjson.OPT_INDENT_2,
        ).decode()


class CreateJsonObjPrompt(WithFormatedJsonSchema):
    """Class that provides a prompt for creating a JSON object.

    This class includes a method to create a prompt for creating a JSON object based on the model's schema and a requirement.
    """

    @classmethod
    @overload
    def create_json_prompt(cls, requirement: List[str]) -> List[str]: ...
    @classmethod
    @overload
    def create_json_prompt(cls, requirement: str) -> str: ...
    @classmethod
    def create_json_prompt(cls, requirement: str | List[str]) -> str | List[str]:
        """Create the prompt for creating a JSON object with given requirement.

        Args:
            requirement (str | List[str]): The requirement for the JSON object.

        Returns:
            str | List[str]: The prompt for creating a JSON object with given requirement.
        """
        if isinstance(requirement, str):
            return TEMPLATE_MANAGER.render_template(
                configs.templates.create_json_obj_template,
                {"requirement": requirement, "json_schema": cls.formated_json_schema()},
            )
        return [
            TEMPLATE_MANAGER.render_template(
                configs.templates.create_json_obj_template,
                {"requirement": r, "json_schema": cls.formated_json_schema()},
            )
            for r in requirement
        ]


class InstantiateFromString(Base):
    """Class that provides a method to instantiate the class from a string.

    This class includes a method to instantiate the class from a JSON string representation.
    """

    @classmethod
    def instantiate_from_string(cls, string: str) -> Self | None:
        """Instantiate the class from a string.

        Args:
            string (str): The string to instantiate the class from.

        Returns:
            Self | None: The instance of the class or None if the string is not valid.
        """
        obj = JsonCapture.convert_with(string, cls.model_validate_json)
        logger.debug(f"Instantiate `{cls.__name__}` from string, {'Failed' if obj is None else 'Success'}.")
        return obj


class ProposedAble(CreateJsonObjPrompt, InstantiateFromString):
    """Class that provides a method to propose a JSON object based on the requirement.

    This class combines the functionality to create a prompt for a JSON object and instantiate it from a string.
    """


class SketchedAble(ProposedAble, Display):
    """Class that provides a method to scratch the object.

    This class combines the functionality to propose a JSON object, instantiate it from a string, and display it.
    """


class ProposedUpdateAble(SketchedAble, UpdateFrom, ABC):
    """Make the obj can be updated from the proposed obj in place.

    This class provides the ability to update an object in place from a proposed object.
    """


class FinalizedDumpAble(Base):
    """Class that provides a method to finalize the dump of the object.

    This class includes methods to finalize the JSON representation of the object and dump it to a file.
    """

    def finalized_dump(self) -> str:
        """Finalize the dump of the object.

        Returns:
            str: The finalized dump of the object.
        """
        return self.model_dump_json()

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
        return TEMPLATE_MANAGER.render_template(
            configs.templates.dependencies_template,
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


class Vectorizable(Base):
    """Class that prepares the vectorization of the model.

    This class includes methods to prepare the model for vectorization, ensuring it fits within a specified token length.
    """

    def _prepare_vectorization_inner(self) -> str:
        return rtoml.dumps(self.model_dump())

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
        max_length = max_length or configs.embedding.max_sequence_length
        chunk = self._prepare_vectorization_inner()
        if max_length and (length := token_counter(text=chunk)) > max_length:
            logger.error(err := f"Chunk exceeds maximum sequence length {max_length}, got {length}, see {chunk}")
            raise ValueError(err)

        return chunk


class ScopedConfig(Base):
    """Class that manages a scoped configuration.

    This class includes attributes and methods to manage configuration settings scoped to the instance.
    """

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

    llm_tpm: Optional[PositiveInt] = None
    """The tokens per minute of the LLM model."""

    llm_rpm: Optional[PositiveInt] = None
    """The requests per minute of the LLM model."""

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
            other (ScopedConfig): Another instance from which to copy attribute values.

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
            others (Union[ScopedConfig, Iterable[ScopedConfig]]): Another instance or iterable of instances from which to copy attribute values.

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
        return self


class Patch[T](ProposedAble):
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


class SequencePatch[T](ProposedUpdateAble):
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
