"""Drive a string edit by natural-language request using ``fabricatio-diff``.

The agent sees the source with each line tagged ``LINE:HASH|content``,
asks an LLM to emit anchor-based edit ops, applies them through the Rust
primitives, and asks a second LLM to judge whether the requirement is met.
The loop retries until the judge says YES or ``max_iterations`` is reached.

Routing-group variant for the edit call comes from ``fabricatio_core.rust``
(``TASK`` / ``SMOL`` / ``TINY`` / ``SLOW`` / ``PLAN``); the judge uses its
own default routing and is not steered by this argument.

Run with a configured model provider (e.g. ``OPENAI_API_KEY`` set, or a
local config under ``fabricatio.toml``)::

    python examples/diff/hashline_diff.py
"""

import asyncio

from fabricatio import Role as BaseRole
from fabricatio_core import logger
from fabricatio_core.rust import TASK
from fabricatio_diff.capabilities.hashline_edit import (
    HashlineEdit,
    HashlineEditExhaustedError,
)

# --- Role with the HashlineEdit capability ---


class Coder(BaseRole, HashlineEdit):
    """An agent that edits code from a natural-language requirement."""


async def main() -> None:
    """Edit a Python function on user request and print the result."""
    agent = Coder(name="diff-coder")

    source = """\
def greet(name):
    msg = "Hello, " + name
    print(msg)
greet("world")
"""

    requirement = (
        'Inside `greet`, replace the concatenation `msg = "Hello, " + name` with an f-string `msg = f"Hi, {name}"`.'
    )

    try:
        # `send_to` defaults to TASK (see fabricatio_core.rust). Pass
        # e.g. SMOL to use a cheaper model for the edit.
        result = await agent.hashline_diff(source, requirement, send_to=TASK)
    except HashlineEditExhaustedError as err:
        logger.error(f"Could not satisfy the requirement in {err.iterations} iterations; last error: {err.last_error}")
        logger.info("Last source the loop produced:\n" + err.last_source)
        return

    logger.info("--- edited source ---")
    logger.info(result.content)

    logger.info("--- meta ---")
    logger.info(f"iterations  : {result.iterations}")
    logger.info(f"satisfied   : {result.satisfied}")
    logger.info(f"applied ops : {[op.kind for op in result.applied_edits]}")
    logger.info(f"history     : {result.history}")


if __name__ == "__main__":
    asyncio.run(main())
