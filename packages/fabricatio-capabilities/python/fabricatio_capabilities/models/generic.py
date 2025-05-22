"""This module defines generic classes for models in the Fabricatio library, providing a foundation for various model functionalities."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Self, Type, Union, final, overload

import ujson
from fabricatio_core.fs import dump_text
from fabricatio_core.fs.readers import safe_text_read
from fabricatio_core.journal import logger
from fabricatio_core.models.generic import Base, Display, ProposedAble, UnsortGenerate
from fabricatio_core.rust import CONFIG, TEMPLATE_MANAGER, blake3_hash
from fabricatio_core.utils import ok
from pydantic import (
    BaseModel,
    PrivateAttr,
)


class AsPrompt:
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
            CONFIG.templates.as_prompt_template,
            self._as_prompt_inner(),
        )

    @abstractmethod
    def _as_prompt_inner(self) -> Dict[str, str]:
        """Generate the inner part of the prompt.

        This method should be implemented by subclasses to provide the specific data for the prompt.

        Returns:
            Dict[str, str]: The data for the prompt.
        """


class WithRef[T](Base, ABC):
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
    def update_ref[S: WithRef](self: S, reference: T) -> S:
        ...

    @overload
    def update_ref[S: WithRef](self: S, reference: "WithRef[T]") -> S:
        ...

    @overload
    def update_ref[S: WithRef](self: S, reference: None = None) -> S:
        ...

    def update_ref[S: WithRef](self: S, reference: Union[T, "WithRef[T]", None] = None) -> S:
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


class ModelHash(Base, ABC):
    """Class that provides a hash value for the object.

    This class includes a method to calculate a hash value for the object based on its JSON representation.
    """

    def __hash__(self) -> int:
        """Calculates a hash value for the object based on its model_dump_json representation.

        Returns:
            int: The hash value of the object.
        """
        return hash(self.model_dump_json())


class UpdateFrom(ABC):
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


class SketchedAble(ProposedAble, Display, ABC):
    """Class that provides a method to scratch the object.

    This class combines the functionality to propose a JSON object, instantiate it from a string, and display it.
    """


class ProposedUpdateAble(SketchedAble, UpdateFrom, ABC):
    """Make the obj can be updated from the proposed obj in place.

    This class provides the ability to update an object in place from a proposed object.
    """


class FinalizedDumpAble(Base, ABC):
    """Class that provides a method to finalize the dump of the object.

    This class includes methods to finalize the JSON representation of the object and dump it to a file.
    """

    def finalized_dump(self) -> str:
        """Finalize the dump of the object.

        Returns:
            str: The finalized dump of the object.
        """
        return self.model_dump_json(indent=1, by_alias=True)

    def finalized_dump_to(self, path: str | Path) -> Self:
        """Finalize the dump of the object to a file.

        Args:
            path (str | Path): The path to save the finalized dump.

        Returns:
            Self: The current instance of the object.
        """
        dump_text(path, self.finalized_dump())
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
