"""Generates topic analysis for Anki flashcards.

This module provides the GenerateAnalysis class, which extends the Propose class
to generate structured topic analysis using a template-based approach.
"""

from typing import List, Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import TASK

from fabricatio_anki.config import anki_config
from fabricatio_anki.models.topic_analysis import TopicAnalysis


class GenerateAnalysis(Propose):
    """This class provides functionality to generate topic analysis for Anki flashcards.

    It extends the Propose class and uses the TopicAnalysis model to structure the output.
    """

    @overload
    async def generate_analysis(
        self, topic: str, send_to: str | None = TASK, **kwargs: Unpack[ValidateKwargs[TopicAnalysis]]
    ) -> TopicAnalysis | None: ...

    @overload
    async def generate_analysis(
        self, topic: List[str], send_to: str | None = TASK, **kwargs: Unpack[ValidateKwargs[TopicAnalysis]]
    ) -> List[TopicAnalysis | None] | None: ...

    async def generate_analysis(
        self, topic: str | List[str], send_to: str | None = TASK, **kwargs: Unpack[ValidateKwargs[TopicAnalysis]]
    ) -> TopicAnalysis | List[TopicAnalysis | None] | List[TopicAnalysis] | None:
        """Generates an analysis for the given topic(s) using a template-based approach.

        Args:
            topic (str or List[str]): A string or list of strings representing
                the topic(s) to analyze.
            send_to: Routing-group variant for the LLM call. Resolved against the agent variant
                registry (see `fabricatio_core.rust`). Defaults to `TASK`; pass `SMOL`/`TINY`/`PLAN`
                to steer to a different model tier.
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
            send_to=send_to,
            **kwargs,
        )
