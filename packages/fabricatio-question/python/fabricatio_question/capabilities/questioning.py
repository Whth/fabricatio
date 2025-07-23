"""Questioning capabilities module for interactive user prompts.

This module provides the Questioning class which extends the Propose capability
to create interactive selection prompts for users.
"""

from typing import List, Unpack

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import GenerateKwargs
from fabricatio_core.utils import ok

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
        # let llm draft the question that will be asked to the user
        question: SelectionQuestion = ok(
            await self.propose(
                SelectionQuestion,
                TEMPLATE_MANAGER.render_template(
                    question_config.selection_template, {"q": q}
                ),  # create the generation prompt
                **kwargs,
            ),
            "Failed to generate selection question.",
        )

        if k == 1:
            return await question.single()

        return await question.multiple(k)

    async def selection_string(self, q: str, k: int = 1, **kwargs: Unpack[GenerateKwargs]) -> str:
        """Generates a selection question and returns the formatted response with selected indices.

        This method creates a selection question using the internal propose method to generate
        options and then gathers user input for either a single or multiple selections. The result
        is rendered using a template that includes the question topic, options, and selections.

        Args:
            q (str): The prompt text used to generate the selection question.
            k (int, optional): The number of selections allowed. Defaults to 1.
                If k=1, a single selection is made. If k>1, multiple selections are made up to k.
            **kwargs: Additional keyword arguments passed to the LLM generation process.

        Returns:
            str: A formatted string representing the rendered selection question along with
                the indices of the selected options.

        Raises:
            Exception: If question generation or user interaction encounters an error.
        """
        question: SelectionQuestion = ok(
            await self.propose(
                SelectionQuestion,
                TEMPLATE_MANAGER.render_template(
                    question_config.selection_template, {"q": q}
                ),  # create the generation prompt
                **kwargs,
            ),
            "Failed to generate selection question.",
        )

        if k == 1:
            selection = await question.single()
            selected_indices = [question.option.index(selection)]
        else:
            selected_indices = [question.option.index(s) for s in await question.multiple(k)]

        return TEMPLATE_MANAGER.render_template(
            question_config.selection_display_template,
            {"topic": question.q, "options": question.option, "selections": [selected_indices]},
        )
