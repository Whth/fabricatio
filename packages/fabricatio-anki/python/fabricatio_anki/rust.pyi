"""Rust bindings for the Rust API of fabricatio-anki."""

from typing import List, Optional


class DeckConfig:
    """Configuration for an Anki deck.

    Attributes:
        name (str): The name of the deck.
        description (str): A description of the deck.
        deck_id (int): A unique identifier for the deck.
        author (Optional[str]): The author of the deck, if specified.
    """
    name: str
    description: str
    deck_id: int
    author: Optional[str]


class ModelConfig:
    """Configuration for a model in Anki.

    Attributes:
        model_id (int): A unique identifier for the model.
        fields (List[str]): A list of field names used in the model.
    """
    model_id: int
    fields: List[str]


class TemplateConfig:
    """Configuration for a template in Anki.

    Attributes:
        name (str): The name of the template.
        front_html (str): HTML content for the front side of the card.
        back_html (str): HTML content for the back side of the card.
        style_css (str): CSS styling for the template.
    """
    name: str
    front_html: str
    back_html: str
    style_css: str


class ModelData:
    """Data structure containing model configuration and templates.

    Attributes:
        config (ModelConfig): The model's configuration.
        templates (List[TemplateConfig]): A list of templates associated with the model.
        media_files (List[str]): A list of media file names used by the model.
    """
    config: ModelConfig
    templates: List[TemplateConfig]
    media_files: List[str]


class AnkiDeckLoader:
    def __init__(self, project_path: str) -> None:
        """Initialize the AnkiDeckLoader with the given project path.

        Args:
            project_path (str): The path to the Anki deck project directory.
        """

    def load_deck_config(self) -> DeckConfig:
        """Load the deck configuration from the project.

        Returns:
            DeckConfig: The loaded deck configuration.
        """

    def load_model_data(self, model_name: str) -> ModelData:
        """Load the model data for the specified model.

        Args:
            model_name (str): The name of the model to load.

        Returns:
            ModelData: The loaded model data.
        """

    def get_available_models(self) -> List[str]:
        """Get a list of available models in the project.

        Returns:
            List[str]: A list of model names.
        """

    def load_csv_data(self, model_name: str) -> List[List[str]]:
        """Load the CSV data for the specified model.

        Args:
            model_name (str): The name of the model to load CSV data for.

        Returns:
            List[List[str]]: The loaded CSV data.
        """

    def build_deck(self) -> None:
        """Build the complete Anki deck from the project data."""

    def export_deck(self, output_path: str) -> None:
        """Export the built Anki deck to the specified output path.

        Args:
            output_path (str): The path to export the deck to.
        """

    def create_project_template(self, project_path: str) -> None:
        """Create a new Anki deck project template at the specified path.

        Args:
            project_path (str): The path to create the project template at.
        """
