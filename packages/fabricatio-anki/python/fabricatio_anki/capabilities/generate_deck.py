"""Provide capabilities for creating a deck of cards."""
from typing import List, Unpack, Optional

from fabricatio_anki.config import anki_config
from fabricatio_core import TEMPLATE_MANAGER

from fabricatio_anki.models.template import Template
from fabricatio_core.capabilities.propose import Propose

from fabricatio_anki.models.deck import Deck, Model
from fabricatio_core.models.kwargs_types import ValidateKwargs


class GenerateDeck(Propose):
    """Create a deck of cards."""

    async def create_deck(self, name: str, description: Optional[str] = None,
                         **kwargs: Unpack[ValidateKwargs[Optional[Deck]]]) -> Deck | None:
        """Create a deck with the given name and description."""
        return await self.propose(
            Deck,
            TEMPLATE_MANAGER.render_template(
                anki_config.make_deck_creation_proposal_template,
                {"name": name, "description": description}
            ),
            **kwargs,
        )

    async def generate_model(self, name: str, fields: List[str], 
                           **kwargs: Unpack[ValidateKwargs[Optional[Model]]]) -> Model | None:
        """Generate a model with the given name and fields."""
        return await self.propose(
            Model,
            TEMPLATE_MANAGER.render_template(
                anki_config.generate_anki_card_type_template,
                {"name": name, "fields": fields}
            ),
            **kwargs,
        )

    async def generate_template(self, fields: List[str], requirement: str,
                                **kwargs: Unpack[ValidateKwargs[Optional[Template]]]) -> Template | None:
        """Generate a template with the given fields and requirement.
        
        This method creates an Anki card template by proposing a template structure
        based on the provided fields and specific requirements. The template defines
        how the card content will be displayed and formatted.
        
        Args:
            fields (List[str]): A list of field names that will be available in the template.
                               These fields represent the data points that can be used
                               in the card template (e.g., ['Front', 'Back', 'Extra']).
            requirement (str): A detailed description of the template requirements,
                             including formatting specifications, styling preferences,
                             and any special display logic needed for the card template.
            **kwargs: Additional keyword arguments for validation and proposal configuration.
                     These are unpacked from ValidateKwargs[Optional[Template]] and may
                     include validation settings, retry options, or other proposal parameters.
        
        Returns:
            Template | None: A Template object containing the generated template structure
                           if successful, or None if the template generation failed or
                           was rejected during the proposal validation process.
        
        Raises:
            Any exceptions that may be raised by the underlying propose() method,
            including validation errors, template rendering errors, or network-related
            issues during the AI proposal process.
        
        Example:
            >>> generator = GenerateDeck()
            >>> fields = ['Question', 'Answer', 'Hint']
            >>> requirement = "Create a clean template with the question on front and answer on back"
            >>> template = await generator.generate_template(fields, requirement)
        """
        return await self.propose(
            Template,
            TEMPLATE_MANAGER.render_template(
                anki_config.generate_anki_card_type_template,
                { "fields": fields, "requirement": requirement}
                
            ),
             **kwargs,
            
        )