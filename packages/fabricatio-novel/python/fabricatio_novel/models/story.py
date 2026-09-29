"""Output model for a composed story: the story plan plus its materialized scenes."""

from typing import Self

from fabricatio_capabilities.models.generic import WordCount

from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import StoryPlan
from fabricatio_novel.models.scene import Scene


class Story(StoryPlan, WordCount):
    """A composed story: its plan fields and the scenes it contains.

    Both writing channels mirror the story context's own lists — the entries in force
    at this level, the same lists its prompts rendered — rather than the plan's
    contributions alone.
    """

    scenes: list[Scene]

    @property
    def exact_word_count(self) -> int:
        """Sum the exact word counts of every scene in this story."""
        return sum(c.exact_word_count for c in self.scenes)

    @classmethod
    def from_context(cls, ctx: StoryContext) -> Self:
        """Materialize a story from its story context, materializing each scene recursively."""
        return cls(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=ctx.expected_word_count,
            writing_styles=list(ctx.writing_styles),
            writing_constraints=list(ctx.writing_constraints),
            scenes=[Scene.from_context(sc) for sc in ctx.child_contexts],
        )
