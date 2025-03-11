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

    corrected = await role.correct_string(code, topic="If the cli app is of good design", supervisor_check=False)
    logger.success(f"Corrected: \n{corrected}")


if __name__ == "__main__":
    asyncio.run(main())
