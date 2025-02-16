"""This module defines generic classes for models in the Fabricatio library."""

from pathlib import Path
from typing import List, Self

import orjson
from fabricatio.fs.readers import magika
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class Base(BaseModel):
    """Base class for all models with Pydantic configuration."""

    model_config = ConfigDict(use_attribute_docstrings=True)


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


class WithJsonExample(Base):
    """Class that provides a JSON schema for the model."""

    @classmethod
    def json_example(cls) -> str:
        """Return a JSON example for the model.

        Returns:
            str: A JSON example for the model.
        """
        return orjson.dumps(
            {field_name: field_info.description for field_name, field_info in cls.model_fields.items()},
            option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
        ).decode()


class WithDependency(Base):
    """Class that manages file dependencies."""

    dependencies: List[str] = Field(default_factory=list)
    """The file dependencies of the task, a list of file paths."""

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

    def generate_prompt(self) -> str:
        """Generate a prompt for the task based on the file dependencies.

        Returns:
            str: The generated prompt for the task.
        """
        contents = [Path(d).read_text("utf-8") for d in self.dependencies]
        recognized = [magika.identify_path(c) for c in contents]
        out = ""
        for r, p, c in zip(recognized, self.dependencies, contents, strict=False):
            out += f"---\n\n> {p}\n```{r.dl.ct_label}\n{c}\n```\n\n"
        return out
