"""Rust bindings for the Rust API of fabricatio-anki."""


def compile_deck(path: str, output: str) -> None:
    """Compile an Anki deck from a project directory and export it to the specified output path.

    This function serves as the main entry point for compiling Anki deck projects created with
    the fabricatio-anki framework. It takes a project directory containing deck configuration,
    model definitions, templates, and CSV data, then processes all components to generate a
    complete Anki deck file (.apkg format).

    The compilation process includes:
    1. Loading and validating the deck configuration from deck.toml
    2. Processing all model definitions and their associated templates
    3. Reading CSV data files and converting them to Anki notes
    4. Collecting and packaging media files referenced in the templates
    5. Generating the final .apkg file with proper Anki database structure

    Args:
        path (str): The absolute or relative path to the Anki deck project directory.
                   This directory should contain:
                   - deck.toml: Main deck configuration file
                   - models/: Directory containing model definitions and templates
                   - data/: Directory containing CSV files with card data
                   - media/: Directory containing any media files (images, audio, etc.)

        output (str): The absolute or relative path where the compiled .apkg file should be saved.
                     The file will be created if it doesn't exist, or overwritten if it does.
                     The path should include the desired filename with .apkg extension.

    Raises:
        Exception: If the project directory structure is invalid or missing required files.
        Exception: If the deck.toml configuration file contains invalid settings.
        Exception: If any model definition files are malformed or contain syntax errors.
        Exception: If CSV data files have mismatched columns compared to model field definitions.
        Exception: If referenced media files cannot be found or accessed.
        Exception: If the output path is invalid or cannot be written to due to permissions.
        Exception: If there are any internal errors during the Anki deck generation process.

    Example:
        >>> compile_deck("/path/to/my-deck-project", "/path/to/output/my-deck.apkg")

    Note:
        The function will validate the entire project structure before beginning compilation.
        All errors are reported with descriptive messages to help identify and fix issues.
        The generated .apkg file is compatible with Anki 2.1 and later versions.
    """




def create_deck_project(
    path: str,
    deck_name: str | None = None,
    deck_description: str | None = None,
    author: str | None = None,
    model_name: str | None = None,
    fields: list[str] | None = None,
) -> None:
    """Create a new Anki deck project template with the specified configuration.

    This function generates a complete project structure for creating Anki decks using the
    fabricatio-anki framework. It creates all necessary directories, configuration files,
    and sample templates to get started with deck development.

    The generated project follows a structured layout that separates concerns:
    - Deck metadata and global configuration
    - Model definitions with fields and templates
    - Data files for card content
    - Media resources for multimedia content

    Project Structure:
    
    ```text
    anki_deck_project/
    ├── deck.yaml                # Metadata: Deck name, description, author, etc.
    ├── models/                  # Each Model corresponds to a subdirectory
    │   ├── vocab_card/          # Model name
    │   │   ├── fields.yaml      # Field definitions (e.g., Word, Meaning)
    │   │   ├── templates/       # Each template corresponds to a subdirectory
    │   │   │   ├── word_to_meaning/
    │   │   │   │   ├── front.html
    │   │   │   │   ├── back.html
    │   │   │   │   └── style.css
    │   │   │   └── meaning_to_word/
    │   │   │       ├── front.html
    │   │   │       ├── back.html
    │   │   │       └── style.css
    │   │   └── media/            # Optional: Media resources specific to this model
    │   └── grammar_card/
    │       ├── fields.yaml
    │       ├── templates/
    │       └── media/
    ├── data/                     # User data (for template injection)
    │   ├── vocab_card.csv        # CSV format, each line represents a card
    │   └── grammar_card.csv
    └── media/                    # Global media resources (images, audio, etc.)
    ```

    Args:
        path (str): The absolute or relative path where the new project directory should be created.
                   If the directory doesn't exist, it will be created along with any necessary
                   parent directories. If it already exists, the function will add the project
                   structure to it (existing files may be overwritten).

        deck_name (str | None, optional): The display name for the Anki deck that will appear
                                         in Anki's deck browser. If None, defaults to "Sample Deck".
                                         This name can contain spaces and special characters as it's
                                         used for display purposes only.

        deck_description (str | None, optional): A detailed description of the deck's purpose and
                                               content. This appears in Anki's deck information and
                                               helps users understand what the deck contains. If None,
                                               defaults to "A sample Anki deck created with Fabricatio".

        author (str | None, optional): The name or identifier of the deck creator. This information
                                      is embedded in the deck metadata and can be useful for attribution
                                      and contact purposes. If None, defaults to "Generated by Fabricatio".

        model_name (str | None, optional): The name for the default model (note type) that will be
                                          created in the project. Model names should be descriptive
                                          and use underscores instead of spaces (e.g., "basic_card",
                                          "vocabulary_card"). If None, defaults to "basic_card".

        fields (list[str] | None, optional): A list of field names that define the structure of
                                           cards using this model. Each field represents a piece
                                           of information that can be filled in for each card
                                           (e.g., ["Front", "Back"] for basic cards, or
                                           ["Word", "Pronunciation", "Definition", "Example"] for
                                           vocabulary cards). Field names should be descriptive
                                           and avoid special characters. If None, defaults to
                                           ["Front", "Back"] for a basic two-sided card model.

    Raises:
        Exception: If the specified path cannot be created due to permission restrictions or
                  invalid path format (e.g., contains illegal characters for the filesystem).
        Exception: If any of the required directories cannot be created in the project structure.
        Exception: If the configuration files (deck.yaml, fields.yaml) cannot be written due to
                  I/O errors or insufficient disk space.
        Exception: If the template HTML/CSS files cannot be created or written to.
        Exception: If the sample CSV data file cannot be generated.
        Exception: If any parameter contains invalid characters that would cause issues in
                  Anki or the filesystem (e.g., null bytes, extremely long strings).

    Example:
        Basic project creation:
        >>> create_deck_project("/path/to/my-new-deck")
        
        Customized project with specific configuration:
        >>> create_deck_project(
        ...     "/path/to/vocabulary-deck",
        ...     deck_name="French Vocabulary",
        ...     deck_description="Essential French words for beginners",
        ...     author="Language Learning Team",
        ...     model_name="french_vocab",
        ...     fields=["French", "English", "Pronunciation", "Example"]
        ... )

    Note:
        - The function creates a fully functional project template that can be immediately
          compiled into an Anki deck using the compile_deck function.
        - Sample data and templates are provided to demonstrate the structure and can be
          modified or replaced with actual content.
        - The generated templates include basic HTML structure and CSS styling that can
          be customized for different visual presentations.
        - All file paths use forward slashes internally but are converted to the appropriate
          format for the current operating system.
        - The project structure is designed to be version-control friendly, with text-based
          configuration files and clear separation of content and presentation.
    """
