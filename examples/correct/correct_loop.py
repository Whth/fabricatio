"""Example of review usage."""

import asyncio

from fabricatio import Role, logger
from questionary import confirm
from rich import print as r_print


async def main() -> None:
    """Main function."""
    role = Role(
        name="Reviewer",
        description="A role that reviews the code.",
    )

    code = await role.aask(
        "write a cli app using rust with clap which can generate a basic manifest of a standard rust project, output code only,no extra explanation, you should using derive mode of clap."
    )

    logger.success(f"Code: \n{code}")

    while await confirm("Do you want to review the code?").ask_async():
        code = await role.correct_string(code, topic="If the cli app is of good design", supervisor_check=False)
        r_print(code)
    logger.success(f"Corrected: \n{code}")


if __name__ == "__main__":
    asyncio.run(main())
