"""Example of proposing a task to a role."""

import asyncio
from typing import Dict, List, Set, Unpack

import orjson
from fabricatio import Action, JsonCapture, Role, WorkFlow, logger
from fabricatio.models.events import Event
from fabricatio.models.task import Task


class Rate(Action):
    """Rate the task."""

    name: str = "rate"
    output_key: str = "task_output"

    async def _execute(self, to_rate: List[str], rate_topic: str, dimensions: Set[str], **_) -> [Dict[str, float]]:
        """Rate the task."""
        return await asyncio.gather(
            *[
                self.rate(
                    target,
                    rate_topic,
                    dimensions,
                )
                for target in to_rate
            ]
        )


class WhatToRate(Action):
    """Figure out what to rate."""

    name: str = "figure out what to rate"

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


async def main() -> None:
    """Main function."""
    role = Role(
        name="TaskRater",
        description="A role that can rate tasks.",
        registry={
            Event.instantiate_from("rate_food").push_wildcard().push("pending"): WorkFlow(
                name="Rate food",
                steps=(WhatToRate, Rate),
                extra_init_context={
                    "rate_topic": "If this food is cheap and delicious",
                    "dimensions": {"taste", "price", "quality", "safety", "healthiness", "freshness"},
                },
            ),
        },
    )
    task = await role.propose(
        "rate for rotten apple, ripen banana, fresh orange, giga-burger, smelly pizza with flies on it, and a boiling instant coffee",
    )
    rating = await task.move_to("rate_food").delegate()

    logger.success(f"Result: \n{rating}")


if __name__ == "__main__":
    asyncio.run(main())
