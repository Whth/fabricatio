"""Example of review usage."""

import asyncio

from fabricatio import Role, logger


async def main() -> None:
    """Main function."""
    role = Role(
        name="Reviewer",
        description="A role that reviews the code.",
    )

    code = await role.aask(
        "write a cli app using rust with clap which can generate a basic manifest of a standard rust project, output code only,no extra explanation"
    )

    logger.success(f"Code: \n{code}")
    res = await role.review_string(code, "If the cli app is of good design")
    logger.success(f"Review: \n{res.display()}")
    await res.supervisor_check(True)
    logger.success(f"Review: \n{res.display()}")


if __name__ == "__main__":
    asyncio.run(main())
