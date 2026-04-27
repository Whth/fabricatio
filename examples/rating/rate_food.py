"""Demonstrate the Rating capability — how Fabricatio can decompose a vague request ("what should I eat?") into structured rating criteria, rate each option, and produce composite scores and rankings."""

import asyncio
from typing import Dict, List, Set

from fabricatio import Action, Event, Task, WorkFlow, logger
from fabricatio import Role as RoleBase
from fabricatio.capabilities import ProposeTask, Rating
from fabricatio_core.rust import json_parser
from fabricatio_core.utils import ok


class Role(RoleBase, ProposeTask):
    """Role that can rate tasks using LLM-generated criteria and composite scoring."""


class Rate(Action, Rating):
    """Rate items against given criteria. Uses the Rating capability to evaluate each item and return per-criterion scores."""

    output_key: str = "task_output"

    async def _execute(self, to_rate: List[str], rate_topic: str, criteria: Set[str], **_) -> List[Dict[str, float]]:
        logger.info(f"Rating the: \n{to_rate}")
        return await self.rate(
            to_rate,
            rate_topic,
            criteria,
        )


class WhatToRate(Action):
    """Figure out what to rate."""

    output_key: str = "to_rate"

    async def _execute(self, task_input: Task, rate_topic: str, **_) -> List[str]:
        def _validate(resp: str) -> List[str] | None:
            return json_parser.validate_list(resp, str)

        return await self.aask_validate(
            f"This is task briefing:\n{task_input.briefing}\n\n"
            f"We are talking about {rate_topic}. you need to extract targets to rate into a the JSON array\n"
            f"The response SHALL be a JSON array of strings within the codeblock\n"
            f"# Example\n"
            f'```json\n["this is a target to rate", "this is another target to rate"]\n```',
            _validate,
        )


class MakeCriteria(Action, Rating):
    """Dynamically generate rating criteria from examples. Rather than hardcoding criteria, the LLM analyzes the items and topic to produce relevant evaluation dimensions."""

    output_key: str = "criteria"

    async def _execute(self, rate_topic: str, to_rate: List[str], **_) -> Set[str]:
        criteria = await self.draft_rating_criteria_from_examples(rate_topic, to_rate)
        logger.info(f"Criteria: \n{criteria}")
        return set(criteria)


class MakeCompositeScore(Action, Rating):
    """Produce a single numeric score per item by combining all criteria evaluations. Reduces multi-dimensional ratings to a sortable ranking."""

    output_key: str = "task_output"

    async def _execute(self, rate_topic: str, to_rate: List[str], **_) -> List[float]:
        return await self.composite_score(
            rate_topic,
            to_rate,
        )


class Best(Action, Rating):
    """Select the top-ranked item from a rated list. Delegates to the LLM to pick the best based on the composite evaluation."""

    output_key: str = "task_output"

    async def _execute(self, rate_topic: str, to_rate: List[str], **_) -> str:
        return (await self.best(to_rate, topic=rate_topic)).pop(0)


async def main() -> None:
    """Demonstrate a full rating pipeline: propose a task from natural language, rate with default criteria, generate custom criteria, compute composite scores, and pick the best."""
    role = Role(
        name="TaskRater",
        description="A role that can rate tasks.",
        skills={
            Event.quick_instantiate("rate_food").collapse(): WorkFlow(
                name="Rate food",
                steps=(WhatToRate, Rate),
                extra_init_context={
                    "rate_topic": "If this food is cheap and delicious",
                    "criteria": {"taste", "price", "quality", "safety", "healthiness"},
                },
            ),
            Event.quick_instantiate("make_criteria_for_food").collapse(): WorkFlow(
                name="Make criteria for food",
                steps=(WhatToRate, MakeCriteria, Rate),
                extra_init_context={
                    "rate_topic": "if the food is 'good'",
                },
            ),
            Event.quick_instantiate("make_composite_score").collapse(): WorkFlow(
                name="Make composite score",
                steps=(WhatToRate, MakeCompositeScore),
                extra_init_context={
                    "rate_topic": "if the food is 'good'",
                },
            ),
            Event.quick_instantiate("best").collapse(): WorkFlow(
                name="choose the best",
                steps=(WhatToRate, Best),
                extra_init_context={"rate_topic": "if the food is 'good'"},
            ),
        },
    )
    task = ok(
        await role.propose_task(
            "rate these food, so that i can decide what to eat today. choco cake, strawberry icecream, giga burger, cup of coffee, rotten bread from the trash bin, and a salty of fruit salad",
        ),
        "Failed to propose task.",
    )
    rating = await task.delegate("rate_food")

    logger.info(f"Result: \n{rating}")

    generated_criteria = await task.delegate("make_criteria_for_food")

    logger.info(f"Generated Criteria: \n{generated_criteria}")

    composite_score = await task.delegate("make_composite_score")

    logger.info(f"Composite Score: \n{composite_score}")

    best = await task.delegate("best")

    logger.info(f"Best: \n{best}")


if __name__ == "__main__":
    asyncio.run(main())
