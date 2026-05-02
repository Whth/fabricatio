"""Demonstrate content review via the Review capability.

``review_string()`` analyses text against a topic and produces an
``Improvement`` object containing identified problems and candidate
solutions.  This is the first half of the review-then-correct workflow;
the ``Correct`` capability can apply those solutions automatically.
"""

import asyncio

from fabricatio import Role as BaseRole
from fabricatio import logger
from fabricatio.capabilities import Review
from fabricatio_core.utils import ok

# --- Role with the Review capability ---


class Reviewer(BaseRole, Review):
    """A role that reviews text content for problems and solutions."""


async def main() -> None:
    """Review text for grammar and style issues, then display the findings."""
    role = Reviewer(
        name="Reviewer",
        description="Reviews text content for grammar and style issues.",
    )

    original = """
    The quick brown fox jumped over the lazy dog.
    This is a old way to test typewriters.
    """

    # review_string produces an Improvement: problems + candidate solutions
    improvement = ok(
        await role.review_string(original, topic="grammar and style clarity"),
    )

    logger.info(f"Focused on: {improvement.focused_on}")
    for i, ps in enumerate(improvement.problem_solutions, 1):
        logger.info(f"Problem {i}: {ps.problem.name}")
        logger.info(f"  Cause:     {ps.problem.description}")
        logger.info(f"  Severity:  {ps.problem.severity_level}")
        logger.info(f"  Solutions: {len(ps.solutions)}")


if __name__ == "__main__":
    asyncio.run(main())
