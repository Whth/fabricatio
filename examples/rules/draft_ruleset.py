"""Example of using the library."""

import asyncio

from fabricatio import Event, Role, WorkFlow, logger
from fabricatio.actions.output import PersistentAll
from fabricatio.actions.rules import DraftRuleSet
from fabricatio.models.task import Task


async def main() -> None:
    """Main function."""
    Role(
        name="Undergraduate Researcher",
        llm_temperature=1.15,
        llm_model="openai/deepseek-v3-250324",
        llm_rpm=1000,
        llm_tpm=3000000,
        llm_max_tokens=8190,
        registry={
            Event.quick_instantiate(ns := "article"): WorkFlow(
                name="write ruleset",
                description="Generate an outline for an article. dump the outline to the given path. in typst format.",
                steps=(
                    DraftRuleSet(ruleset_requirement="1.when try to use an article as reference cited in our article, you should obey the format like (author1, author2 et al., YYYY)\n"
                                                     "2.we use typst to generate numeric citation. For example, for an article whose `bibtex_key` is `YanWindEnergy2018`, you can create a numeric citation by typing `#cite(<YanWindEnergy2018>)`, which could be processed and output as a numeric citation like `[1]` in the upper right corner of text.\n"
                                                     "3.in addition, you can use `#cite()` to cite multiple article at once, for example, there are three articles whose `bibtex_key` are `YanWindEnergy2018`, `YanWindEnergy2019`, `YanWindEnergy2020, you can cite them three as numeric citation by typing `#cite(<YanWindEnergy2018>)#cite(<YanWindEnergy2019>)#cite(<YanWindEnergy2020>)` which could be processed and output as a numeric citation like `[1,2,3]` in the upper right corner of text."
                                                     "4.to cover more references, we usually cite more than one articles that have similar opinions in a single sentence if possible."),
                    PersistentAll(persist_dir="persistent"),
                ),
            )
        },
    )

    proposed_task = Task(name="write an article")
    path = await proposed_task.delegate(ns)
    logger.success(f"The rule is saved in:\n{path}")


if __name__ == "__main__":
    asyncio.run(main())
