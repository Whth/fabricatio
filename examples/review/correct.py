"""Example of review usage."""

import asyncio

from fabricatio import Role as BaseRole
from fabricatio import logger
from fabricatio.capabilities import Correct, Review
from fabricatio_core.utils import ok


class Role(BaseRole, Review, Correct):
    """Reviewer role."""


async def main() -> None:
    """Main function."""
    role = Role(
        name="Correction Officer",
        description="A role that reviews the code.",
    )

    code = await role.aask(
        "write a cli app using rust with clap which can generate a basic manifest of a standard rust project, output code only,no extra explanation"
    )

    logger.info(f"Code: \n{code}")

    imp = ok(await role.review_string(code, topic="If the cli app is build with the derive feat enabled"))

    corrected = await role.correct_string(code, improvement=imp)
    logger.info(f"Corrected: \n{corrected}")


if __name__ == "__main__":
    asyncio.run(main())
