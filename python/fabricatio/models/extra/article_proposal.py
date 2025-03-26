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

    literature_review: List[str]
    """A list of key references and literature that support the research context and background."""

    expected_outcomes: List[str]
    """A list of anticipated results or contributions that the research aims to achieve."""

    keywords: List[str]
    """A list of keywords that represent the main topics and focus areas of the research."""

    abstract: str
    """A concise summary of the research proposal, outlining the main points and objectives."""

    min_word_count: int
    """The minimum number of words required for the research proposal."""

    def _as_prompt_inner(self) -> Dict[str, str]:
        return {
            "ArticleBriefing": self.referenced,
            "ArticleProposal": self.display(),
        }
