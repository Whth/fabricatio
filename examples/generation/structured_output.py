"""Demonstrate structured output via the Propose capability.

``propose()`` asks the LLM to fill in a Pydantic schema that extends
``ProposedAble``.  The response is parsed and validated automatically,
returning a typed Python instance.
"""

import asyncio

from fabricatio import Role as BaseRole
from fabricatio import logger
from fabricatio.capabilities import Propose
from fabricatio_core.models.generic import ProposedAble

# --- Schema (must extend ProposedAble, not plain BaseModel) ---


class Translation(ProposedAble):
    """Structured translation result."""

    original: str
    """The original text."""

    translated: str
    """The translated text."""

    language: str
    """Target language."""


# --- Role that mixes in the Propose capability ---


class Translator(BaseRole, Propose):
    """A role that produces structured translations."""


async def main() -> None:
    """Create a translator role and produce a structured translation."""
    role = Translator(
        name="Translator",
        description="Translates text and returns structured output.",
    )

    result = await role.propose(
        Translation,
        "Translate 'Hello, world!' to French",
    )

    logger.info(f"Original:   {result.original}")
    logger.info(f"Translated: {result.translated}")
    logger.info(f"Language:   {result.language}")


if __name__ == "__main__":
    asyncio.run(main())
