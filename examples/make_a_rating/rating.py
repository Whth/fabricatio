"""Example of proposing a task to a role."""

import asyncio
from typing import Dict, List, Set, Unpack

import orjson
from fabricatio import Action, JsonCapture, Role, WorkFlow, logger
from fabricatio.capabilities.rating import Rating
from fabricatio.models.events import Event
from fabricatio.models.task import Task


class Rate(Action, Rating):
    """Rate the task."""

    output_key: str = "task_output"

    async def _execute(self, to_rate: List[str], rate_topic: str, criteria: Set[str], **_) -> List[Dict[str, float]]:
        logger.info(f"Rating the: \n{to_rate}")
        """Rate the task."""
        return await self.rate(
            to_rate,
            rate_topic,
            criteria,
        )


class WhatToRate(Action):
    """Figure out what to rate."""

    output_key: str = "to_rate"

    async def _execute(self, task_input: Task, rate_topic: str, **cxt: Unpack) -> List[str]:
        def _validate(resp: str) -> List[str] | None:
            if (
                (cap := JsonCapture.convert_with(resp, orjson.loads)) is not None
                and isinstance(cap, list)
                and all(isinstance(i, str) for i in cap)
            ):
                return cap
            return None

        return await self.aask_validate(
            f"This is task briefing:\n{task_input.briefing}\n\n"
            f"We are talking about {rate_topic}. you need to extract targets to rate into a the JSON array\n"
            f"The response SHALL be a JSON array of strings within the codeblock\n"
            f"# Example\n"
            f'```json\n["this is a target to rate", "this is another target to rate"]\n```',
            _validate,
        )


class MakeCriteria(Action, Rating):
    """Make criteria for rating."""

    output_key: str = "criteria"

    async def _execute(self, rate_topic: str, to_rate: List[str], **cxt: Unpack) -> Set[str]:
        criteria = await self.draft_rating_criteria_from_examples(rate_topic, to_rate)
        logger.info(f"Criteria: \n{criteria}")
        return set(criteria)


class MakeCompositeScore(Action, Rating):
    """Make a composite score."""

    output_key: str = "task_output"

    async def _execute(self, rate_topic: str, to_rate: List[str], **cxt: Unpack) -> List[float]:
        return await self.composite_score(
            rate_topic,
            to_rate,
        )


class Best(Action, Rating):
    """Select the best."""

    output_key: str = "task_output"

    async def _execute(self, rate_topic: str, to_rate: List[str], **cxt: Unpack) -> str:
        return (await self.best(to_rate, topic=rate_topic)).pop(0)


async def main() -> None:
    """Main function."""
    role = Role(
        name="TaskRater",
        description="A role that can rate tasks.",
        registry={
            Event.quick_instantiate("rate_food"): WorkFlow(
                name="Rate food",
                steps=(WhatToRate, Rate),
                extra_init_context={
                    "rate_topic": "If this food is cheap and delicious",
                    "criteria": {"taste", "price", "quality", "safety", "healthiness"},
                },
            ),
            Event.quick_instantiate("make_criteria_for_food"): WorkFlow(
                name="Make criteria for food",
                steps=(WhatToRate, MakeCriteria, Rate),
                extra_init_context={
                    "rate_topic": "if the food is 'good'",
                },
            ),
            Event.quick_instantiate("make_composite_score"): WorkFlow(
                name="Make composite score",
                steps=(WhatToRate, MakeCompositeScore),
                extra_init_context={
                    "rate_topic": "if the food is 'good'",
                },
            ),
            Event.quick_instantiate("best"): WorkFlow(
                name="choose the best",
                steps=(WhatToRate, Best),
                extra_init_context={"rate_topic": "if the food is 'good'"},
            ),
        },
    )
    task = await role.propose_task(
        "rate these food, so that i can decide what to eat today. choco cake, strawberry icecream, giga burger, cup of coffee, rotten bread from the trash bin, and a salty of fruit salad",
    )
    rating = await task.delegate("rate_food")

    logger.success(f"Result: \n{rating}")

    generated_criteria = await task.delegate("make_criteria_for_food")

    logger.success(f"Generated Criteria: \n{generated_criteria}")

    composite_score = await task.delegate("make_composite_score")

    logger.success(f"Composite Score: \n{composite_score}")

    best = await task.delegate("best")

    logger.success(f"Best: \n{best}")


if __name__ == "__main__":
    asyncio.run(main())
