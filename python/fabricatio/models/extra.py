"""Extra models for built-in actions."""

from abc import abstractmethod
from itertools import chain
from typing import Generator, List, Optional, Self, Tuple

from fabricatio.journal import logger
from fabricatio.models.generic import Base, CensoredAble, Display, PrepareVectorization, ProposedAble
from fabricatio.models.utils import ok
from pydantic import BaseModel, Field

# <editor-fold desc="ArticleEssence">


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


class ArticleProposal(CensoredAble, Display):
    """Structured proposal for academic paper development with core research elements.

    Guides LLM in generating comprehensive research proposals with clearly defined components.
    """

    title: str = Field(...)
    """Paper title in academic style (Title Case, 8-15 words). Example: 'Exploring Neural Architecture Search for Low-Resource Machine Translation'"""

    focused_problem: List[str]
    """Specific research problem(s) or question(s) addressed (list of 1-3 concise statements).
    Example: ['NAS computational overhead in low-resource settings', 'Architecture transferability across language pairs']"""

    research_aim: List[str]
    """Primary research objectives (list of 2-4 measurable goals).
    Example: ['Develop parameter-efficient NAS framework', 'Establish cross-lingual architecture transfer metrics']"""

    research_methods: List[str]
    """Methodological components (list of techniques/tools).
    Example: ['Differentiable architecture search', 'Transformer-based search space', 'Multi-lingual perplexity evaluation']"""

    technical_approaches: List[str]
    """Technical approaches"""


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


class ArticleOutline(Display, CensoredAble):
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
class Paragraph(CensoredAble):
    """Structured academic paragraph blueprint for controlled content generation."""

    description: str
    """Functional summary of the paragraph's role in document structure.
    Example: 'Establishes NAS efficiency improvements through differentiable methods'"""

    writing_aim: List[str]
    """Specific communicative objectives for this paragraph's content.
    Example: ['Introduce gradient-based NAS', 'Compare computational costs',
             'Link efficiency to practical applications']"""

    sentences: List[str]
    """List of sentences forming the paragraph's content."""


class ArticleRef(CensoredAble):
    """Reference to a specific section or subsection within an article.

    Always instantiated with a fine-grind reference to a specific subsection if possible.
    """

    referred_chapter_title: str
    """Full title of the chapter that contains the referenced section."""

    referred_section_title: Optional[str] = None
    """Full title of the section that contains the referenced subsection. Defaults to None if not applicable, which means the reference is to the entire chapter."""

    referred_subsection_title: Optional[str] = None
    """Full title of the subsection that contains the referenced paragraph. Defaults to None if not applicable, which means the reference is to the entire section."""

    def __hash__(self) -> int:
        """Overrides the default hash function to ensure consistent hashing across instances."""
        return hash((self.referred_chapter_title, self.referred_section_title, self.referred_subsection_title))


