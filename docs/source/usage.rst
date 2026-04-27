Usage
=====

Overview
--------

Fabricatio is a streamlined Python library for building LLM applications using an event-based agent structure. It features:

- **Event-Driven Architecture**: Robust task management through an EventEmitter pattern
- **LLM Integration & Templating**: Seamlessly interact with large language models and dynamic content generation
- **Async & Extensible**: Fully asynchronous execution with easy extension via custom actions and workflows

Basic Example
-------------

Here's a simple "Hello World" example:

.. code-block:: python

   """Example of a simple hello world program using fabricatio."""

   from typing import Any

   # Import necessary classes from the namespace package.
   from fabricatio import Action, Event, Role, Task, WorkFlow, logger

   # Create an action.
   class Hello(Action):
       """Action that says hello."""
       
       output_key: str = "task_output"

       async def _execute(self, **_) -> Any:
           ret = "Hello fabricatio!"
           logger.info("executing talk action")
           return ret


   # Create the role and register the workflow.
   (Role()
    .register_workflow(Event.quick_instantiate("talk"), WorkFlow(name="talk", steps=(Hello,)))
    .dispatch())


   # Make a task and delegate it to the workflow registered above.
   assert Task(name="say hello").delegate_blocking("talk") == "Hello fabricatio!"

Async Usage
-----------

For asynchronous execution:

.. code-block:: python

   import asyncio
   from fabricatio import Action, Role, Task, logger, WorkFlow, Event
   from typing import Any


   class Hello(Action):
       output_key: str = "task_output"

       async def _execute(self, **_) -> Any:
           return "Hello fabricatio!"

   async def main() -> None:
       role = Role()
       role.register_workflow(
           Event.quick_instantiate("talk"),
           WorkFlow(name="talk", steps=(Hello,))
       )
       role.dispatch()

       result = await Task(name="say hello").delegate("talk")
       logger.success(f"Result: {result}")

   if __name__ == "__main__":
       asyncio.run(main())

Delegation Modes
^^^^^^^^^^^^^^^^

Fabricatio provides two delegation modes:

- ``delegate()`` (async, non-blocking): Returns a ``Task`` handle. Use this when
  you need to run multiple tasks concurrently or want to avoid blocking the event
  loop.
- ``delegate_blocking()`` (sync): Blocks until the task completes. Use this in
  synchronous contexts or simple scripts where concurrency is not needed.

Fire-and-forget: You can call ``delegate()`` and discard the result if you only
need to trigger the side effect. The task will still be processed by the Role.

Why async matters: Concurrent task execution lets you interleave LLM calls,
database queries, and external API requests without blocking the event loop.
This is critical for chat loops, streaming responses, and real-time applications
where latency must be kept low.

Usage Scenarios
---------------

Fabricatio supports various usage scenarios:

Simple Chat
  Interactive conversational loop. Demonstrates ``Action`` as a stateful chat
  handler — each turn appends to conversation history, and the workflow persists
  context across interactions.

Retrieval-Augmented Generation (RAG)
  Retrieves relevant documents *before* the LLM call. Shows how ``Action``\ s
  compose external data (embeddings, vector DB) with generation — the retrieval
  step feeds context into the prompt step.

Article Extraction
  Parses and injects structured data into vector databases. Demonstrates
  multi-step pipelines: fetch, parse, chunk, embed, and store — each a separate
  ``Action``.

Propose Task
  LLM-driven task decomposition from natural language. The LLM analyses a user
  request and breaks it into sub-tasks, each of which can be dispatched as a new
  workflow.

Code Review
  Demonstrates the review→correct workflow pattern: review code, collect
  feedback, then apply corrections in a follow-up action — all within the same
  workflow.

Write Outline
  Demonstrates structured output generation with typst formatting. The
  ``Action`` returns a structured schema that is rendered into a formatted
  document.

For detailed examples and advanced usage patterns, explore the ``examples/`` directory in the repository.

Key Concepts
------------

**Actions**
  The basic unit of work in Fabricatio. Each action performs a specific task and can be chained together.
  *Why:* Encapsulate LLM calls and side effects so they're composable and testable.

**Workflows**
  A sequence of actions that define how tasks are processed.
  *Why:* Chain actions into deterministic pipelines — each step's output feeds the next.

**Events**
  Triggers that initiate workflows. Events follow an event-driven architecture pattern.
  *Why:* Decouple task submission from execution — the same event can trigger different workflows in different Roles.

**Roles**
  Entities that manage workflows and handle task delegation.
  *Why:* Own workflows and LLM configuration, enabling different agents with different capabilities.

**Tasks**
  Work items that get processed through workflows.
  *Why:* Carry state through a workflow, track dependencies, and support cancellation.

Getting Started
---------------

1. Install fabricatio with desired capabilities
2. Define your actions by subclassing ``Action``
3. Create workflows combining your actions
4. Register workflows with roles using events
5. Submit tasks for processing

   ``Task.delegate(event_name)`` dispatches the task to the ``Role`` that owns
   the matching workflow. The task carries state (``init_context``,
   ``dependencies``) across workflow steps, so each action in the chain has
   access to previous results.

For detailed examples and advanced usage patterns, explore the ``examples/`` directory in the repository.
