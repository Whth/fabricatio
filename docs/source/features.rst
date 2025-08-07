Features
========

Fabricatio provides a powerful set of features designed to streamline the development of LLM applications through its event-driven architecture, seamless LLM integration, and extensible async framework.

Event-Driven Architecture
-------------------------

Fabricatio's core architecture is built around an event-driven model that promotes loose coupling and high cohesion between components. This pattern allows for scalable, maintainable, and flexible application development.

EventEmitter Pattern
~~~~~~~~~~~~~~~~~~~~

At the heart of Fabricatio's event-driven architecture is the ``EventEmitter`` class, which provides a robust mechanism for managing event handling with both exact and wildcard event matching capabilities.

The ``EventEmitter`` supports:

- **Exact Event Matching**: Direct registration and emission of specific events
- **Wildcard Event Matching**: Pattern-based event handling using wildcards (``*``) for flexible event routing
- **Concurrent Event Processing**: Multiple event handlers can be executed concurrently for improved performance
- **Hierarchical Event Structure**: Events can be organized in hierarchical namespaces using configurable separators

Key features of the EventEmitter pattern include:

.. code-block:: python

   from fabricatio import EventEmitter

   # Create an event emitter with custom separator
   emitter = EventEmitter(sep="::")

   # Register handlers for exact events
   emitter.on("user::login", login_handler)
   
   # Register handlers with wildcards for pattern matching
   emitter.on("user::*", user_activity_handler)

   # Emit events with data
   await emitter.emit("user::login", user_data)

Task Management Workflows
~~~~~~~~~~~~~~~~~~~~~~~~~

Fabricatio's event-driven architecture excels at managing complex task workflows through its sophisticated task lifecycle management system.

**Task Lifecycle Management**

Tasks in Fabricatio progress through well-defined states:

- **Pending**: Task has been created but not yet started
- **Running**: Task is currently being processed
- **Finished**: Task completed successfully
- **Failed**: Task encountered an error during processing
- **Cancelled**: Task was cancelled before completion

Each state transition triggers corresponding events that can be handled by registered workflows:

.. code-block:: python

   # Task state transitions emit events
   task = Task(name="process_data")
   
   # Emits "work::process_data::Pending"
   task.publish("work")
   
   # Emits "work::process_data::Running" 
   await task.start()
   
   # Emits "work::process_data::Finished"
   await task.finish(result)

**Event-Based Workflow Registration**

Roles in Fabricatio register workflows to handle specific events, creating a flexible routing system:

.. code-block:: python

   role = Role()
   role.register_workflow(
       Event.quick_instantiate("process"),  # Matches "process::*::pending"
       WorkFlow(name="data_processor", steps=(Validate, Process, Store))
   )
   role.dispatch()  # Register workflows with the event emitter

Benefits of Event-Driven Design
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Fabricatio's event-driven architecture provides several key advantages:

**Scalability**
  - Decoupled components can be scaled independently
  - Event-based communication supports distributed processing
  - Concurrent event handling maximizes resource utilization

**Flexibility**
  - New functionality can be added through event handlers without modifying existing code
  - Wildcard event matching enables generic handlers for related events
  - Dynamic workflow registration allows runtime configuration

**Maintainability**
  - Loose coupling reduces dependencies between system components
  - Clear event boundaries make code easier to understand and debug
  - Standardized event patterns promote consistency across applications

**Extensibility**
  - Event handlers can be added or removed without system downtime
  - Plugin architecture supports modular feature development
  - Event inheritance enables specialized handling of generic events

LLM Integration & Templating
----------------------------

Fabricatio provides seamless integration with Large Language Models through its sophisticated templating system and unified LLM interface.

Handlebars Templating
~~~~~~~~~~~~~~~~~~~~~

Fabricatio leverages Handlebars as its primary templating engine, providing a powerful and familiar way to generate dynamic content for LLM interactions. The ``TemplateManager`` wraps the high-performance handlebars-rust engine for efficient template rendering.

**Template Features**

