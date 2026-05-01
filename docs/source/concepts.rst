Core Concepts
=============

This guide explains the fundamental concepts that power Fabricatio.

Event-Driven Architecture
-------------------------

Fabricatio uses an event-driven architecture where agents respond to events rather than direct method calls. This pattern enables loose coupling and flexible composition.

Event System
~~~~~~~~~~~~

Events are the triggers that initiate workflow execution:

.. code-block:: python

    from fabricatio import Event

    # Create an event by name
    event = Event.quick_instantiate("talk")
    
    # Collapse to string for registration
    event_key = event.collapse()  # "talk"

Events support:

- **Quick instantiation**: ``Event.quick_instantiate(name)`` 
- **String conversion**: ``.collapse()`` returns the event name
- **Custom payload**: Events can carry data (see advanced usage)

EventEmitter Pattern
~~~~~~~~~~~~~~~~~~~~

The ``EventEmitter`` provides publish-subscribe functionality:

.. code-block:: python

    from fabricatio import EventEmitter

    emitter = EventEmitter()
    
    def handler(data):
        print(f"Received: {data}")
    
    # Subscribe
    emitter.on("message", handler)
    
    # Publish
    emitter.emit("message", "Hello!")

Roles
-----

A ``Role`` is the primary agent entity that orchestrates skills and LLM interactions.

.. code-block:: python

    from fabricatio import Role, Event, WorkFlow

    role = Role(
        name="assistant",
        description="A helpful assistant",
        skills={
            Event.quick_instantiate("help").collapse(): WorkFlow(
                name="help",
                steps=(HelpAction,)
            )
        }
    )

Role Lifecycle
~~~~~~~~~~~~~~

.. mermaid::

   flowchart TD
       A["1. Create Role with skills registered"]
       B["2. Propose task or create directly"]
       C["3. Delegate task to event name"]
       D["4. Event triggers WorkFlow"]
       E["5. Actions execute in sequence"]
       F["6. Result returned to task"]
       A --> B --> C --> D --> E --> F

Skills
------

A ``Skill`` maps an Event to a WorkFlow:

.. code-block:: python

    from fabricatio import Skill

    skill = Skill(
        event=Event.quick_instantiate("analyze"),
        workflow=WorkFlow(name="analyze", steps=(AnalyzeAction,))
    )

Skills are stored in the Role's skill registry and retrieved by event name during delegation.

WorkFlows
---------

A ``WorkFlow`` defines a sequence of Actions:

.. code-block:: python

    from fabricatio import WorkFlow, Action

    class Step1(Action):
        async def _execute(self, **kwargs):
            # First step
            return "step1_result"

    class Step2(Action):
        async def _execute(self, **kwargs):
            # Second step
            return "step2_result"

    workflow = WorkFlow(
        name="multi_step",
        steps=(Step1, Step2)  # Executes in order
    )

WorkFlow Execution Flow
~~~~~~~~~~~~~~~~~~~~~~~

.. mermaid::

   flowchart TD
       A["WorkFlow.start()"]
       B["Execute Step 1"]
       C["Execute Step 2"]
       D["Execute Step N"]
       E["WorkFlow.complete()"]
       A --> B
       B -->|"_execute() returns result"| C
       C -->|"_execute() returns result"| D
       D -->|"_execute() returns result"| E

Tasks
-----

``Task`` represents a unit of work:

.. code-block:: python

    from fabricatio import Task

    # Create a task directly
    task = Task(name="analyze", briefing="Analyze the code")

    # Or propose from role (LLM-generated)
    task = await role.propose_task("Write a report on X")

Task Properties
~~~~~~~~~~~~~~~

- ``name``: Identifier for the task
- ``briefing``: Instructions for execution
- ``input``: Input data for actions
- ``output``: Result after execution
- ``status``: Current state (pending, running, completed, failed)

Delegation Modes
~~~~~~~~~~~~~~~~

.. code-block:: python

    # Blocking (waits for completion)
    result = await task.delegate_blocking("event_name")

    # Non-blocking (returns immediately)
    # Returns coroutine that can be awaited later
    coro = await task.delegate("event_name")
    result = await coro

    # Fire-and-forget
    task.delegate("event_name")  # No awaiting

Actions
-------

``Action`` is the atomic execution unit:

.. code-block:: python

    from fabricatio import Action
    from typing import Any

    class MyAction(Action):
        output_key: str = "my_result"
        
        async def _execute(self, **kwargs) -> Any:
            # Access task input
            task_input = kwargs.get("task_input")
            
            # Access previous step results
            prev_results = kwargs.get("workflow_results", {})
            
            # Return result
            return "my_output"

Action Lifecycle
~~~~~~~~~~~~~~~~

.. mermaid::

   flowchart TD
       A["Action._execute() called"]
       B["Pre-execution\n(setup, validation)"]
       C["Execute logic\n(_execute override point)"]
       D["Post-execution\n(result storage, cleanup)"]
       E["Return result"]
       A --> B --> C --> D --> E

Capability Mixins
-----------------

Capabilities are mixins that provide reusable functionality:

LLM Capability
~~~~~~~~~~~~~~

``UseLLM`` provides LLM interaction:

.. code-block:: python

    from fabricatio.capabilities import UseLLM

    class MyAction(Action, UseLLM):
        async def _execute(self, **kwargs):
            # Simple text request
            response = await self.aask("What is Python?")
            
            # Structured output
            structured = await self.aask_structured(
                "Extract info",
                response_format=MyModel
            )
            
            # With custom parameters
            custom = await self.aask(
                "Explain",
                temperature=0.5,
                max_tokens=100
            )

Other Capabilities
~~~~~~~~~~~~~~~~~~

.. note::

   The ``sphinxcontrib-mermaid`` package that renders these diagrams is `seeking new maintainers <https://github.com/mgaitan/sphinxcontrib-mermaid/issues/148>`_. Consider contributing if you're interested.

.. mermaid::

   %%{init: {'themeVariables': {'fontFamily': 'monospace'}}}%%
   erDiagram
       Capability {
           string UseLLM "LLM interaction methods"
           string Review "Code/content review methods"
           string Extract "Structured extraction from text"
           string ProposeTask "Task proposal generation"
           string Improve "Content improvement"
           string Rule "Rule-based processing"
           string MilvusRAG "Vector store RAG"
       }

Logger Integration
------------------

Fabricatio provides structured logging:

.. code-block:: python

    from fabricatio import logger

    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")

Logger output includes:

- Timestamp
- Log level
- Module name
- Message

Logger Configuration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

    [debug]
    log_level = "DEBUG"  # or INFO, WARNING, ERROR

Async Execution
---------------

All Fabricatio operations are async-first:

.. code-block:: python

    import asyncio

    async def main():
        # All operations are async
        result = await role.aask("Hello")
        result = await task.delegate("event")
        
        # Run multiple tasks concurrently
        results = await asyncio.gather(
            task1.delegate("event"),
            task2.delegate("event"),
            task3.delegate("event"),
        )

    asyncio.run(main())

Best Practices
--------------

1. **Always use async/await**
   Never mix sync and async code without proper handling.

2. **Handle exceptions**
   Use try/except for graceful error handling:

   .. code-block:: python

       try:
           result = await task.delegate("event")
       except Exception as e:
           logger.error(f"Task failed: {e}")

3. **Set appropriate timeouts**
   Configure timeouts for long-running operations:

   .. code-block:: python

       [llm]
       timeout = 120  # seconds

4. **Use structured output for reliability**
   Prefer ``aask_structured()`` over ``aask()`` when possible.
