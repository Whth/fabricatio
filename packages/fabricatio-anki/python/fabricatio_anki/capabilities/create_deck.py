"""Provide capabilities for creating a deck of cards."""
from fabricatio_core.capabilities.propose import Propose

from fabricatio_anki.models.deck_model import Deck


class CreateDeck(Propose):
    """Create a deck of cards."""


    async def create_deck(self)->Deck:
        ...
