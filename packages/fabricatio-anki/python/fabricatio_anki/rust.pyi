"""Rust bindings for the Rust API of fabricatio-anki."""







from typing import List, Optional, Tuple, Self

class DeckBuilder:
    """A builder for creating Anki decks with models and notes."""
    
    def __init__(self) -> None:
        """Create a new DeckBuilder instance."""
        ...
    
    def create_deck(self, deck_id: int, name: str, description: str) -> Self:
        """Create a new deck with the given ID, name, and description.
        
        Args:
            deck_id: Unique identifier for the deck
            name: Name of the deck
            description: Description of the deck
            
        Returns:
            Self for method chaining
        """
        ...
    
    def create_model(
        self,
        model_id: int,
        name: str,
        fields: List[str],
        templates: List[Tuple[str, str, str]],
        css: Optional[str] = None
    ) -> Self:
        """Create a new model with the given parameters.
        
        Args:
            model_id: Unique identifier for the model
            name: Name of the model
            fields: List of field names
            templates: List of (name, question_format, answer_format) tuples
            css: Optional path to CSS file
            
        Returns:
            Self for method chaining
            
        Raises:
            IOError: If CSS file cannot be read
        """
        ...
    
    def add_note(self, model_id: int, fields: List[str]) -> Self:
        """Add a note to the deck using the specified model.
        
        Args:
            model_id: ID of the model to use
            fields: List of field values
            
        Returns:
            Self for method chaining
            
        Raises:
            KeyError: If model not found
            ValueError: If note creation fails
            RuntimeError: If no deck has been created
        """
        ...
    
    def write_to_file(self, filename: str) -> None:
        """Write the deck to a file.
        
        Args:
            filename: Path to the output file
            
        Raises:
            IOError: If file cannot be written
            RuntimeError: If no deck to write
        """
        ...
    
    def write_package_to_file(self, filename: str, media_files: List[str]) -> None:
        """Write the deck as a package with media files.
        
        Args:
            filename: Path to the output file
            media_files: List of media file paths
            
        Raises:
            ValueError: If package creation fails
            IOError: If file cannot be written
            RuntimeError: If no deck to write
        """
        ...