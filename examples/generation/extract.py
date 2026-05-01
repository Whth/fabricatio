"""Demonstrate structured extraction via the Extract capability.

``extract()`` takes unstructured text and a target Pydantic schema
(extending ``ProposedAble``), then asks the LLM to pull out the
relevant fields and return a typed instance.
"""

import asyncio

from fabricatio import Role as BaseRole
from fabricatio import logger
from fabricatio.capabilities import Extract
from fabricatio_core.models.generic import ProposedAble
from pydantic import Field

# --- Target schema ---

class PersonInfo(ProposedAble):
    """Information about a person extracted from free-form text."""

    name: str
    """Full name."""

    age: int | None = None
    """Age in years, if mentioned."""

    occupation: str | None = None
    """Job title or profession."""

    skills: list[str] = Field(default_factory=list)
    """Known technical or professional skills."""


# --- Role with Extract capability ---

class Extractor(BaseRole, Extract):
    """A role that extracts structured data from text."""


async def main() -> None:
    """Extract structured person info from free-form text."""
    role = Extractor(
        name="Extractor",
        description="Extracts structured information from unstructured text.",
    )

    text = """
    John Doe is a 35-year-old software engineer at Google.
    He has 10 years of experience and specializes in Python and Rust.
    """

    result = await role.extract(PersonInfo, text)

    logger.info(f"Name:       {result.name}")
    logger.info(f"Age:        {result.age}")
    logger.info(f"Occupation: {result.occupation}")
    logger.info(f"Skills:     {result.skills}")


if __name__ == "__main__":
    asyncio.run(main())
