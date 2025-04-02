"""Example of review usage."""

import asyncio

from fabricatio import Role, logger
from fabricatio.capabilities.censor import Censor


class Coder(Role, Censor):
    """Reviewer role."""


async def main() -> None:
    """Main function."""
    role = Coder(
        name="Bob",
        description="A role that reviews the code.",
    )

    code = await role.aask(
        "write a cli app using rust with clap which can generate a basic manifest of a standard rust project, output code only,no extra explanation"
    )

    ruleset = await role.draft_ruleset("should not use clap to write cli.", rule_count=1)
    logger.success(f"Code: \n{code}")
    code = await role.censor_string(code, ruleset)

    logger.success(f"Code: \n{code}")


if __name__ == "__main__":
    asyncio.run(main())
