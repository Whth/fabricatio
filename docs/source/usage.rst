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

Usage Scenarios
---------------

Fabricatio supports various usage scenarios:

- Simple Chat
- Retrieval-Augmented Generation (RAG)
- Article Extraction
- Propose Task
- Code Review
- Write Outline

For detailed examples and advanced usage patterns, explore the ``examples/`` directory in the repository.

Key Concepts
------------

**Actions**
  The basic unit of work in Fabricatio. Each action performs a specific task and can be chained together.

**Workflows**
  A sequence of actions that define how tasks are processed.

**Events**
  Triggers that initiate workflows. Events follow an event-driven architecture pattern.

**Roles**
  Entities that manage workflows and handle task delegation.

**Tasks**
  Work items that get processed through workflows.

Getting Started
---------------

1. Install fabricatio with desired capabilities
2. Define your actions by subclassing ``Action``
3. Create workflows combining your actions
4. Register workflows with roles using events
5. Submit tasks for processing

For detailed examples and advanced usage patterns, explore the ``examples/`` directory in the repository.
