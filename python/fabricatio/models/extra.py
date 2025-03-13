"""Extra models for built-in actions."""

from typing import List

from fabricatio.models.generic import Base, Display, FinalizedDumpAble, PrepareVectorization, ProposedAble
from pydantic import Field


class Equation(Base):
    """Mathematical formalism specification for research contributions.

    Encodes equations with dual representation: semantic meaning and typeset-ready notation.
    """

    description: str
    """Equation significance structured in three elements:
    1. Physical/conceptual meaning
    2. Role in technical workflow
    3. Relationship to paper's core contribution
    Example: 'Defines constrained search space dimensionality reduction. Used in architecture optimization phase (Section 3.2). Enables 40% parameter reduction.'"""

    latex_code: str
    """LaTeX representation following academic typesetting standards:
    - Must use equation environment
    - Multiline equations aligned at '='
    - Unit annotations where applicable
    Example: r'\begin{equation} \\mathcal{L}_{NAS} = \alpha \\|\theta\\|_2 + \beta H(p) \\end{equation}'"""


class Figure(Base):
    """Visual component specification for technical communication.

    Combines graphical assets with structured academic captioning.
    """

    description: str
    """Figure interpretation guide containing:
    1. Key visual elements mapping
    2. Data representation methodology
    3. Connection to research findings
    Example: 'Architecture search space topology (left) vs. convergence curves (right). Demonstrates NAS efficiency gains through constrained search.'"""

    figure_caption: str
    """Complete caption following Nature-style guidelines:
    1. Brief overview statement (首句总结)
    2. Technical detail layer
    3. Result implication
    Example: 'Figure 3: Differentiable NAS framework. (a) Search space topology with constrained dimensions. (b) Training convergence across language pairs. Dashed lines indicate baseline methods.'"""

    figure_path: str
    """Filesystem path to high-resolution vector graphic (PDF/EPS/SVG).
    Strict validation requirements:
    - Absolute path under /assets/figures/
    - Naming convention: fig[chapter]-[section]_[description].pdf
    Example: '/assets/figures/fig3-2_nas_convergence.pdf'"""


class Highlightings(Base):
    """Technical showcase aggregator for research artifacts.

    Curates core scientific components with machine-parseable annotations.
    """

    highlighted_equations: List[Equation] = Field(default_factory=list)
    """3-5 pivotal equations representing theoretical contributions.
    Each must:
    - Use $$ wrapping for display math
    - Contain at least one novel operator/symbol
    - Reference in Methods/Results sections
    Example: Equation describing proposed loss function"""

    highlighted_algorithms: List[str] = Field(default_factory=list)
    """Algorithm pseudocode following ACM style:
    1. Numbered steps with bold keywords
    2. Complexity analysis subsection
    3. Novel components marked with ※
    Example:
    'Algorithm 1: Constrained NAS
    1. Initialize search space with §3.1 constraints ※
    2. While not converged:
        a. Compute gradient ▽θ
        b. Update architecture parameters...'"""

    highlighted_figures: List[Figure] = Field(default_factory=list)
    """4-6 key figures demonstrating:
    1. Framework overview (1 required)
    2. Quantitative results (2-3 required)
    3. Ablation studies (1 optional)
    Each must appear in Results/Discussion chapters."""

    highlighted_tables: List[str] = Field(default_factory=list)
    """Critical data presentations using booktabs format:
    - Minimum 3 comparison baselines
    - Statistical significance markers (*/†/‡)
    - Standard deviation in parentheses
    Example:
    \begin{tabular}{lcc}
    \toprule
    Method & BLEU & Δ Params \\
    \\midrule
    Ours & 32.4 & -41\\%† \\
    \bottomrule
    \\end{tabular}"""


class ArticleEssence(ProposedAble, Display, PrepareVectorization):
    """Semantic fingerprint of academic paper for structured analysis.

    Encodes research artifacts with dual human-machine interpretability.
    """

    title: str = Field(...)
    """Complete title with technical specificity (12-18 words).
    Must contain:
    1. Methodology focus
    2. Application domain
    3. Performance metric
    Example: 'EfficientViT: Multi-Scale Linear Attention for High-Resolution Dense Prediction'"""

    authors: List[str]
    """Author list with institutional annotations.
    Format: [First Last¹, First Last²]
    Superscripts mapping to affiliations.
    Example: ['Yuanhao Zhou¹', 'Lei Chen²']"""

    keywords: List[str]
    """5-8 ACM CCS concepts in camel case.
    Example: ['Computing methodologies~Neural networks', 'Hardware~Emerging technologies']"""

    publication_year: int
    """Publication timestamp in ISO 8601 (YYYY format).
    Constraint: 2017 ≤ year ≤ current_year"""

    highlightings: Highlightings = Field(default_factory=Highlightings)
    """Technical highlight reel containing:
    - Core equations (Theory)
    - Key algorithms (Implementation)
    - Critical figures (Results)
    - Benchmark tables (Evaluation)"""

    domain: List[str]
    """Primary research domains from ACM CCS 2023 taxonomy.
    Exactly 2-3 categories required.
    Example: ['Computing methodologies → Machine learning']"""

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


