"""Extra models for built-in actions."""

from typing import List, Self

from fabricatio.models.generic import Base, Display, FinalizedDumpAble, PrepareVectorization, ProposedAble
from pydantic import Field


# <editor-fold desc="ArticleEssence">
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


# </editor-fold>


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

    technical_approaches: List[str] = Field(default_factory=list)


# <editor-fold desc="ArticleOutline">
class ArticleSubsectionOutline(Base):
    """Atomic research component specification for academic paper generation."""

    title: str = Field(...)
    """Technical focus descriptor following ACL title conventions:
    - Title Case with 4-8 word limit
    - Contains method and domain components
    Example: 'Differentiable Search Space Optimization'"""

    description: str = Field(...)
    """Tripartite content specification with strict structure:
    1. Technical Core: Method/algorithm/formalism (1 sentence)
    2. Structural Role: Placement rationale in section (1 clause)
    3. Research Value: Contribution to paper's thesis (1 clause)

    Example: 'Introduces entropy-constrained architecture parameters enabling
    gradient-based NAS. Serves as foundation for Section 3.2. Critical for
    maintaining search space diversity while ensuring convergence.'"""


class ArticleSectionOutline(Base):
    """Methodological unit organizing related technical components."""

    title: str = Field(...)
    """Process-oriented header with phase identification:
    - Title Case with 5-10 word limit
    - Indicates research stage/methodological focus
    Example: 'Cross-Lingual Evaluation Protocol'"""

    description: str = Field(...)
    """Functional specification with four required elements:
    1. Research Stage: Paper progression position
    2. Technical Innovations: Novel components
    3. Scholarly Context: Relationship to prior work
    4. Forward Flow: Connection to subsequent sections

    Example: 'Implements constrained NAS framework building on Section 2's
    theoretical foundations. Introduces dynamic resource allocation mechanism.
    Directly supports Results section through ablation study parameters.'"""

    subsections: List[ArticleSubsectionOutline] = Field(..., min_length=3, max_length=5)
    """IMRaD-compliant substructure with technical progression:
    1. Conceptual Framework
    2. Methodological Details
    3. Implementation Strategy
    4. Validation Approach
    5. Transition Logic

    Example Flow:
    [
        'Search Space Constraints',
        'Gradient Optimization Protocol',
        'Multi-GPU Implementation',
        'Convergence Validation',
        'Cross-Lingual Extension'
    ]"""


class ArticleChapterOutline(Base):
    """Macro-structural unit implementing standard academic paper organization."""

    title: str = Field(...)
    """IMRaD-compliant chapter title with domain specification:
    - Title Case with 2-4 word limit
    - Matches standard paper sections
    Example: 'Multilingual Evaluation Results'"""

    description: str = Field(...)
    """Strategic chapter definition containing:
    1. Research Phase: Introduction/Methods/Results/etc.
    2. Chapter Objectives: 3-5 specific goals
    3. Thesis Alignment: Supported claims/contributions
    4. Structural Flow: Adjacent chapter relationships

    Example: 'Presents cross-lingual NAS results across 10 language pairs.
    Validates efficiency claims from Introduction. Provides empirical basis
    for Discussion chapter. Contrasts with single-language baselines.'"""

    sections: List[ArticleSectionOutline] = Field(..., min_length=3, max_length=5)
    """Standard academic progression implementing chapter goals:
    1. Context Establishment
    2. Technical Presentation
    3. Empirical Validation
    4. Comparative Analysis
    5. Synthesis

    Example Structure:
    [
        'Experimental Setup',
        'Monolingual Baselines',
        'Cross-Lingual Transfer',
        'Low-Resource Scaling',
        'Error Analysis'
    ]"""


class ArticleOutline(ProposedAble, Display, FinalizedDumpAble):
    """Complete academic paper blueprint with hierarchical validation."""

    title: str = Field(...)
    """Full technical title following ACL 2024 guidelines:
    - Title Case with 12-18 word limit
    - Structure: [Method] for [Task] via [Approach] in [Domain]
    Example: 'Efficient Differentiable NAS for Low-Resource MT Through
    Parameter-Sharing: A Cross-Lingual Study'"""

    prospect: str = Field(...)
    """Consolidated research statement with four pillars:
    1. Problem Identification: Current limitations
    2. Methodological Response: Technical approach
    3. Empirical Validation: Evaluation strategy
    4. Scholarly Impact: Field contributions

    Example: 'Addressing NAS computational barriers through constrained
    differentiable search spaces, validated via cross-lingual MT experiments
    across 50+ languages, enabling efficient architecture discovery with
    60% reduced search costs.'"""

    chapters: List[ArticleChapterOutline] = Field(..., min_length=5, max_length=8)
    """IMRaD structure with enhanced academic validation:
    1. Introduction: Problem Space & Contributions
    2. Background: Theoretical Foundations
    3. Methods: Technical Innovations
    4. Experiments: Protocol Design
    5. Results: Empirical Findings
    6. Discussion: Interpretation & Limitations
    7. Conclusion: Synthesis & Future Work
    8. Appendices: Supplementary Materials"""

    def finalized_dump(self) -> str:
        """Generates standardized hierarchical markup for academic publishing systems.

        Implements ACL 2024 outline conventions with four-level structure:
        = Chapter Title (Level 1)
        == Section Title (Level 2)
        === Subsection Title (Level 3)
        ==== Subsubsection Title (Level 4)

        Returns:
            str: Strictly formatted outline with academic sectioning

        Example:
            = Methodology
            == Neural Architecture Search Framework
            === Differentiable Search Space
            ==== Constrained Optimization Parameters
            === Implementation Details
            == Evaluation Protocol
        """
        lines: List[str] = []
        for i, chapter in enumerate(self.chapters, 1):
            lines.append(f"= Chapter {i}: {chapter.title}")
            for j, section in enumerate(chapter.sections, 1):
                lines.append(f"== {i}.{j} {section.title}")
                for k, subsection in enumerate(section.subsections, 1):
                    lines.append(f"=== {i}.{j}.{k} {subsection.title}")
        return "\n".join(lines)


