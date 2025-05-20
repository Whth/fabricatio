"""A structured proposal for academic paper development with core research elements."""

from typing import Dict, List

from fabricatio.models.generic import (
    AsPrompt,
    Described,
    Language,
    PersistentAble,
    SketchedAble,
    Titled,
    WithRef,
    WordCount,
)
from pydantic import Field


class ArticleProposal(SketchedAble, WithRef[str], AsPrompt, PersistentAble, WordCount, Described, Titled, Language):
    """Structured proposal for academic paper development with core research elements.

    Guides LLM in generating comprehensive research proposals with clearly defined components.
    """

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

    description: str = Field(alias="abstract")
    """A concise summary of the research proposal, outlining the main points and objectives."""

    def _as_prompt_inner(self) -> Dict[str, str]:
        return {
            "ArticleBriefing": self.referenced,
            "ArticleProposal": self.display(),
        }
