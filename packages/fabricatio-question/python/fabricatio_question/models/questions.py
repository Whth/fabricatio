"""Provide question models for interactive user input."""

from typing import List

import questionary
from fabricatio_core.models.generic import SketchedAble


class SelectionQuestion(SketchedAble):
    """Interactive selection question for single or multiple choice prompts."""

    q: str
    """The question text to display to the user."""
    option: List[str]
    """List of available options for the user to choose from."""

    async def single(self) -> str:
        """Present a single-choice selection question to the user.

        Returns:
            The selected option as a string.
        """
        return await questionary.select(self.q, choices=self.option).ask_async()

    async def multiple(self, k: int = 0) -> List[str]:
        """Present a multiple-choice selection question to the user.

        Args:
            k: Number of selections required. If k=0, any number is allowed.

        Returns:
            List of selected options as strings.
        """
        # Use 'questionary.checkbox' with validation based on k value
        if k == 0:
            selected_options = await questionary.checkbox(self.q, choices=self.option).ask_async()
        else:
            selected_options = await questionary.checkbox(
                self.q,
                choices=self.option,
                validate=lambda selections: True if len(selections) == k else f"Please select exactly {k} options.",
            ).ask_async()
        return selected_options
