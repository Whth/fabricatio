"""ArticleEssence: Semantic fingerprint of academic paper for structured analysis."""

from typing import List

from fabricatio.models.generic import Display, PrepareVectorization, ProposedAble
from pydantic import BaseModel, Field


class Equation(BaseModel):
    """Mathematical formalism specification for research contributions.

    Encodes equations with dual representation: semantic meaning and typeset-ready notation.
    """

    description: str
    """Equation significance structured in three elements:
    1. Physical/conceptual meaning of the equation.
    2. Role in technical workflow (e.g., derivation, optimization, or analysis).
    3. Relationship to the paper's core contribution (e.g., theoretical foundation, empirical validation).
    Example: "Defines constrained search space dimensionality reduction. Used in architecture optimization phase (Section 3.2). Enables 40% parameter reduction."
    """

    latex_code: str
    """LaTeX representation following academic typesetting standards:
    - Must use equation environment (e.g., `equation`, `align`).
    - Multiline equations must align at '=' using `&`.
    - Include unit annotations where applicable.
    Example: "\\begin{equation} \\mathcal{L}_{NAS} = \\alpha \\|\\theta\\|_2 + \\beta H(p) \\end{equation}"
    """


class Figure(BaseModel):
    """Visual component specification for technical communication.

    Combines graphical assets with structured academic captioning.Extracted from the article provided
    """

    description: str
    """Figure interpretation guide containing:
    1. Key visual elements mapping (e.g., axes, legends, annotations).
    2. Data representation methodology (e.g., visualization type, statistical measures).
    3. Connection to research findings (e.g., supports hypothesis, demonstrates performance).
    Example: "Architecture search space topology (left) vs. convergence curves (right). Demonstrates NAS efficiency gains through constrained search."
    """

    figure_caption: str
    """Complete caption following Nature-style guidelines:
    1. Brief overview statement (首句总结).
    2. Technical detail layer (e.g., data sources, experimental conditions).
    3. Result implication (e.g., key insights, implications for future work).
    Example: "Figure 3: Differentiable NAS framework. (a) Search space topology with constrained dimensions. (b) Training convergence across language pairs. Dashed lines indicate baseline methods."
    """

    figure_serial_number: int
    """The Image serial number extracted from the Markdown article provided, the path usually in the form of `![](images/1.jpg)`, in this case the serial number is `1`"""


class Algorithm(BaseModel):
    """Algorithm specification for research contributions."""

    title: str
    """Algorithm title with technical focus descriptor (e.g., 'Gradient Descent Optimization').

    Tip: Do not attempt to translate the original element titles when generating JSON.
    """

    description: str
    """Algorithm description with technical focus descriptor:
    - Includes input/output specifications.
    - Describes key steps and their purpose.
    - Explains its role in the research workflow.
    Example: "Proposed algorithm for neural architecture search. Inputs include search space constraints and training data. Outputs optimized architecture."
    """


class Table(BaseModel):
    """Table specification for research contributions."""

    title: str
    """Table title with technical focus descriptor (e.g., 'Comparison of Model Performance Metrics').

    Tip: Do not attempt to translate the original element titles when generating JSON.
    """

    description: str
    """Table description with technical focus descriptor:
    - Includes data source and structure.
    - Explains key columns/rows and their significance.
    - Connects to research findings or hypotheses.
    Example: "Performance metrics for different architectures. Columns represent accuracy, F1-score, and inference time. Highlights efficiency gains of proposed method."
    """