The templating system supports:

- **Logic-less Templates**: Clean separation between presentation and logic
- **Helper Functions**: Extensible template functionality through custom helpers
- **Partials**: Reusable template components for consistent formatting
- **Context-aware Rendering**: Templates can access complex data structures

.. code-block:: handlebars

   {{!-- Example template for task briefing --}}
   Task: {{name}}
   Goals: 
   {{#each goals}}
   - {{this}}
   {{/each}}
   
   Description: {{description}}
   
   Dependencies:
   {{#each dependencies}}
   - {{this}}
   {{/each}}

**Template Management**

Fabricatio's template system provides flexible template discovery and management:

.. code-block:: python

   from fabricatio_core.rust import TEMPLATE_MANAGER, CONFIG
   
   # Templates are automatically discovered from configured directories
   templates_dir = CONFIG.template_manager.template_stores[0]
   
   # Render templates with context data
   result = TEMPLATE_MANAGER.render_template(
       "task_briefing", 
       task.model_dump()
   )

Dynamic Content Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~

Fabricatio's LLM integration enables sophisticated dynamic content generation through its action-based workflow system.

**LLM Configuration**

The system provides comprehensive LLM configuration through multiple sources with clear priority ordering:

.. code-block:: python

   # Configuration priority: Call Arguments > .env > Environment Variables > 
   # fabricatio.toml > pyproject.toml > <ROAMING>/fabricatio/fabricatio.toml > Defaults
   
   from fabricatio_core.rust import CONFIG
   
   llm_config = CONFIG.llm
   print(f"Using model: {llm_config.model}")
   print(f"Temperature: {llm_config.temperature}")

**Action-based LLM Interaction**

Actions in Fabricatio can seamlessly interact with LLMs through built-in methods:

.. code-block:: python

   class ContentGenerator(Action):
       """Action that generates content using LLM."""
       
       output_key: str = "generated_content"
       
       async def _execute(self, task_input: Task, **context) -> str:
           # Generate content using LLM with templated prompt
           prompt = TEMPLATE_MANAGER.render_template(
               "content_generation_prompt",
               {"task": task_input.model_dump(), "context": context}
           )
           
           # Interact with LLM through unified interface
           response = await self.aask(prompt)
           return response

**Template-driven Prompt Engineering**

Fabricatio's templating system enables sophisticated prompt engineering:

.. code-block:: handlebars

   {{!-- Complex prompt template with conditional logic --}}
   You are a {{role}}. Your task is to {{task.description}}.
   
   {{#if task.goals}}
   Objectives:
   {{#each task.goals}}
   - {{this}}
   {{/each}}
   {{/if}}
   
   {{#if context.examples}}
   Examples:
   {{#each context.examples}}
   {{this}}
   {{/each}}
   {{/if}}
   
   Please provide your response in {{output_format}}.

Async & Extensible
------------------

Fabricatio is built from the ground up with asynchronous execution and extensibility as core principles, enabling high-performance LLM applications that can be easily customized and extended.

Asynchronous Execution Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Fabricatio leverages Python's async/await syntax throughout its architecture to provide non-blocking, concurrent execution of tasks and workflows.

**Concurrent Task Processing**

The framework supports concurrent execution of multiple tasks:

.. code-block:: python

   import asyncio
   from fabricatio import Task
   
   async def process_multiple_tasks():
       # Create multiple tasks
       tasks = [
           Task(name=f"task_{i}", description=f"Process item {i}")
           for i in range(10)
       ]
       
       # Delegate all tasks concurrently
       results = await asyncio.gather(*[
           task.delegate("processing") for task in tasks
       ])
       
       return results

**Non-blocking Action Execution**

All actions in Fabricatio are designed to be non-blocking:

.. code-block:: python

   class AsyncAction(Action):
       """Example of an async action."""
       
       async def _execute(self, **context):
           # Non-blocking I/O operations
           data = await fetch_external_data()
           
           # Concurrent processing
           processed_data = await process_data_concurrently(data)
           
           return processed_data

**Event Loop Integration**

Fabricatio integrates seamlessly with Python's asyncio event loop:

.. code-block:: python

   # Blocking execution for simple cases
   result = Task(name="simple").delegate_blocking("workflow")
   
   # Async execution for complex scenarios
   async def main():
       result = await Task(name="async").delegate("workflow")
       return result
   
   asyncio.run(main())

Extension Mechanisms
~~~~~~~~~~~~~~~~~~~~

Fabricatio provides multiple extension points that allow developers to customize and extend the framework's functionality.

**Custom Actions**

Developers can create custom actions by subclassing the ``Action`` base class:

.. code-block:: python

   from fabricatio import Action
   
   class CustomProcessing(Action):
       """Custom action for specialized processing."""
       
       # Override context variables with values from context
       ctx_override: bool = True
       
       # Store output in context under this key
       output_key: str = "processed_data"
       
       # Custom attributes that can be overridden from context
       threshold: float = 0.5
       max_retries: int = 3
       
       async def _execute(self, task_input: Task, **context) -> Any:
           # Custom implementation
           result = await self.process_with_custom_logic(
               task_input, 
               threshold=self.threshold,
               max_retries=self.max_retries
           )
           return result

**Custom Workflows**

Workflows can be customized to implement specific processing patterns:

.. code-block:: python

   from fabricatio import WorkFlow
   
   class CustomWorkflow(WorkFlow):
       """Custom workflow with specialized behavior."""
       
       # Custom initialization context
       extra_init_context = {
           "custom_helper": my_helper_function,
           "default_config": {"timeout": 30}
       }
       
       async def serve(self, task: Task) -> None:
           # Custom workflow logic before calling super().serve(task)
           await self.pre_process(task)
           await super().serve(task)
           await self.post_process(task)

**Plugin Architecture**

Fabricatio supports a plugin architecture through its modular design:

.. code-block:: python

   # Create specialized roles with custom capabilities
   class SpecializedRole(Role):
       """Role with domain-specific capabilities."""
       
       def __init__(self):
           super().__init__(
               name="specialized_processor",
               description="Handles domain-specific processing tasks"
           )
           
           # Register domain-specific workflows
           self.register_workflow(
               Event.quick_instantiate("domain_process"),
               DomainWorkflow(steps=(Validate, Process, DomainSpecificAction))
           )

Workflow Customization
~~~~~~~~~~~~~~~~~~~~~~

Fabricatio provides extensive customization options for workflow behavior and task processing.

**Context Management**

Workflows provide sophisticated context management for sharing data between actions:

.. code-block:: python

   # Initialize workflow with custom context
   workflow = WorkFlow(
       name="custom_processor",
       steps=(Action1, Action2, Action3),
       extra_init_context={
           "api_client": get_api_client(),
           "database_connection": get_db_connection(),
           "custom_config": load_config()
       }
   )
   
   # Update context dynamically
   workflow.update_init_context(new_setting="value")

**Error Handling and Recovery**

Custom workflows can implement sophisticated error handling:

.. code-block:: python

   class ResilientWorkflow(WorkFlow):
       """Workflow with enhanced error handling."""
       
       async def serve(self, task: Task) -> None:
           try:
               await super().serve(task)
           except SpecificException as e:
               await self.handle_specific_error(task, e)
           except Exception as e:
               await self.handle_generic_error(task, e)
               raise

**Dynamic Workflow Composition**

Workflows can be composed dynamically at runtime:

.. code-block:: python

   def create_workflow_for_task(task_type: str) -> WorkFlow:
       """Factory function for creating type-specific workflows."""
       
       if task_type == "analysis":
           steps = (ValidateInput, AnalyzeData, GenerateReport)
       elif task_type == "generation":
           steps = (PrepareContext, GenerateContent, ReviewOutput)
       else:
           steps = (DefaultValidate, DefaultProcess)
           
       return WorkFlow(
           name=f"{task_type}_processor",
           steps=steps
       )