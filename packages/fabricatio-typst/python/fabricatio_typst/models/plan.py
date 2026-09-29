"""Flat per-element plan models and their bare-JSON-array list classes.

Every level of the article is planned on its own, from its parent's plan, so a plan
never carries children: the element's share of the parent's word budget is expressed
as a ``weight`` and the child budgets are allocated deterministically when the plans
are materialized into contexts. Each field's description is prompt-visible — it is
rendered into the planner's JSON schema — and comes from the field's attribute
docstring (``Base.model_config`` sets ``use_attribute_docstrings``), so every level
redeclares the fields whose text differs at its own scale, alias included.
"""

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core.models.generic import Described, JSONList, SketchedAble, Titled
from pydantic import Field, PositiveFloat


class WeightedPlan(SketchedAble, Titled, Described):
    """Plan of a single article element: heading, elaboration, writing aims and word-count weight."""

    title: str = Field(alias="heading")
    """The heading of this element: professional and concise, with no prefixed heading number."""

    description: str = Field(alias="elaboration")
    """What this element establishes at its own scale: the claim it makes and the material it covers."""

    aims: list[str]
    """The writing aims of this element: the points its text must make and the reader state it must leave
    behind; 2-5 entries, each one sentence and actionable."""

    weight: PositiveFloat = 1.0
    """Relative size of this element for allocating the parent's expected word count; assign by how much
    space this element needs compared with its siblings, not by an absolute number."""

    writing_styles: list[str]
    """Style directives for this element's text: voice, register, terminology and recurring techniques; an
    empty list when the inherited guidance is enough."""

    writing_constraints: list[str]
    """Hard writing constraints binding this element alone: citation rules, forbidden phrasings, structural
    requirements. They are shown to this element's planner as the rules in force; the parent's list is
    never merged into this one."""


class SubsectionPlan(WeightedPlan):
    """Plan of a single subsection; its weight allocates the section's expected word count."""

    description: str = Field(alias="elaboration")
    """What this subsection argues: its claim and the evidence it presents, at subsection scale."""

    writing_styles: list[str]
    """Style directives for this subsection's text; 0-2 entries — the article, chapter and section already
    state the paper's voice, so add only what is specific to this subsection."""

    writing_constraints: list[str]
    """Hard writing constraints binding this subsection alone; 1-4 entries — the tightest gate of the
    pipeline, since a rule that must reach the prose has to be restated here."""


class SectionPlan(WeightedPlan):
    """Plan of a single section; its weight allocates the chapter's expected word count."""

    description: str = Field(alias="elaboration")
    """What this section develops: the part of the chapter's argument it carries, at section scale."""

    writing_styles: list[str]
    """Style directives for this section's text; 1-3 entries — every subsection below inherits them, so
    keep them to what the whole section needs."""

    writing_constraints: list[str]
    """Hard writing constraints binding this section; 1-4 entries."""


class ChapterPlan(WeightedPlan):
    """Plan of a single chapter; its weight allocates the article's expected word count."""

    description: str = Field(alias="elaboration")
    """What this chapter establishes: its role in the paper's argument, at chapter scale."""

    writing_styles: list[str]
    """Style directives for this chapter's text; 1-3 entries — every section and subsection below
    inherits them, so keep them to what the whole chapter needs."""

    writing_constraints: list[str]
    """Hard writing constraints binding this chapter; 1-4 entries."""


class ArticlePlan(WeightedPlan, WordCount):
    """Plan of the article itself: its heading, abstract, aims, style and total word budget."""

    description: str = Field(alias="elaboration")
    """The abstract of the article: its problem, method and claimed contribution; the chapters are
    planned from this."""

    writing_styles: list[str]
    """Style directives for the whole article; 3-8 entries — every chapter, section and subsection
    inherits them, so they reach every prompt in the run and must stay to what binds the entire paper."""

    writing_constraints: list[str]
    """Hard writing constraints binding the whole article; 3-8 entries — they are shown to every planner
    below as the rules in force and restated at each level they must reach."""

    expected_word_count: int = 0
    """The total expected word count of the whole article; the root of the word budget that every
    chapter, section and subsection allocation divides."""


class ChapterPlans(JSONList[ChapterPlan]):
    """The complete, ordered breakdown of the one Article into its chapters — nothing omitted, nothing extra.

    Every chapter of the paper appears exactly once, in reading order; the chapters together must cover the
    article's problem, approach and conclusions with no overlap. Each chapter's weight is its share of the
    article's expected word count and is relative to the other chapters' weights.
    """


class SectionPlans(JSONList[SectionPlan]):
    """The complete, ordered breakdown of the one Chapter into its sections — nothing omitted, nothing extra.

    Every section of the chapter appears exactly once, in reading order; the sections together must develop
    what the chapter's elaboration promises, with no overlap. Each section's weight is its share of the
    chapter's expected word count and is relative to the other sections' weights.
    """


class SubsectionPlans(JSONList[SubsectionPlan]):
    """The complete, ordered breakdown of the one Section into its subsections — nothing omitted, nothing extra.

    Every subsection of the section appears exactly once, in reading order; the subsections together must
    argue what the section's elaboration promises, one claim per subsection, with no overlap. Each
    subsection's weight is its share of the section's expected word count and is relative to the other
    subsections' weights.
    """
