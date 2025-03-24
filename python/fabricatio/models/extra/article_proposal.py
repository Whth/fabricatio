"""A structured proposal for academic paper development with core research elements."""

from typing import Dict, List

from fabricatio.models.generic import AsPrompt, CensoredAble, Display, PersistentAble, WithRef


class ArticleProposal(CensoredAble, Display, WithRef[str], AsPrompt, PersistentAble):
    """Structured proposal for academic paper development with core research elements.

    Guides LLM in generating comprehensive research proposals with clearly defined components.
    """

    language: str
    """The language in which the article is written. This should align with the language specified in the article briefing."""

    title: str
    """The title of the academic paper, formatted in Title Case."""

    focused_problem: List[str]
    """A list of specific research problems or questions that the paper aims to address."""

    technical_approaches: List[str]
    """A list of technical approaches or methodologies used to solve the research problems."""

    research_methods: List[str]
    """A list of methodological components, including techniques and tools utilized in the research."""

    research_aim: List[str]
    """A list of primary research objectives that the paper seeks to achieve."""

    def _as_prompt_inner(self) -> Dict[str, str]:
        return {"ArticleBriefing": self.referenced, "ArticleProposal": self.display()}
