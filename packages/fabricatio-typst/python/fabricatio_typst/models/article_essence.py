"""ArticleEssence: Semantic fingerprint of academic paper for structured analysis."""

from typing import Any

from fabricatio_capabilities.models.generic import PersistentAble
from fabricatio_core.models.generic import SketchedAble, Vectorizable
from pydantic import BaseModel


class Equation(BaseModel):
    """Mathematical formalism specification for research contributions."""

    description: str
    """Structured significance including:
    1. Conceptual meaning
    2. Technical workflow role
    3. Contribution relationship
    """

    latex_code: str
    """Typeset-ready notation."""


class Figure(BaseModel):
    """Visual component with academic captioning."""

    description: str
    """Interpretation guide covering:
    1. Visual element mapping
    2. Data representation method
    3. Research connection
    """

    figure_caption: str
    """Nature-style caption containing:
    1. Overview statement
    2. Technical details
    3. Result implications
    """

    figure_serial_number: int
    """Image serial number extracted from Markdown path"""


class Highlightings(BaseModel):
    """Technical component aggregator."""

    highlighted_equations: list[Equation]
    """Equations that highlight the article's core contributions"""

    highlighted_figures: list[Figure]
    """key figures requiring:
    1. Framework overview
    2. Quantitative results
    """


class ArticleEssence(SketchedAble, PersistentAble, Vectorizable):
    """Structured representation of a scientific article's core elements in its original language."""

    language: str
    """Language of the original article."""

    title: str
    """Exact title of the original article."""

    authors: list[str]
    """Original author full names as they appear in the source document."""

    keywords: list[str]
    """Original keywords as they appear in the source document."""

    publication_year: int
    """Publication year in ISO 8601 (YYYY format)."""

    highlightings: Highlightings
    """Technical highlights including equations, algorithms, figures, and tables."""

    abstract: str
    """Abstract text in the original language."""

    core_contributions: list[str]
    """Technical contributions using CRediT taxonomy verbs."""

    technical_novelty: list[str]
    """Patent-style claims with technical specificity."""

    research_problems: list[str]
    """Problem statements as how/why questions."""

    limitations: list[str]
    """Technical limitations analysis."""

    bibtex_cite_key: str
    """Bibtex cite key of the original article."""
    metadata: dict[str, Any] | None = None
    """Optional metadata for vector DB storage."""

    @property
    def content(self) -> str:
        """Serialized JSON content for storage."""
        return self.compact()

    def _as_prompt_inner(self) -> dict[str, str] | dict[str, Any] | Any:
        return self.model_dump()

    def _prepare_vectorization_inner(self) -> str:
        return self.compact()