# </editor-fold>


# <editor-fold desc="Article">
class Paragraph(ProposedAble):
    """Structured academic paragraph blueprint for controlled content generation."""

    description: str
    """Functional summary of the paragraph's role in document structure.
    Example: 'Establishes NAS efficiency improvements through differentiable methods'"""

    writing_aim: List[str]
    """Specific communicative objectives for this paragraph's content.
    Example: ['Introduce gradient-based NAS', 'Compare computational costs',
             'Link efficiency to practical applications']"""

    lines: List[str]
    """Hierarchically structured content with enforced rhetorical elements:
    1. Topic Sentence: Principal claim/position (1 sentence)
    2. Development: Evidence chain with citations (2-4 sentences)
    3. Synthesis: Interpretation & significance (1 sentence)
    4. Transition: Logical bridge to next paragraph (optional)

    Example: [
        'Differentiable NAS revolutionized architecture search efficiency.',
        'DARTS reduced search costs from 2000+ to 4 GPU days (Liu et al., 2019) while maintaining competitive ImageNet accuracy.',
        'This order-of-magnitude improvement enables NAS deployment in resource-constrained research contexts.',
        'These efficiency gains directly impact our framework's design choices as detailed in Section 3.'
    ]"""


class SectionRef(ProposedAble):
    """Cross-component reference system for maintaining document consistency."""

    ref_chapter_title: str
    """Title of referenced chapter (e.g., 'Methodology')"""

    ref_section_title: str
    """Exact section header text (e.g., '3.2 Gradient Optimization')"""

    ref_subsection_title: str
    """Specific subsection identifier (e.g., '3.2.1 Learning Rate Scheduling')"""


class ArticleBase(ProposedAble, Display):
    """Foundation for hierarchical document components with dependency tracking."""

    description: str
    """Functional purpose statement for this component's role in the paper.
    Example: 'Defines evaluation metrics for cross-lingual transfer experiments'"""

    writing_aim: List[str]
    """Author intentions mapped to rhetorical moves:
    Example: ['Establish metric validity', 'Compare with baseline approaches',
             'Justify threshold selection']"""

    title: str = Field(...)
    """Standardized academic header following ACL style guidelines:
    - Title Case with maximal 12-word length
    - No abbreviations without prior definition
    Example: 'Multilingual Benchmark Construction'"""

    support_to: List[SectionRef]
    """Upstream dependencies requiring this component's validation.
    Format: List of hierarchical references to supported claims/sections
    Example: [SectionRef(chapter='Results', section='4.1', subsection='4.1.2')]"""

    depend_on: List[SectionRef]
    """Downstream prerequisites for content validity.
    Format: List of references to foundational components
    Example: [SectionRef(chapter='Methods', section='2.3', subsection='2.3.4')]"""


class ArticleSubsection(ArticleBase):
    """Atomic argumentative unit with technical specificity."""

    title: str = Field(...)
    """Technical descriptor with maximal information density:
    Format: [Method]-[Domain]-[Innovation]
    Example: 'Transformer-Based Architecture Search Space'"""

    support_to: List[SectionRef]
    """Immediate parent components and supported hypotheses.
    Example: [SectionRef(chapter='Methods', section='3', subsection='3.1')]"""

    depend_on: List[SectionRef]
    """Technical dependencies including equations, algorithms, and datasets.
    Example: [SectionRef(chapter='Background', section='2.2', subsection='2.2.3')]"""

    paragraphs: List[Paragraph] = Field(..., min_length=3, max_length=5)
    """Technical exposition following ACM writing guidelines:
    1. Contextualization: Position in research design
    2. Technical Detail: Equations/algorithms/code
    3. Validation: Citations/experimental confirmation
    4. Interpretation: Scholarly significance
    5. Transition: Logical connection to subsequent content

    Example Paragraph Chain:
    [
        'Our search space builds on standard CNN architectures...',
        'Formally, we define architecture parameters $\\alpha \\in R^d$ where...',
        'This parameterization reduces search complexity by 42% compared to...',
        'The efficiency gains validate our approach to...'
    ]"""


