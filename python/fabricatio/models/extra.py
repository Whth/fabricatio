"""Extra models for built-in actions."""

from typing import Generator, List, Optional, Self

from fabricatio.models.generic import Base, Display, FinalizedDumpAble, PrepareVectorization, ProposedAble

# <editor-fold desc="ArticleEssence">
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

    subsections: List[ArticleSubsectionOutline] = Field(
        ...,
    )
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

    sections: List[ArticleSectionOutline] = Field(
        ...,
    )
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

    chapters: List[ArticleChapterOutline] = Field(
        ...,
    )
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

    support_to: List[SectionRef]
    """Upstream dependencies requiring this component's validation.
    Format: List of hierarchical references to supported claims/sections
    """

    depend_on: List[SectionRef]
    """Downstream prerequisites for content validity.
    Format: List of references to foundational components
    """

    title: str = Field(...)
    """Standardized academic header following ACL style guidelines:
    - Title Case with maximal 12-word length
    - No abbreviations without prior definition
    Example: 'Multilingual Benchmark Construction'"""

    def get_dependencies(self, article: "Article") -> List["ArticleSubsection"]:
        """Retrieves all upstream dependencies for this component, including those that support it and those it depends on.

        Args:
            article (Article): The overall academic document for reference.

        Returns:
            List[ArticleSubsection]: List of all upstream dependencies for this component.
        """
        return [
            article.get_subsection(ref.ref_chapter_title, ref.ref_section_title, ref.ref_subsection_title)
            for ref in self.support_to
        ] + [article.get_subsection(ref.ref_chapter_title, ref.ref_section_title) for ref in self.depend_on]


class ArticleSubsection(ArticleBase):
    """Atomic argumentative unit with technical specificity."""

    title: str = Field(...)
    """Technical descriptor with maximal information density:
    Format: [Method]-[Domain]-[Innovation]
    Example: 'Transformer-Based Architecture Search Space'"""

    paragraphs: List[Paragraph] = Field(
        ...,
    )
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

    subsections: List[ArticleSubsection] = Field(
        ...,
    )
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

    sections: List[ArticleSection] = Field(
        ...,
    )
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


class Article(ProposedAble, Display, FinalizedDumpAble):
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

    chapters: List[ArticleChapter] = Field(
        ...,
    )
    """IMRaD-compliant document structure with enhanced validation:
    1. Introduction: Motivation & Contributions
    2. Background: Literature & Theory
    3. Methods: Technical Implementation
    4. Experiments: Protocols & Setup
    5. Results: Empirical Findings
    6. Discussion: Interpretation & Limitations
    7. Conclusion: Summary & Future Work

    Additional: Appendices, Ethics Review, Reproducibility Statements"""

    def finalized_dump(self) -> str:
        """Exports the article in `typst` format.

        Returns:
                str: Strictly formatted outline with typst formatting.
        """
        lines = []
        for sec in self.dfs_iter():
            match sec:
                case cha if isinstance(cha, ArticleChapter):
                    lines.append(f"= {cha.title}")
                case sec if isinstance(sec, ArticleSection):
                    lines.append(f"== {sec.title}")
                case subsec if isinstance(subsec, ArticleSubsection):
                    lines.append(f"=== {subsec.title}")
                    lines.append(" \\".join("".join(p.lines) for p in subsec.paragraphs))

                case _:
                    raise TypeError(f"Unknown type: {type(sec)}")

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

    def get_subsection(
        self, chapter_title: str, section_title: str, subsection_title: str
    ) -> Optional[ArticleSubsection]:
        """Retrieves a specific subsection based on chapter and section titles.

        Args:
            chapter_title (str): Title of the chapter.
            section_title (str): Title of the section.
            subsection_title (str): Title of the subsection.

        Returns:
            ArticleSubsection: The requested subsection.
        """
        return next(
            (
                subsection
                for chapter in self.chapters
                for section in chapter.sections
                for subsection in section.subsections
                if chapter.title == chapter_title
                and section.title == section_title
                and subsection.title == subsection_title
            ),
            None,
        )

    def gather_dependencies(self, article: ArticleBase) -> List[ArticleSubsection]:
        """Collects all dependencies for the article, including supported and dependent components.

        Args:
            article (ArticleBase): The article to gather dependencies from.

        Returns:
            List[ArticleSubsection]: List of all dependencies for the article.
        """
        return [
            self.get_subsection(d.ref_chapter_title, d.ref_section_title, d.ref_subsection_title)
            for d in article.depend_on
        ]

    def gather_reverse_dependencies(self, article: ArticleBase) -> List[ArticleSubsection]:
        """Collects all reverse dependencies for the article, including supported and dependent components.

        Args:
            article (ArticleBase): The article to gather dependencies from.

        Returns:
            List[ArticleSubsection]: List of all dependencies for the article.
        """

    def chap_iter(self) -> Generator[ArticleChapter, None, None]:
        """Iterates over all chapters in the article.

        Yields:
            ArticleChapter: Each chapter in the article.
        """
        yield from self.chapters

    def section_iter(self) -> Generator[ArticleSection, None, None]:
        """Iterates over all sections in the article.

        Yields:
            ArticleSection: Each section in the article.
        """
        for chap in self.chapters:
            yield from chap.sections

    def subsection_iter(self) -> Generator[ArticleSubsection, None, None]:
        """Iterates over all subsections in the article.

        Yields:
            ArticleSubsection: Each subsection in the article.
        """
        for sec in self.section_iter():
            yield from sec.subsections

    def dfs_iter(self) -> Generator[ArticleBase, None, None]:
        """Performs a depth-first search (DFS) through the article structure.

        Returns:
            Generator[ArticleBase]: Each component in the article structure.
        """
        for chap in self.chap_iter():
            yield chap
            for sec in chap.sections:
                yield sec
                for subsec in sec.subsections:
                    yield subsec


# </editor-fold>
