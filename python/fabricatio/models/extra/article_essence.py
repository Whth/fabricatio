"""ArticleEssence: Semantic fingerprint of academic paper for structured analysis."""

from typing import List, Self

from fabricatio.models.generic import Display, PersistentAble, PrepareVectorization, ProposedAble
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


class Algorithm(BaseModel):
    """Research algorithm specification."""

    title: str
    """Technical title descriptor."""

    description: str
    """Description including:
    - Input/output specs
    - Key steps
    - Workflow role
    """


class Table(BaseModel):
    """Research table specification."""

    title: str
    """Technical title descriptor."""

    description: str
    """Description covering:
    - Data source/structure
    - Column/row significance
    - Research connections
    """


class Highlightings(BaseModel):
    """Technical component aggregator."""

    highlighted_equations: List[Equation]
    """3-5 pivotal equations with:
    - Display math formatting
    - Novel operators
    - Section references
    """

    highlighted_algorithms: List[Algorithm]
    """1-2 key algorithms showing:
    - Pseudocode/steps
    - Computational innovations
    """

    highlighted_figures: List[Figure]
    """4-6 key figures requiring:
    1. Framework overview (required)
    2. Quantitative results (2-3 required)
    3. Ablation studies (optional)
    """

    highlighted_tables: List[Table]
    """2-3 tables summarizing:
    - Method comparisons
    - Empirical results
    """


class ArticleEssence(ProposedAble, Display, PersistentAble, PrepareVectorization):
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

    domain: List[str]
    """Domain tags for research focus."""

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

    future_work: List[str]
    """Research roadmap items with 3 horizons: immediate, mid-term, and long-term."""

    impact_analysis: List[str]
    """Impact analysis of the research."""

    bibtex_cite_key: str
    """Bibtex cite key of the original article."""

    def update_cite_key(self, new_cite_key: str) -> Self:
        """Update the bibtex_cite_key of the article."""
        self.bibtex_cite_key = new_cite_key
        return self

    def _prepare_vectorization_inner(self) -> str:
        return self.model_dump_json()