class Highlightings(BaseModel):
    """Technical showcase aggregator for research artifacts.

    Curates core scientific components with machine-parseable annotations.
    """

    highlighted_equations: List[Equation]
    """3-5 pivotal equations representing theoretical contributions:
    - Each equation must be wrapped in $$ for display math.
    - Contain at least one novel operator/symbol.
    - Be referenced in Methods/Results sections.
    Example: Equation describing proposed loss function.
    """

    highlighted_algorithms: List[Algorithm]
    """1-2 key algorithms demonstrating methodological contributions:
    - Include pseudocode or step-by-step descriptions.
    - Highlight innovation in computational approach.
    Example: Algorithm for constrained search space exploration.

    Tip: Do not attempt to translate the original element titles when generating JSON.
    """

    highlighted_figures: List[Figure]
    """4-6 key figures demonstrating:
    1. Framework overview (1 required).
    2. Quantitative results (2-3 required).
    3. Ablation studies (1 optional).
    Each must appear in Results/Discussion chapters.
    Example: Figure showing architecture topology and convergence curves.
    """

    highlighted_tables: List[Table]
    """2-3 key tables summarizing:
    - Comparative analysis of methods.
    - Empirical results supporting claims.
    Example: Table comparing model performance across datasets.

    Tip: Do not attempt to translate the original element titles when generating JSON.
    """


class ArticleEssence(ProposedAble, Display, PrepareVectorization):
    """Semantic fingerprint of academic paper for structured analysis.

    Encodes research artifacts with dual human-machine interpretability.
    """

    title: str = Field(...)
    """Exact title of the original article without any modification.
    Must be preserved precisely from the source material without:
    - Translation
    - Paraphrasing
    - Adding/removing words
    - Altering style or formatting
    """

    authors: List[str]
    """Original author names exactly as they appear in the source document. No translation or paraphrasing.
    Extract complete list without any modifications or formatting changes."""

    keywords: List[str]
    """Original keywords exactly as they appear in the source document. No translation or paraphrasing.
    Extract the complete set without modifying format or terminology."""

    publication_year: int
    """Publication timestamp in ISO 8601 (YYYY format)."""

    highlightings: Highlightings
    """Technical highlight reel containing:
    - Core equations (Theory)
    - Key algorithms (Implementation)
    - Critical figures (Results)
    - Benchmark tables (Evaluation)"""

    domain: List[str]
    """Domain tags for research focus."""

    abstract: str = Field(...)
    """Three-paragraph structured abstract:
    Paragraph 1: Problem & Motivation (2-3 sentences)
    Paragraph 2: Methodology & Innovations (3-4 sentences)
    Paragraph 3: Results & Impact (2-3 sentences)
    Total length: 150-250 words"""

    core_contributions: List[str]
    """3-5 technical contributions using CRediT taxonomy verbs.
    Each item starts with action verb.
    Example:
    - 'Developed constrained NAS framework'
    - 'Established cross-lingual transfer metrics'"""

    technical_novelty: List[str]
    """Patent-style claims with technical specificity.
    Format: 'A [system/method] comprising [novel components]...'
    Example:
    'A neural architecture search system comprising:
     a differentiable constrained search space;
     multi-lingual transferability predictors...'"""

    research_problems: List[str]
    """Problem statements as how/why questions.
    Example:
    - 'How to reduce NAS computational overhead while maintaining search diversity?'
    - 'Why do existing architectures fail in low-resource cross-lingual transfer?'"""

    limitations: List[str]
    """Technical limitations analysis containing:
    1. Constraint source (data/method/theory)
    2. Impact quantification
    3. Mitigation pathway
    Example:
    'Methodology constraint: Single-objective optimization (affects 5% edge cases),
    mitigated through future multi-task extension'"""

    future_work: List[str]
    """Research roadmap items with 3 horizons:
    1. Immediate extensions (1 year)
    2. Mid-term directions (2-3 years)
    3. Long-term vision (5+ years)
    Example:
    'Short-term: Adapt framework for vision transformers (ongoing with CVPR submission)'"""

    impact_analysis: List[str]
    """Bibliometric impact projections:
    - Expected citation counts (next 3 years)
    - Target application domains
    - Standard adoption potential
    Example:
    'Predicted 150+ citations via integration into MMEngine (Alibaba OpenMMLab)'"""

    def _prepare_vectorization_inner(self) -> str:
        return self.model_dump_json()
