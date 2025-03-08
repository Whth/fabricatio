"""Extra models for built-in actions."""

from typing import List

from fabricatio.models.generic import Base, Display, FinalizedDumpAble, PrepareVectorization, ProposedAble
from pydantic import Field


class Equation(Base):
    """Structured representation of mathematical equations (including their physical or conceptual meanings)."""

    description: str = Field(...)
    """A concise explanation of the equation's meaning, purpose, and relevance in the context of the research."""

    latex_code: str = Field(...)
    """The LaTeX code used to represent the equation in a publication-ready format."""


class Figure(Base):
    """Structured representation of figures (including their academic significance and explanatory captions)."""

    description: str = Field(...)
    """A detailed explanation of the figure's content and its role in conveying key insights."""

    figure_caption: str = Field(...)
    """The caption accompanying the figure, summarizing its main points and academic value."""

    figure_path: str = Field(...)
    """The file path to the figure"""


class Highlightings(Base):
    """Structured representation of highlighted elements in an academic paper (including equations, algorithms, figures, and tables)."""

    # Academic Achievements Showcase
    highlighted_equations: List[Equation] = Field(default_factory=list)
    """Core mathematical equations that represent breakthroughs in the field, accompanied by explanations of their physical or conceptual significance."""

    highlighted_algorithms: List[str] = Field(default_factory=list)
    """Pseudocode for key algorithms, annotated to highlight innovative components."""

    highlighted_figures: List[Figure] = Field(default_factory=list)
    """Critical diagrams or illustrations, each accompanied by a caption explaining their academic importance."""

    highlighted_tables: List[str] = Field(default_factory=list)
    """Important data tables, annotated to indicate statistical significance or other notable findings."""


class ArticleEssence(ProposedAble, Display, PrepareVectorization):
    """Structured representation of the core elements of an academic paper(providing a comprehensive digital profile of the paper's essential information)."""

    # Basic Metadata
    title: str = Field(...)
    """The full title of the paper, including any subtitles if applicable."""

    authors: List[str] = Field(default_factory=list)
    """A list of the paper's authors, typically in the order of contribution."""

    keywords: List[str] = Field(default_factory=list)
    """A list of keywords that summarize the paper's focus and facilitate indexing."""

    publication_year: int = Field(None)
    """The year in which the paper was published."""

    # Core Content Elements
    domain: List[str] = Field(default_factory=list)
    """The research domains or fields addressed by the paper (e.g., ['Natural Language Processing', 'Computer Vision'])."""

    abstract: str = Field(...)
    """A structured abstract that outlines the research problem, methodology, and conclusions in three distinct sections."""

    core_contributions: List[str] = Field(default_factory=list)
    """Key academic contributions that distinguish the paper from prior work in the field."""

    technical_novelty: List[str] = Field(default_factory=list)
    """Specific technical innovations introduced by the research, listed as individual points."""

    # Academic Discussion Dimensions
    research_problem: str = Field("")
    """A clearly defined research question or problem addressed by the study."""

    limitations: List[str] = Field(default_factory=list)
    """An analysis of the methodological or experimental limitations of the research."""

    future_work: List[str] = Field(default_factory=list)
    """Suggestions for potential directions or topics for follow-up studies."""

    impact_analysis: str = Field("")
    """An assessment of the paper's potential influence on the development of the field."""

    def _prepare_vectorization_inner(self) -> str:
        return self.model_dump_json()


class ArticleProposal(ProposedAble, Display):
    """Structured representation of the proposal for an academic paper."""

    title: str = Field(...)
    """The proposed title of the paper."""

    focused_problem: List[str] = Field(default_factory=list)
    """The specific research problem or question that the paper aims to address."""
    research_aim: List[str] = Field(default_factory=list)
    """The main objective or goal of the research, outlining what the study aims to achieve."""
    research_methods: List[str] = Field(default_factory=list)
    """The methods used in the research, including the approach, techniques, and tools employed."""


class ArticleSubsectionOutline(Base):
    """Structured representation of the subsections of an academic paper."""

    title: str = Field(...)
    """The title of the subsection."""

    description: str = Field(...)
    """A brief description of the subsection's content should be, how it fits into the overall structure of the paper, and its significance in the context of the research."""


class ArticleSectionOutline(Base):
    """Structured representation of the sections of an academic paper."""

    title: str = Field(...)
    """The title of the section."""
    description: str = Field(...)
    """A brief description of the section's content should be, how it fits into the overall structure of the paper, and its significance in the context of the research."""
    subsections: List[ArticleSubsectionOutline] = Field(default_factory=list)
    """The subsections of the section, outlining their content and significance."""


class ArticleChapterOutline(Base):
    """Structured representation of the chapters of an academic paper."""

    title: str = Field(...)
    """The title of the chapter."""
    description: str = Field(...)
    """A brief description of the chapter's content should be, how it fits into the overall structure of the paper, and its significance in the context of the research."""
    sections: List[ArticleSectionOutline] = Field(default_factory=list)
    """The sections of the chapter, outlining their content and significance."""


class ArticleOutline(ProposedAble, Display, FinalizedDumpAble):
    """Structured representation of the outline for an academic paper."""

    title: str = Field(...)
    """The proposed title of the paper."""

    prospect: str = Field(...)
    """A brief description of the research problem or question that the paper aims to address manipulating methods or techniques"""

    chapters: List[ArticleChapterOutline] = Field(default_factory=list)
    """The chapters of the paper, outlining their content and significance."""

    def finalized_dump(self) -> str:
        """Finalized dump of the article outline.

        Returns:
            str: The finalized dump of the article outline.
        """
        lines: List[str] = []

        for chapter in self.chapters:
            lines.append(f"= {chapter.title}")
            for section in chapter.sections:
                lines.append(f"== {section.title}")
                for subsection in section.subsections:
                    lines.append(f"=== {subsection.title}")

        return "\n\n".join(lines)
