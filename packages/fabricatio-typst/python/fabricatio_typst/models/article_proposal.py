"""A structured proposal for academic paper development with core research elements."""

from fabricatio_capabilities.models.generic import (
    AsPrompt,
    PersistentAble,
    WordCount,
)
from fabricatio_core.models.generic import (
    Described,
    Language,
    SketchedAble,
    Titled,
)
from pydantic import Field

from fabricatio_typst.models.artifacts import ArticleArtifacts


class ArticleProposal(SketchedAble, AsPrompt, PersistentAble, WordCount, Described, Titled, Language):
    """Structured proposal for academic paper development with core research elements.

    Guides LLM in generating comprehensive research proposals with clearly defined components.
    """

    artifacts: ArticleArtifacts = Field(default_factory=ArticleArtifacts)
    """Shared pipeline artifacts (briefing, proposal, outline)."""

    focused_problem: list[str]
    """A list of specific research problems or questions that the paper aims to address."""

    technical_approaches: list[str]
    """A list of technical approaches or methodologies used to solve the research problems."""

    research_methods: list[str]
    """A list of methodological components, including techniques and tools utilized in the research."""

    research_aim: list[str]
    """A list of primary research objectives that the paper seeks to achieve."""

    literature_review: list[str]
    """A list of key references and literature that support the research context and background."""

    expected_outcomes: list[str]
    """A list of anticipated results or contributions that the research aims to achieve."""

    keywords: list[str]
    """A list of keywords that represent the main topics and focus areas of the research."""

    description: str = Field(alias="abstract")
    """A concise summary of the research proposal, outlining the main points and objectives."""

    def _as_prompt_inner(self) -> dict[str, str]:
        return {
            "ArticleBriefing": self.artifacts.access_briefing(),
            "ArticleProposal": self.display(),
        }
