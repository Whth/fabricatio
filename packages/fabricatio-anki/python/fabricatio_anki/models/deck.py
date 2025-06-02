"""Module for defining data models and constants related to Anki decks."""

from enum import StrEnum
from pathlib import Path
from time import perf_counter_ns
from typing import List, Optional, Self, Set, Type

from fabricatio_capabilities.models.generic import Patch
from fabricatio_core.models.generic import Named, SketchedAble, WithBriefing
from pydantic import BaseModel

from fabricatio_anki.models.template import Template
from fabricatio_anki.rust import save_metadata


class Constants(StrEnum):
    """Constants used across the module to represent various keys and directories."""

    MEDIA = "media"
    TEMPLATES = "templates"
    MODEL = "model"
    FIELDS = "fields"
    DECK = "deck"
    MODEL_ID = "model_id"


class Model(SketchedAble, Named):
    """Represents a model in Anki which contains fields and templates.

    Attributes:
        fields (List[str]): The list of field names in the model.
        templates (List[Template]): The list of templates associated with the model.
    """

    fields: List[str]
    """List of field names that define the data structure for this model.
    Each field represents a piece of information that can be filled in when creating cards,
    such as 'Front', 'Back', 'Extra', etc. These fields are used as placeholders
    in the template HTML and determine what data can be stored for each note."""

    templates: List[Template]
    """List of card templates associated with this model.
    Each template defines how the fields should be displayed on the front and back
    of a card, including the HTML structure and CSS styling. A model can have
    multiple templates to create different card variations from the same field data."""

    def save_to(self, parent_dir: Path | str) -> Self:
        """Saves the model's metadata and its templates to the specified directory.

        Args:
            parent_dir (Path | str): Directory where the model should be saved.

        Returns:
            Self: The instance of the model after saving.
        """
        model_root = Path(parent_dir) / self.name
        save_metadata(
            model_root, Constants.FIELDS, {Constants.MODEL_ID: perf_counter_ns(), Constants.FIELDS: self.fields}
        )

        for t in self.templates:
            t.save_to(model_root / Constants.TEMPLATES)
        return self


class Deck(SketchedAble, WithBriefing):
    """Represents an Anki deck which contains multiple models.

    Attributes:
        author (str): Author of the deck. Defaults to 'Anonymous'.
        models (List[Model]): The list of models included in the deck.
    """

    author: str = "Anonymous"
    """The author or creator of this Anki deck.
    This field identifies who created the deck and is displayed in the deck metadata.
    Defaults to 'Anonymous' if no author is specified."""

    models: List[Model]
    """List of card models that define the structure and appearance of cards in this deck.
    Each model contains fields and templates that determine how information is organized
    and displayed. A deck can contain multiple models to support different types of cards
    or study materials within the same deck."""

    def save_to(self, path: Path | str) -> Self:
        """Saves all models in the deck to the specified path and writes deck metadata.

        Args:
            path (Path | str): Directory where the deck should be saved.

        Returns:
            Self: The instance of the deck after saving.
        """
        models_root = Path(path) / Constants.MODEL

        for m in self.models:
            m.save_to(models_root)

        save_metadata(
            models_root, Constants.DECK, {Constants.MODEL_ID: perf_counter_ns(), **self.model_dump(exclude={"models"})}
        )

        return self


class ModelMetaData(WithBriefing, Patch[Deck]):
    """Patch class for updating metadata of a deck model.

    This class is used to apply metadata updates to a Deck instance,
    while excluding specific fields from the update process.
    """

    @staticmethod
    def excluded_fields() -> Set[str]:
        """Returns a set of fields that should be excluded from updates.

        These fields are intentionally not modified when applying metadata patches.

        Returns:
            Set[str]: A set containing the names of excluded fields.
        """
        return {"models", "author"}

    @staticmethod
    def ref_cls() -> Optional[Type[BaseModel]]:
        """Returns the reference class for this patch.

        Determines which class this patch can be applied to.

        Returns:
            Optional[Type[BaseModel]]: The Deck class.
        """
        return Deck