class ArticleProposal(ProposedAble, Display):
    """Structured proposal for academic paper development with core research elements.

    Guides LLM in generating comprehensive research proposals with clearly defined components.
    """

    title: str = Field(...)
    """Paper title in academic style (Title Case, 8-15 words). Example: 'Exploring Neural Architecture Search for Low-Resource Machine Translation'"""

    focused_problem: List[str] = Field(default_factory=list)
    """Specific research problem(s) or question(s) addressed (list of 1-3 concise statements).
    Example: ['NAS computational overhead in low-resource settings', 'Architecture transferability across language pairs']"""

    research_aim: List[str] = Field(default_factory=list)
    """Primary research objectives (list of 2-4 measurable goals).
    Example: ['Develop parameter-efficient NAS framework', 'Establish cross-lingual architecture transfer metrics']"""

    research_methods: List[str] = Field(default_factory=list)
    """Methodological components (list of techniques/tools).
    Example: ['Differentiable architecture search', 'Transformer-based search space', 'Multi-lingual perplexity evaluation']"""


class ArticleSubsectionOutline(Base):
    """Atomic content unit within academic paper sections.

    Provides structured content specification for LLM-generated subsections.
    """

    title: str = Field(...)
    """Subsection title reflecting specific content focus (Title Case, 3-8 words).
    Example: 'Differentiable Search Space Design'"""

    description: str = Field(...)
    """Content specification with three required elements:
    1. Core technical content
    2. Structural purpose in section
    3. Research significance
    Example: 'Introduces continuous relaxation method for search space, enabling gradient-based optimization. Forms technical foundation for Section 3. Critical for reducing search complexity.'"""


class ArticleSectionOutline(Base):
    """Primary organizational unit within paper chapters.

    Defines section-level structure with nested subsections for hierarchical content organization.
    """

    title: str = Field(...)
    """Section title indicating methodological phase or conceptual component (Title Case).
    Example: 'Architecture Search Methodology'"""

    description: str = Field(...)
    """Functional description covering:
    1. Section's research stage
    2. Key contributions
    3. Flow relationship with adjacent sections
    Example: 'Presents core NAS framework building on literature from Section 2. Introduces novel constrained search space. Leads to implementation details in Section 4.'"""

    subsections: List[ArticleSubsectionOutline]
    """Ordered sequence of 3-5 subsections implementing IMRaD structure within section. Maintains logical flow from problem statement to technical solution."""


class ArticleChapterOutline(Base):
    """Macro-level paper organization unit.

    Represents major paper divisions (Introduction, Methodology, etc.) with hierarchical section structure.
    """

    title: str = Field(...)
    """Chapter title reflecting standard academic sections (Title Case).
    Example: 'Experimental Evaluation', 'Theoretical Framework'"""

    description: str = Field(...)
    """Chapter role specification containing:
    1. Research phase covered
    2. Chapter-specific objectives
    3. Relationship to overall paper thesis
    Example: 'Validates NAS framework through multilingual experiments. Demonstrates method effectiveness across 10 language pairs. Supports core thesis of parameter-efficient architecture search.'"""

    sections: List[ArticleSectionOutline]
    """3-5 sections implementing chapter's main function. Ordered to maintain academic paper logic:
    Introduction → Related Work → Methods → Experiments → Analysis"""


class ArticleOutline(ProposedAble, Display, FinalizedDumpAble):
    """Complete hierarchical structure for academic paper generation.

    Provides multi-level outline specification for LLM-based paper drafting with strict academic conventions.
    """

    title: str = Field(...)
    """Full paper title with technical specificity (Title Case, 12-18 words).
    Example: 'Parameter-Efficient Neural Architecture Search for Low-Resource Machine Translation: A Cross-Lingual Transfer Approach'"""

    prospect: str = Field(...)
    """Unified problem-solution statement combining:
    1. Core research gap
    2. Proposed methodology
    3. Expected contribution
    Example: 'Addressing NAS computational barriers in low-resource NLP through differentiable constrained search spaces and cross-lingual transfer metrics, enabling efficient architecture discovery for 50+ languages.'"""

    chapters: List[ArticleChapterOutline]
    """Standard academic structure (5-8 chapters):
    1. Introduction
    2. Related Work
    3. Methodology
    4. Experiments
    5. Results
    6. Discussion
    7. Conclusion
    Maintains IMRaD logical flow with clear inter-chapter transitions."""

    def finalized_dump(self) -> str:
        """Generates standardized hierarchical markup for paper drafting systems.

        Returns:
            str: Multi-level outline using academic markup conventions:
            = Chapter Title
            == Section Title
            === Subsection Title
            ==== Subsubsection Title (if needed)

        Example:
            = Methodology
            == Neural Architecture Search Framework
            === Differentiable Search Space
            === Constrained Optimization Approach
        """
        lines: List[str] = []

        for chapter in self.chapters:
            lines.append(f"= {chapter.title}")
            for section in chapter.sections:
                lines.append(f"== {section.title}")
                for subsection in section.subsections:
                    lines.append(f"=== {subsection.title}")

        return "\n\n".join(lines)
