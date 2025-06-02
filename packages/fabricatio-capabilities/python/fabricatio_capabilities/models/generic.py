"""This module defines generic classes for models in the Fabricatio library, providing a foundation for various model functionalities."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Self, Set, Type, final

import ujson
from fabricatio_core.fs import dump_text
from fabricatio_core.fs.readers import safe_text_read
from fabricatio_core.journal import logger
from fabricatio_core.models.generic import Base, ProposedAble, SketchedAble, UnsortGenerate
from fabricatio_core.rust import blake3_hash
from pydantic import (
    BaseModel,
)


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
    """A generic patch class that allows field-based updates to target objects.

    This class provides functionality to:
    1. Apply patches to update object fields
    2. Generate dictionary representations of patches
    3. Handle JSON schema generation with reference class integration

    The patch system works by comparing fields between the patch and target object,
    ensuring type safety while enabling flexible data transformations.

    Type Parameters:
        T: The type of object this patch can be applied to (typically a Pydantic model)

    Example:
        >>> from pydantic import BaseModel
        >>> class MyModel(BaseModel):
        ...     name: str
        ...     value: int
        ...
        >>> class MyPatch(Patch[MyModel], BaseModel):
        ...     name: str
        ...
        >>> target = MyModel(name="old", value=42)
        >>> patch = MyPatch(name="new")
        >>> updated = patch.apply(target)
        >>> assert updated.name == "new" and updated.value == 42
    """

    def apply(self, other: T) -> T:
        """Apply the patch to another instance.

        This method copies all fields from the patch to the target object,
        ensuring that only existing fields are modified.

        Args:
            other (T): The instance to apply the patch to.

        Returns:
            T: The instance with the patch applied.

        Raises:
            ValueError: If a field in the patch is not found in the target instance.

        Example:
            >>> class User(BaseModel):
            ...     name: str
            ...     age: int
            ...
            >>> class UserPatch(Patch[User], BaseModel):
            ...     name: Optional[str] = None
            ...
            >>> user = User(name="Alice", age=30)
            >>> patch = UserPatch(name="Bob")
            >>> updated_user = patch.apply(user)
            >>> print(updated_user.name)  # Output: Bob
        """
        for field in self.__class__.model_fields:
            if not hasattr(other, field):
                raise ValueError(f"{field} not found in {other}, are you applying to the wrong type?")
            setattr(other, field, getattr(self, field))
        return other

    def as_kwargs(self) -> Dict[str, Any]:
        """Get the kwargs of the patch.

        Converts the patch into a dictionary suitable for use with **kwargs syntax.

        Returns:
            Dict[str, Any]: A dictionary representation of the patch.

        Example:
            >>> class ConfigPatch(Patch[MyModel], BaseModel):
            ...     timeout: int
            ...     retries: int
            ...
            >>> patch = ConfigPatch(timeout=30, retries=3)
            >>> kwargs = patch.as_kwargs()
            >>> print(kwargs)  # {'timeout': 30, 'retries': 3}
        """
        return self.model_dump()

    @staticmethod
    def ref_cls() -> Optional[Type[BaseModel]]:
        """Get the reference class of the model.

        This can be overridden in subclasses to provide a reference model for schema documentation.

        Returns:
            Optional[Type[BaseModel]]: The reference class if available, None otherwise.
        """
        return None

    @staticmethod
    def excluded_fields() -> Set[str]:
        """Get a list of fields to exclude from the patch.

        This can be overridden in subclasses to provide a list of fields that should be excluded from the patch.

        Returns:
            Set[str]: A list of fields to exclude from the patch.
        """
        return set()

    @classmethod
    def formated_json_schema(cls) -> str:
        """Get the JSON schema of the model in a formatted string.

        Generates a JSON schema with optional documentation inherited from a reference class.
        This is particularly useful for API documentation and validation systems.

        Returns:
            str: The JSON schema of the model in a formatted string.

        Example:
            >>> class MyBaseModel(BaseModel):
            ...     id: int
            ...     name: str
            ...
            >>> class MyPatch(Patch[MyBaseModel], BaseModel):
            ...     @staticmethod
            ...     def ref_cls():
            ...         return MyBaseModel
            ...
            >>> print(MyPatch.formated_json_schema())
            {
              "title": "MyBaseModel",
              "type": "object",
              "properties": {
                "id": {
                  "type": "integer",
                  "description": "..."
                },
                "name": {
                  "type": "string",
                  "description": "..."
                }
              },
              "required": ["id", "name"]
            }
        """
        my_schema = cls.model_json_schema(schema_generator=UnsortGenerate)

        excluded_fields = cls.excluded_fields()

        # drop excluded fields
        for field_name in excluded_fields:
            my_schema["properties"].pop(field_name)
            my_schema["required"].remove(field_name) if field_name in my_schema["required"] else None

        if (ref_cls := cls.ref_cls()) is not None:
            # copy the desc info of each corresponding fields from ref_cls
            for field_name in [f for f in cls.model_fields if f in (set(ref_cls.model_fields) - excluded_fields)]:
                my_schema["properties"][field_name]["description"] = (
                    ref_cls.model_fields[field_name].description or my_schema["properties"][field_name]["description"]
                )
            my_schema["description"] = ref_cls.__doc__
            my_schema["title"] = ref_cls.__name__
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