class ArticleBase(CensoredAble, Display):
    """Foundation for hierarchical document components with dependency tracking."""

    description: str
    """Required: Functional purpose statement for this component's role in the paper.
    Format: Single paragraph (2-3 sentences) describing specific contribution to overall paper structure.
    Example: 'Defines evaluation metrics for cross-lingual transfer experiments'"""

    writing_aim: List[str]
    """Required: List of specific rhetorical objectives (3-5 items).
    Format: Each item must be an actionable phrase starting with a verb.
    Example: ['Establish metric validity', 'Compare with baseline approaches',
             'Justify threshold selection']"""

    support_to: List[ArticleRef]
    """Required: List of ArticleRef objects identifying components this section provides evidence for.
    Format: Each reference must point to a specific chapter, section, or subsection.
    Note: References form a directed acyclic graph in the document structure."""

    depend_on: List[ArticleRef]
    """Required: List of ArticleRef objects identifying components this section builds upon.
    Format: Each reference must point to a previously defined chapter, section, or subsection.
    Note: Circular dependencies are not permitted."""

    title: str
    """Required: Standardized academic header
    Requirements:
    - Must use Title Case formatting
    - Maximum length: 12 words
    - No abbreviations without prior definition in document
    Example: 'Multilingual Benchmark Construction'"""

    @abstractmethod
    def to_typst_code(self) -> str:
        """Converts the component into a Typst code snippet for rendering."""

    @abstractmethod
    def update_from(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""

    def __eq__(self, other: "ArticleBase") -> bool:
        """Compares two ArticleBase objects based on their model_dump_json representation."""
        return self.model_dump_json() == other.model_dump_json()

    def __hash__(self) -> int:
        """Calculates a hash value for the ArticleBase object based on its model_dump_json representation."""
        return hash(self.model_dump_json())


class ArticleSubsection(ArticleBase):
    """Atomic argumentative unit with technical specificity."""

    title: str
    """Technical descriptor with maximal information density:
    Format: [Method]-[Domain]-[Innovation]
    Example: 'Transformer-Based Architecture Search Space'"""

    paragraphs: List[Paragraph]
    """List of Paragraph objects forming the content of the subsection.

    Each Paragraph describes a specific part of the academic narrative with:
    - A brief description of its purpose,
    - A list of sentences that collectively convey the ideas,
    - Writing aims that outline the intended rhetorical moves.

    This field aggregates multiple Paragraph instances to build a coherent and structured component of the subsection.
    """

    def update_from(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        if not isinstance(other, ArticleSubsection):
            raise TypeError("Cannot update from a non-ArticleSubsection instance.")
        if self.title != other.title:
            raise ValueError("Cannot update from a different title.")
        logger.debug(f"Updating SubSection {self.title}")
        self.paragraphs = other.paragraphs
        return self

    def to_typst_code(self) -> str:
        """Converts the component into a Typst code snippet for rendering.

        Returns:
            str: Typst code snippet for rendering.
        """
        return f"=== {self.title}\n" + "\n\n".join("".join(p.sentences) for p in self.paragraphs)


class ArticleSection(ArticleBase):
    """Methodological complete unit presenting cohesive research phase."""

    title: str
    """Process-oriented header indicating methodological scope.
    Example: 'Cross-Lingual Transfer Evaluation Protocol'"""

    subsections: List[ArticleSubsection]
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

    def update_from(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        if not isinstance(other, ArticleSection):
            raise TypeError("Cannot update from a non-ArticleSection instance.")
        if self.title != other.title:
            raise ValueError("Cannot update from a different title.")
        if any(True for sel, oth in zip(self.subsections, other.subsections, strict=True) if sel.title != oth.title):
            raise ValueError(
                "Cannot update from a different number of subsections or the title of the subsections is not the same."
            )
        for self_subsec, other_subsec in zip(self.subsections, other.subsections, strict=True):
            self_subsec.update_from(other_subsec)
        return self

    def to_typst_code(self) -> str:
        """Converts the section into a Typst formatted code snippet.

        Returns:
            str: The formatted Typst code snippet.
        """
        return f"== {self.title}\n" + "\n\n".join(subsec.to_typst_code() for subsec in self.subsections)


class ArticleChapter(ArticleBase):
    """Macro-structural unit implementing IMRaD document architecture."""

    title: str
    """Standard IMRaD chapter title with domain specification.
    Example: 'Neural Architecture Search for Low-Resource Languages'"""

    sections: List[ArticleSection]
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

    def update_from(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        if not isinstance(other, ArticleChapter):
            raise TypeError("Cannot update from a non-ArticleChapter instance.")
        if self.title != other.title:
            raise ValueError("Cannot update from a different title.")
        if any(True for sel, oth in zip(self.sections, other.sections, strict=True) if sel.title != oth.title):
            raise ValueError(
                "Cannot update from a different number of sections or the title of the sections is not the same."
            )
        for self_sec, other_sec in zip(self.sections, other.sections, strict=True):
            self_sec.update_from(other_sec)
        return self

    def to_typst_code(self) -> str:
        """Converts the chapter into a Typst formatted code snippet for rendering."""
        return f"= {self.title}\n" + "\n\n".join(sec.to_typst_code() for sec in self.sections)


class Article(Display, CensoredAble):
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
        return "\n\n".join(c.to_typst_code() for c in self.chapters)

    @classmethod
    def from_outline(cls, outline: ArticleOutline) -> "Article":
        """Generates an article from the given outline.

        Args:
            outline (ArticleOutline): The outline to generate the article from.

        Returns:
            Article: The generated article.
        """
        # Set the title from the outline
        article = Article(title=outline.title, abstract="", chapters=[])

        for chapter in outline.chapters:
            # Create a new chapter
            article_chapter = ArticleChapter(
                title=chapter.title,
                description=chapter.description,
                writing_aim=[],
                support_to=[],
                depend_on=[],
                sections=[],
            )
            for section in chapter.sections:
                # Create a new section
                article_section = ArticleSection(
                    title=section.title,
                    description=section.description,
                    writing_aim=[],
                    support_to=[],
                    depend_on=[],
                    subsections=[],
                )
                for subsection in section.subsections:
                    # Create a new subsection
                    article_subsection = ArticleSubsection(
                        title=subsection.title,
                        description=subsection.description,
                        writing_aim=[],
                        support_to=[],
                        depend_on=[],
                        paragraphs=[],
                    )
                    article_section.subsections.append(article_subsection)
                article_chapter.sections.append(article_section)
            article.chapters.append(article_chapter)
        return article

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

    def iter_dfs(self) -> Generator[ArticleBase, None, None]:
        """Performs a depth-first search (DFS) through the article structure.

        Returns:
            Generator[ArticleBase]: Each component in the article structure.
        """
        for chap in self.chap_iter():
            for sec in chap.sections:
                yield from sec.subsections
                yield sec
            yield chap

    def deref(self, ref: ArticleRef) -> ArticleBase:
        """Resolves a reference to the corresponding section or subsection in the article.

        Args:
            ref (ArticleRef): The reference to resolve.

        Returns:
            ArticleBase: The corresponding section or subsection.
        """
        chap = ok(
            next(chap for chap in self.chap_iter() if chap.title == ref.referred_chapter_title), "Chapter not found"
        )
        if ref.referred_section_title is None:
            return chap
        sec = ok(next(sec for sec in chap.sections if sec.title == ref.referred_section_title))
        if ref.referred_subsection_title is None:
            return sec
        return ok(next(subsec for subsec in sec.subsections if subsec.title == ref.referred_subsection_title))

    def gather_dependencies(self, article: ArticleBase) -> List[ArticleBase]:
        """Gathers dependencies for all sections and subsections in the article.

        This method should be called after the article is fully constructed.
        """
        depends = [self.deref(a) for a in article.depend_on]

        supports = []
        for a in self.iter_dfs():
            if article in {self.deref(b) for b in a.support_to}:
                supports.append(a)

        return list(set(depends + supports))

    def gather_dependencies_recursive(self, article: ArticleBase) -> List[ArticleBase]:
        """Gathers all dependencies recursively for the given article.

        Args:
            article (ArticleBase): The article to gather dependencies for.

        Returns:
            List[ArticleBase]: A list of all dependencies for the given article.
        """
        q = self.gather_dependencies(article)

        deps = []
        while a := q.pop():
            deps.extend(self.gather_dependencies(a))

        deps = list(
            chain(
                filter(lambda x: isinstance(x, ArticleChapter), deps),
                filter(lambda x: isinstance(x, ArticleSection), deps),
                filter(lambda x: isinstance(x, ArticleSubsection), deps),
            )
        )

        # Initialize result containers
        formatted_code = ""
        processed_components = []

        # Process all dependencies
        while component := deps.pop():
            # Skip duplicates
            if (component_code := component.to_typst_code()) in formatted_code:
                continue

            # Add this component
            formatted_code += component_code
            processed_components.append(component)

        return processed_components

    def iter_dfs_with_deps(self) -> Generator[Tuple[ArticleBase, List[ArticleBase]], None, None]:
        """Iterates through the article in a depth-first manner, yielding each component and its dependencies.

        Yields:
            Tuple[ArticleBase, List[ArticleBase]]: Each component and its dependencies.
        """
        for component in self.iter_dfs():
            yield component, (self.gather_dependencies_recursive(component))


# </editor-fold>