class ArticleSection(ArticleBase):
    """Methodological complete unit presenting cohesive research phase."""

    title: str = Field(...)
    """Process-oriented header indicating methodological scope.
    Example: 'Cross-Lingual Transfer Evaluation Protocol'"""

    support_to: List[SectionRef]
    """Supported research questions and paper-level claims.
    Example: [SectionRef(chapter='Introduction', section='1', subsection='1.2')]"""

    depend_on: List[SectionRef]
    """Required methodological components and theoretical frameworks.
    Example: [SectionRef(chapter='Background', section='2', subsection='2.4')]"""

    subsections: List[ArticleSubsection] = Field(..., min_length=3, max_length=5)
    """Thematic progression implementing section's research function:
    1. Conceptual Framework
    2. Technical Implementation
    3. Experimental Validation
    4. Comparative Analysis
    5. Synthesis

    Example Subsection Flow:
    [
        'Evaluation Metrics',
        'Dataset Preparation',
        'Baseline Comparisons',
        'Ablation Studies',
        'Interpretation Framework'
    ]"""


class ArticleChapter(ArticleBase):
    """Macro-structural unit implementing IMRaD document architecture."""

    title: str = Field(...)
    """Standard IMRaD chapter title with domain specification.
    Example: 'Neural Architecture Search for Low-Resource Languages'"""

    support_to: List[SectionRef]
    """Supported thesis statements and paper-level contributions.
    Example: [SectionRef(chapter='Abstract', section='', subsection='')]"""

    depend_on: List[SectionRef]
    """Foundational chapters and external knowledge prerequisites.
    Example: [SectionRef(chapter='Related Work', section='2', subsection='2.3')]"""

    sections: List[ArticleSection] = Field(..., min_length=3, max_length=5)
    """Complete research narrative implementing chapter objectives:
    1. Context Establishment
    2. Methodology Exposition
    3. Results Presentation
    4. Critical Analysis
    5. Synthesis

    Example Section Hierarchy:
    [
        'Theoretical Framework',
        'Experimental Design',
        'Results Analysis',
        'Threats to Validity',
        'Comparative Discussion'
    ]"""


class Article(ProposedAble, Display):
    """Complete academic paper specification with validation constraints."""

    title: str = Field(...)
    """Full technical descriptor following ACL 2024 guidelines:
    Structure: [Method] for [Task] in [Domain]: [Subtitle with Technical Focus]
    Example: 'Efficient Differentiable NAS for Low-Resource MT:
             A Parameter-Sharing Approach to Cross-Lingual Transfer'"""

    abstract: str = Field(...)
    """Structured summary with controlled natural language:
    1. Context: 2 clauses (problem + gap)
    2. Methods: 3 clauses (approach + innovation + implementation)
    3. Results: 3 clauses (metrics + comparisons + significance)
    4. Impact: 2 clauses (theoretical + practical)

    Example: 'Neural architecture search (NAS) faces prohibitive... [150 words]'"""

    chapters: List[ArticleChapter] = Field(..., min_length=5, max_length=8)
    """IMRaD-compliant document structure with enhanced validation:
    1. Introduction: Motivation & Contributions
    2. Background: Literature & Theory
    3. Methods: Technical Implementation
    4. Experiments: Protocols & Setup
    5. Results: Empirical Findings
    6. Discussion: Interpretation & Limitations
    7. Conclusion: Summary & Future Work

    Additional: Appendices, Ethics Review, Reproducibility Statements"""

    def init_from_outline(self, outline: ArticleOutline) -> Self:
        """Initialize the article from a given outline.

        Args:
            outline (ArticleOutline): The outline to initialize from.

        Returns:
            Self: The current instance of the article.
        """
        # Set the title from the outline
        self.title = outline.title

        # Initialize chapters based on outline's chapters
        self.chapters = []

        for chapter_outline in outline.chapters:
            # Create a new chapter
            chapter = ArticleChapter(
                title=chapter_outline.title,
                description=chapter_outline.description,
                writing_aim=["Implement " + chapter_outline.description],
                support_to=[],
                depend_on=[],
                sections=[],
            )

            # Create sections for each chapter
            for section_outline in chapter_outline.sections:
                section = ArticleSection(
                    title=section_outline.title,
                    description=section_outline.description,
                    writing_aim=["Address " + section_outline.description],
                    support_to=[],
                    depend_on=[],
                    subsections=[],
                )

                # Create subsections for each section
                for subsection_outline in section_outline.subsections:
                    subsection = ArticleSubsection(
                        title=subsection_outline.title,
                        description=subsection_outline.description,
                        writing_aim=["Explain " + subsection_outline.description],
                        support_to=[],
                        depend_on=[],
                        paragraphs=[
                            Paragraph(
                                description=f"Implementation of {subsection_outline.title}",
                                writing_aim=["Present key concepts", "Support main arguments"],
                                lines=[],
                            )
                        ],
                    )
                    section.subsections.append(subsection)

                chapter.sections.append(section)

            self.chapters.append(chapter)

        # Generate a placeholder abstract from the outline's prospect
        self.abstract = f"Abstract: {outline.prospect}"

        return self


# </editor-fold>
