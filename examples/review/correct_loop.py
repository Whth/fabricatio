"""Example of review usage."""

import asyncio

from fabricatio import Role as RoleBase
from fabricatio import logger
from fabricatio.capabilities import Correct, Review
from questionary import confirm
from rich import print as r_print


class Role(RoleBase, Correct, Review):
    """Role use to review and correct."""


async def main() -> None:
    """Main function."""
    role = Role(
        name="Reviewer",
        description="A role that reviews the code.",
    )

    code = await role.aask(
        "write a cli app using rust with clap which can generate a basic manifest of a standard rust project, output code only,no extra explanation, you should using derive mode of clap."
    )

    logger.info(f"Code: \n{code}")

    while await confirm("Do you want to review the code?").ask_async():
        imp = await role.review_string(code, topic="If the cli app is of good design")

        code = await role.correct_string(code, imp)
        r_print(code)
    logger.info(f"Corrected: \n{code}")


if __name__ == "__main__":
    asyncio.run(main())
