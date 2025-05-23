"""Example of a simple hello world program using fabricatio as a pytest integration test."""

import pytest

from fabricatio import Action, Event, Role, Task, WorkFlow, logger

# Define the Task and Action outside the test function if they are to be reused
# or are part of the setup for multiple tests.
# For a single test, they can also be defined inside.

task_fixture = Task(name="say hello")


class Hello(Action):
    """Action that says hello."""

    output_key: str = "task_output"

    async def _execute(self, **_) -> str:
        logger.info("executing talk action")
        return "Hello fabricatio!"


@pytest.mark.asyncio
async def test_hello_fabricatio_workflow(caplog):
    """
    Tests the basic 'say hello' workflow in fabricatio.
    It defines a 'talker' role with a simple workflow that returns 'Hello fabricatio!',
    delegates a task to this role, and asserts the output.
    """
    # Ensure a clean state for roles/registries if running multiple tests,
    # or manage this globally if appropriate for your test setup.
    # For this example, we assume a fresh environment or that Role re-registration is idempotent/handled.

    Role(name="talker", description="talker role",
         registry={Event.quick_instantiate("talk"): WorkFlow(name="talk", steps=(Hello,))})

    # Delegate the task and get the result
    result = await task_fixture.delegate("talk")

    # Assert the expected outcome
    assert result == "Hello fabricatio!"

    # Optionally, check logs if that's part of the test criteria
    # caplog is a pytest fixture to capture log output
    assert "executing talk action" in caplog.text
    # logger.success is not standard, assuming it's a custom level or alias for info/debug
    # If logger.success logs at INFO level or above:
    assert f"Emitted finished event for task say hello" in caplog.text  # This might be an actual log from your main
    # but here we are asserting the result directly.
    # The original logger.success call is removed from the test logic itself
    # and replaced by an assertion.
