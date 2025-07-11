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

   from fabricatio import Action, Event, Role, Task, WorkFlow, logger


   class Hello(Action):
       """Action that says hello."""

       output_key: str = "task_output"

       async def _execute(self, **_) -> Any:
           ret = "Hello fabricatio!"
           logger.info("executing talk action")
           return ret


   # Register the workflow and dispatch
   (Role()
    .register_workflow(Event.quick_instantiate("talk"), WorkFlow(name="talk", steps=(Hello,)))
    .dispatch())

   # Execute the task
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

Available Examples
------------------

Fabricatio comes with numerous examples demonstrating various use cases:

**Basic Examples:**

- ``examples/minor/hello_fabricatio.py`` - Simple hello world
- ``examples/minor/write_a_poem.py`` - Creative writing
- ``examples/simple_chat/chat.py`` - Basic chat interface

**Advanced Examples:**

- ``examples/simple_rag/simple_rag.py`` - Retrieval-Augmented Generation
- ``examples/extract_article/extract.py`` - Article extraction
- ``examples/propose_task/propose.py`` - Task proposal system
- ``examples/reviewer/review.py`` - Code review automation
- ``examples/write_outline/write_outline.py`` - Outline generation

**Specialized Examples:**

- ``examples/anki_deck/deck_gen.py`` - Anki deck generation
- ``examples/make_diary/diary.py`` - Diary creation from git commits
- ``examples/search_bibtex/search.py`` - BibTeX search functionality
- ``examples/yue/compose.py`` - Yue language composition

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
