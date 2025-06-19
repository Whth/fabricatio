"""Generates topic analysis for Anki flashcards.

This module provides the GenerateAnalysis class, which extends the Propose class
to generate structured topic analysis using a template-based approach.
"""

from typing import List, Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs

from fabricatio_anki.config import anki_config
from fabricatio_anki.models.topic_analysis import TopicAnalysis


class GenerateAnalysis(Propose):
    """This class provides functionality to generate topic analysis for Anki flashcards.

    It extends the Propose class and uses the TopicAnalysis model to structure the output.
    """

    @overload
    async def generate_analysis(
        self, topic: str, **kwargs: Unpack[ValidateKwargs[TopicAnalysis]]
    ) -> None | TopicAnalysis: ...

    @overload
    async def generate_analysis(
        self, topic: List[str], **kwargs: Unpack[ValidateKwargs[TopicAnalysis]]
    ) -> List[TopicAnalysis | None] | None: ...

    async def generate_analysis(
        self, topic: str | List[str], **kwargs: Unpack[ValidateKwargs[TopicAnalysis]]
    ) -> None | TopicAnalysis | List[TopicAnalysis | None] | List[TopicAnalysis]:
        """Generates an analysis for the given topic(s) using a template-based approach.

        This method renders a template with the provided topic information and proposes
        a TopicAnalysis based on the generated content.

        Args:
            topic (str or List[str]): A string or list of strings representing
                the topic(s) to analyze.
            **kwargs (Unpack[ValidateKwargs[TopicAnalysis]]): Additional keyword arguments
                for validation and customization.

        Returns:
            None | TopicAnalysis | List[TopicAnalysis | None]: Returns None, a TopicAnalysis
                object, or a list of TopicAnalysis objects depending on input.
        """
        return await self.propose(
            TopicAnalysis,
            TEMPLATE_MANAGER.render_template(
                anki_config.generate_topic_analysis_template,
                [{"topic": t} for t in topic] if isinstance(topic, list) else {"topic": topic},
            ),
            **kwargs,
        )
