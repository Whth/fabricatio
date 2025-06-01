"""ArticleEssence: Semantic fingerprint of academic paper for structured analysis."""

from typing import List

from fabricatio_capabilities.models.generic import PersistentAble
from fabricatio_core.models.generic import SketchedAble
from fabricatio_rag.models.rag import MilvusDataBase
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

    highlighted_equations: List[Equation]
    """Equations that highlight the article's core contributions"""

    highlighted_figures: List[Figure]
    """key figures requiring:
    1. Framework overview
    2. Quantitative results
    """


class ArticleEssence(SketchedAble, PersistentAble, MilvusDataBase):
    """Structured representation of a scientific article's core elements in its original language."""

    language: str
    """Language of the original article."""

    title: str
    """Exact title of the original article."""

    authors: List[str]
    """Original author full names as they appear in the source document."""

    keywords: List[str]
    """Original keywords as they appear in the source document."""

    publication_year: int
    """Publication year in ISO 8601 (YYYY format)."""

    highlightings: Highlightings
    """Technical highlights including equations, algorithms, figures, and tables."""

    abstract: str
    """Abstract text in the original language."""

    core_contributions: List[str]
    """Technical contributions using CRediT taxonomy verbs."""

    technical_novelty: List[str]
    """Patent-style claims with technical specificity."""

    research_problems: List[str]
    """Problem statements as how/why questions."""

    limitations: List[str]
    """Technical limitations analysis."""

    bibtex_cite_key: str
    """Bibtex cite key of the original article."""

    def _prepare_vectorization_inner(self) -> str:
        return self.compact()
