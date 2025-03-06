"""Example of proposing a task to a role."""

import asyncio

from fabricatio import Event, ExtractArticleEssence, Role, WorkFlow


async def main() -> None:
    """Main function."""
    role = Role(
        name="Researcher",
        description="Extract article essence",
        registry={Event.quick_instantiate("article"): WorkFlow(name="extract", steps=(ExtractArticleEssence,))},
    )
    role.propose()


if __name__ == "__main__":
    asyncio.run(main())
