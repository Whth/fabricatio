"""Questioning capabilities module for interactive user prompts.

This module provides the Questioning class which extends the Propose capability
to create interactive selection prompts for users.
"""

from typing import List, Unpack

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import GenerateKwargs

from fabricatio_question.config import question_config
from fabricatio_question.models.questions import SelectionQuestion


class Questioning(Propose):
    """A capability class for creating interactive user selection prompts.

    This class extends the Propose capability to generate and present
    selection questions to users, allowing for single or multiple choice
    interactions.
    """

    async def selection(self, q: str, k: int = 1, **kwargs: Unpack[GenerateKwargs]) -> str | List[str]:
        """Create an interactive selection prompt for the user.

        This method first uses the LLM to generate a well-structured selection question
        based on the provided prompt, then presents it interactively to the user.
        The question can be configured for single or multiple selections.

        Args:
            q (str): The question or prompt text that will be used to generate
                the interactive selection question.
            k (int, optional): The number of selections allowed. Defaults to 1.
                If k=1, returns a single string. If k>1, returns a list of strings.
            **kwargs: Additional keyword arguments passed to the LLM generation process,
                such as model parameters, temperature, etc.

        Returns:
            str | List[str]: If k=1, returns a single selected string.
                If k>1, returns a list of selected strings up to k items.

        Raises:
            Exception: If the LLM generation fails or user interaction encounters an error.
        """
        q = await self.propose(
            SelectionQuestion,
            TEMPLATE_MANAGER.render_template(
                question_config.selection_template, {"q": q}
            ),  # create the generation prompt
            **kwargs,
        )  # let llm draft the question that will be asked to the user

        if k == 1:
            return await q.single()

        return await q.multiple(k)
