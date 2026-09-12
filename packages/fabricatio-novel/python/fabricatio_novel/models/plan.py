"""Flat per-element plan models and their bare-JSON-array list classes."""

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core.models.generic import Described, JSONList, SketchedAble, Titled
from pydantic import Field, PositiveFloat


class WeightedPlan(SketchedAble, Titled, Described):
    """Plan of a single novel element: title, description, and word-count weight."""

    weight: PositiveFloat = 1.0
    """Relative importance for allocating the parent's expected word count; assign by narrative importance."""

    writing_styles: list[str]
    """Style directives for this element's prose: narrative voice, point of view, tone,
    rhythm, and recurring techniques; empty list when no specific style is required."""

    writing_constraints: list[str]
    """Hard writing constraints binding this element: point of view, tense, perspective,
    prohibitions. The constraints in force at the level above are shown when planning this
    element's children; this list is never merged with the parent's, so each element carries
    its own rules alone and a scene's prose prompt shows the scene's own entries only. Empty
    list when no constraint applies."""

    cast: list[str] = Field(default_factory=list)
    """Names of the characters on stage in this element; the planner proposes the cast.
    Empty when no character appears in this element."""


class ScenePlan(WeightedPlan):
    """Plan of a single scene; its weight allocates the story's expected word count."""

    description: str
    """1 sentence per event this scene stages, in order — as many sentences as its events
    require: for each event name who is present, who does what to whom, where and when it
    happens, and how the situation changes by it. Preserve agency exactly — never swap who acts
    and who is acted upon, never merge two events into one sentence, and never stage an event
    the Story Description above does not contain. The model writes the scene's prose directly
    from this description, so give concrete, stageable details — not a theme or a summary."""

    writing_styles: list[str]
    """1-2 directive entries stating the writing technique for this scene's prose: narrative
    voice and point of view, sentence rhythm, tone and atmosphere, dialogue handling, and
    description density. The model writes the prose directly from these, so name concrete,
    applicable techniques — not a genre label or a theme."""

    writing_constraints: list[str]
    """1-2 entries stating the hard writing constraints that bind this scene's prose: whose
    head it stays in (no head-hopping), where this beat may start or end, and scene-specific
    dialogue or sensory restrictions. Keep this scene inside its own Description: never order
    events that belong to another scene. The story's constraints are shown above as the rules
    in force — carry forward the ones that must still bind this scene, since this list alone
    reaches the prose prompt."""


class StoryPlan(WeightedPlan):
    """Plan of a single story; its weight allocates the chapter's expected word count."""

    description: str
    """1 sentence per event this story will stage, in order — as many sentences as its events
    require: name who does what to whom and what changes by the end, and close with the state
    the story ends in. Preserve agency exactly — never swap who acts and who is acted upon,
    never merge two events into one sentence, and never add an event the Chapter Description
    above does not contain. It is shown when planning the story's scenes, so the events
    written here are exactly what the scenes must stage."""

    writing_styles: list[str]
    """1-2 directive entries stating the writing style its scenes should share: a consistent
    voice, tone, and technique across the story's scenes. Empty list when the chapter's
    style already suffices."""

    writing_constraints: list[str]
    """1-2 entries stating the hard writing constraints binding this story as a whole: its own
    point of view or tense, how its scenes progress, and prohibitions spanning its scenes.
    Never an event order spanning other stories — the ordered story list already fixes the
    chapter's sequencing. The chapter's constraints are shown above as the rules in force;
    carry forward the ones that must still bind this story."""


class ChapterPlan(WeightedPlan):
    """Plan of a single chapter; its weight allocates the novel's expected word count."""

    description: str
    """1 sentence per event of this chapter's share of the Novel Outline, in order — as many
    sentences as its events require: name who does what to whom and how each event lands, and
    close with the state the chapter ends in. Preserve agency exactly — never swap who acts and
    who is acted upon, never merge two events into one sentence, never omit an event of its
    share, and never add one the outline does not contain. It is shown when planning the
    chapter's stories, so the events written here are exactly what the stories must stage."""

    writing_styles: list[str]
    """1-2 directive entries stating the writing style its stories should follow: the
    chapter's narrative voice, tone, and pacing. Empty list when the novel's style
    already suffices."""

    writing_constraints: list[str]
    """2-3 entries stating the hard writing constraints binding this chapter: its own point of
    view or tense and prohibitions spanning its stories. Never an event order spanning the
    whole chapter — the ordered story list you propose is what sequences it, so an order
    written here would be re-planned inside whichever story reads it. The novel's constraints
    are shown above as the rules in force; carry forward the ones that must still bind this
    chapter."""


class NovelPlan(WeightedPlan, WordCount):
    """Plan of the novel itself: metadata only, chapters are planned separately."""

    description: str
    """12-20 sentences condensing the Novel Outline into the novel's complete event chain: walk
    the outline in order and restate every event it contains — who does what to whom and how
    each one lands — ending with the state the story ends in. Preserve agency exactly: never
    swap who acts and who is acted upon, never merge two outline events into one sentence,
    never omit an event, and never add one the outline does not contain. Convey genre and tone
    through these facts, never as a tagline. This description seeds every chapter's planning
    prompt, so its event chain is the fidelity contract every later layer must keep."""

    writing_styles: list[str]
    """6-12 directive entries stating the novel's overall writing style: narrative voice,
    tone, rhythm, and recurring techniques. They seed the style guidance of every chapter,
    story, and scene."""

    writing_constraints: list[str]
    """4-8 entries stating the novel's standing rules: point of view, tense, quality standards
    extracted carefully from the outline. They are shown to every chapter planner as the rules
    in force and are never merged into the chapters' own lists."""


class ScenePlans(JSONList[ScenePlan]):
    """The complete, ordered breakdown of the one Story into its scenes — nothing omitted, nothing extra.

    Each element plans exactly one scene of that story, in narrative order: the first scene
    begins exactly where the Story's Description begins, the last ends where it ends, and
    together they dramatise the whole Description exactly once. Each scene carries only its
    own share of the story — a beat owned by another scene of this list, or by a sibling
    story of the same chapter, is never staged again here.
    """


class StoryPlans(JSONList[StoryPlan]):
    """The complete, ordered breakdown of the one Chapter into its stories — nothing omitted, nothing extra.

    Each element plans exactly one story of that chapter, in narrative order: the first story
    begins exactly where the Chapter's Description begins, the last ends where it ends, and
    together they dramatise the whole Description exactly once. Each story carries only its
    own share of the chapter — a beat owned by another story of this list, or by a story of
    another chapter, is never staged again here.
    """


class ChapterPlans(JSONList[ChapterPlan]):
    """The complete, ordered breakdown of the one Novel into its chapters — nothing omitted, nothing extra.

    Each element plans exactly one chapter of the novel, in reading order: the first chapter
    begins exactly where the Novel's Description begins, the last ends where it ends, and
    together they dramatise the whole Description exactly once. Each chapter carries only its
    own share of the novel — a beat owned by another chapter of this list is never staged
    again here.
    """
