Workflow Patterns
=================

This guide documents common workflow patterns and best practices for building Fabricatio applications.

Event Flow Overview
-------------------

Fabricatio's event-driven architecture follows a consistent flow pattern:

.. mermaid::

   flowchart TD
      TC["Task Created"] --> TD2["Task.delegate"]
      TD2 --> EE["Event Emitter"]
      EE --> WR["WorkFlow Registry\n(Role.skills)"]
      WR --> ME["Match Event"]
      ME --> WS["WorkFlow.serve\n(executes)"]
      WS --> A1["Action 1\n._execute()"]
      WS --> A2["Action 2\n._execute()"]
      WS --> AN["Action N\n._execute()"]
      A1 --> TO["Task.output\n(result)"]
      A2 --> TO
      AN --> TO

Simple Action Workflow
----------------------

The most basic pattern - a single action responding to an event.

.. mermaid::

   flowchart TD
      EV["Event: greet"] --> WF["WorkFlow('greet')"]
      WF --> HA["HelloAction\n._execute() \u2192 'Hello, World!'"]
      HA --> R["Result"]

.. code-block:: python

    from fabricatio import Action, Event, Role, Task, WorkFlow

    class HelloAction(Action):
        async def _execute(self, **kwargs) -> str:
            return "Hello, World!"

    role = Role(
        name="greeter",
        skills={
            Event.quick_instantiate("greet").collapse(): WorkFlow(
                name="greet",
                steps=(HelloAction,)
            )
        }
    )

    task = Task(name="say_hello", briefing="Greet the user")
    result = await task.delegate_blocking("greet")

Multi-Step Pipeline
-------------------

Chain multiple actions where each step's output feeds into the next.

.. mermaid::

   flowchart TD
      WR["workflow_results = {}"] --> FA["Fetch Action\n._execute()\n\u2192 'Fetched: X'"]
      FA --> PA["Process Action\n._execute()\n\u2192 'Processed: Fetched: X'"]
      PA --> FOA["Format Action\n._execute()\n\u2192 'Formatted: Processed: Fetched: X'"]
      FOA --> R["Result"]

.. code-block:: python

    class Fetch(Action):
        async def _execute(self, task_input: Task[str], **_) -> str:
            return f"Fetched: {task_input.briefing}"

    class Process(Action):
        async def _execute(self, task_input: Task[str], **kwargs) -> str:
            # Access previous step result
            prev = kwargs.get("workflow_results", {})
            fetched = prev.get("Fetch", "")
            return f"Processed: {fetched}"

    class Format(Action):
        async def _execute(self, task_input: Task[str], **kwargs) -> str:
            prev = kwargs.get("workflow_results", {})
            processed = prev.get("Process", "")
            return f"Formatted: {processed}"

    role = Role(
        name="pipeline",
        skills={
            Event.quick_instantiate("run").collapse(): WorkFlow(
                name="run",
                steps=(Fetch, Process, Format)
            )
        }
    )

Parallel Actions
----------------

Execute multiple independent actions concurrently.

.. mermaid::

   flowchart TD
      WR["workflow_results = {}"] --> FU["FetchUser Action\n(async)"]
      WR --> FH["FetchHistory Action\n(async)"]
      WR --> OT["Other Action\n(async)"]
      FU --> R1["workflow_results\n'FetchUser'"]
      FH --> R2["workflow_results\n'FetchHistory'"]
      OT --> R3["workflow_results\n'Other'"]
      R1 --> AG["Aggregate Action\nCombines all"]
      R2 --> AG
      R3 --> AG

.. code-block:: python

    class FetchUser(Action):
        async def _execute(self, task_input: Task, **_) -> dict:
            # Fetch user data
            return {"user": await self.aask("Get user info")}

    class FetchHistory(Action):
        async def _execute(self, task_input: Task, **_) -> dict:
            # Fetch history
            return {"history": await self.aask("Get history")}

    class Aggregate(Action):
        async def _execute(self, task_input: Task, **kwargs) -> dict:
            prev = kwargs.get("workflow_results", {})
            # Aggregate independent results
            return {**prev.get("FetchUser", {}), **prev.get("FetchHistory", {})}

    # Note: Parallel execution within a workflow requires asyncio.gather
    # or a custom executor - see advanced patterns

    import asyncio

    async def execute_parallel(actions, task):
        # Manual parallel execution
        results = await asyncio.gather(*[
            action()._execute(task_input=task) for action in actions
        ])
        return results

Conditional Branching
---------------------

Use different workflows based on task characteristics.

.. mermaid::

   flowchart TD
      T["Task"] --> LR["LLM Router\n(aask_struct)"]
      LR -->|"simple"| SA["SimpleAction\n._execute()"]
      LR -->|"complex"| CA["ComplexAction\n._execute()"]
      SA --> R["Result"]
      CA --> R

.. code-block:: python

    class SimpleAction(Action):
        async def _execute(self, task_input: Task[str], **_) -> str:
            return f"Simple: {task_input.briefing}"

    class ComplexAction(Action):
        async def _execute(self, task_input: Task[str], **_) -> str:
            return f"Complex: {await self.aask(task_input.briefing)}"

    async def route_task(task: Task) -> str:
        # LLM-based routing decision
        decision = await role.aask(
            f"Should we use simple or complex processing for: {task.briefing}?",
        )
        if "complex" in decision.lower():
            return "complex"
        return "simple"

    # Usage
    route = await route_task(task)
    result = await task.delegate_blocking(route)

Task Proposal Pattern
---------------------

Let the LLM decompose a goal into multiple tasks.

.. mermaid::

   flowchart TD
      PR["Planner Role\npropose_task('Build REST API')\n\u2192 Task1, Task2, ..."] --> PT["Proposed Task List\nTask(endpoint 1)\nTask(endpoint 2)\nTask(tests)"]
      PT --> E1["Executor\nTask 1"]
      PT --> E2["Executor\nTask 2"]
      PT --> EN["Executor\nTask N"]
      E1 --> AR["All Results"]
      E2 --> AR
      EN --> AR

.. code-block:: python

    from fabricatio.capabilities import ProposeTask

    class Planner(Role, ProposeTask):
        pass

    class Executor(Role):
        async def execute_step(self, step_briefing: str):
            task = Task(name="step", briefing=step_briefing)
            return await task.delegate_blocking("execute")

    planner = Planner(name="planner")
    executor = Executor(name="executor")

    # Get proposed tasks from LLM
    proposed_tasks = await planner.propose_task(
        "Build a REST API for a todo app",
        mode="agentic",  # Detailed sub-tasks
    )

    # Execute each proposed task
    for task in proposed_tasks:
        result = await executor.execute_step(task.briefing)

Error Handling Pattern
----------------------

Graceful error handling with fallback actions.

.. mermaid::

   flowchart TD
      PA["PrimaryAction\n._execute()"] -->|Success| RR["Return Result\nto WorkFlow"]
      PA -->|Exception| LW["Log Warning\nlogger.warning\nRe-raise"]
      LW --> FA["FallbackAction\n._execute()"]
      FA --> FR["Return Fallback\nResult"]

.. code-block:: python

    class PrimaryAction(Action):
        async def _execute(self, task_input: Task, **_) -> str:
            try:
                return await self.aask(task_input.briefing)
            except Exception as e:
                logger.warning(f"Primary failed: {e}")
                raise  # Re-raise to trigger fallback

    class FallbackAction(Action):
        async def _execute(self, task_input: Task, **_) -> str:
            return "Default response due to failure"

    class RecoveryAction(Action):
        async def _execute(self, task_input: Task, **_) -> str:
            # Attempt recovery or use cached data
            return "Recovered response"

    role = Role(
        name="resilient",
        skills={
            Event.quick_instantiate("process").collapse(): WorkFlow(
                name="process",
                steps=(PrimaryAction,),
                fallback=FallbackAction,
            )
        }
    )

RAG Workflow Pattern
--------------------

Retrieval-augmented generation with document ingestion and query.

.. mermaid::

   flowchart TD
      subgraph Init["INIT KNOWLEDGE BASE"]
         IK["InitKBAction\n1. init_client()\n2. view()\n3. consume_string()"] --> MV["Milvus\nVector DB"]
      end
      subgraph Query["QUERY KNOWLEDGE BASE"]
         QK["QueryKBAction\n1. query (similarity search)\n2. aask_retrieved (RAG)"] --> LLM["LLM Response\n(grounded)"]
      end

.. code-block:: python

    from fabricatio import Action, Event, Role, Task, WorkFlow
    from fabricatio_milvus.capabilities.milvus import MilvusRAG

    class InitKnowledgeBase(Action, MilvusRAG):
        async def _execute(self, documents: list[str], **_) -> None:
            self.init_client()
            self.view("knowledge", create=True)
            await self.consume_string(documents)

    class QueryKnowledge(Action, MilvusRAG):
        async def _execute(self, task_input: Task[str], **_) -> str:
            return await self.aask_retrieved(
                task_input.briefing,
                task_input.briefing,
                extra_system_message="Answer based on the knowledge base.",
            )

    role = Role(
        name="knowledge_assistant",
        skills={
            Event.quick_instantiate("init_kb").collapse(): WorkFlow(
                name="init_kb",
                steps=(InitKnowledgeBase,)
            ),
            Event.quick_instantiate("query").collapse(): WorkFlow(
                name="query",
                steps=(QueryKnowledge,)
            ),
        }
    )

    # Initialize knowledge base
    init_task = Task(name="init", briefing=documents)
    await init_task.delegate_blocking("init_kb")

    # Query
    query_task = Task(name="query", briefing="What is X?")
    result = await query_task.delegate_blocking("query")

Structured Output Pattern
-------------------------

Use Pydantic models for reliable structured responses.

.. mermaid::

   flowchart TD
      IN["Prompt: Analyze this code"] --> LLM["LLM Response\nlanguage, complexity,\nissues, suggestions"]
      LLM --> PV["Pydantic Model Validation\nCodeAnalysis instance"]
      PV --> TR["Typed Result\n.language, .issues,\n.suggestions"]

.. code-block:: python

    from pydantic import BaseModel, Field
    from typing import Optional

    class CodeAnalysis(BaseModel):
        language: str = Field(description="Programming language detected")
        complexity: str = Field(description="Complexity rating: low/medium/high")
        issues: list[str] = Field(description="List of code issues found")
        suggestions: list[str] = Field(description="Improvement suggestions")

    class Analyzer(Role):
        async def analyze_code(self, code: str) -> CodeAnalysis:
            return await self.aask_structured(
                f"Analyze this code:\n{code}",
                response_format=CodeAnalysis,
            )

    analyzer = Analyzer(name="analyzer")
    result = await analyzer.analyze_code("def foo(): pass")
    
    # result is a fully typed CodeAnalysis instance
    print(f"Language: {result.language}")
    print(f"Issues: {result.issues}")

Review-Improvement Loop
-----------------------

Iterative refinement through review cycles.

.. mermaid::

   flowchart TD
      IC["Initial Content\nimprove_string(briefing)"] --> REV{"Review\nscore >= 8?"}
      REV -->|No| IMP["Improve with feedback"]
      IMP --> REV
      REV -->|Yes| FC["Final Content"]

.. code-block:: python

    from fabricatio.capabilities import Review, Improve

    class Writer(Role, Improve):
        pass

    class Reviewer(Role, Review):
        pass

    writer = Writer(name="writer")
    reviewer = Reviewer(name="reviewer")

    async def write_with_review(briefing: str, max_iterations: int = 3) -> str:
        content = await writer.improve_string(briefing, style="clear")
        
        for i in range(max_iterations):
            review_result = await reviewer.review_string(
                content,
                criteria="quality and clarity"
            )
            
            if review_result.score >= 8:
                break
                
            # Incorporate feedback
            feedback = "\n".join(review_result.suggestions)
            content = await writer.improve_string(
                f"Original:\n{content}\n\nFeedback:\n{feedback}",
                style="clear"
            )
        
        return content

Checkpoint Pattern
------------------

Save workflow state for recovery.

.. mermaid::

   flowchart TD
      WS["Workflow Start"] --> LC{"Load Checkpoint\n(if exists)"}
      LC -->|"has state\nstep_2_complete"| SKIP["Skip to Step 2\nReturn cached result"]
      LC -->|"no state"| S1["Execute Step 1\nSave checkpoint\nstep_1_complete"]
      S1 --> S2["Execute Step 2\nSave checkpoint\nstep_2_complete\nSave result"]
      S2 --> RET["Return result"]

.. code-block:: python

    from fabricatio.checkpoint import Checkpoint

    class LongRunningAction(Action):
        async def _execute(self, task_input: Task, **kwargs) -> str:
            checkpoint = Checkpoint.load("workflow_id")
            
            if checkpoint.has_state("step_2_complete"):
                # Resume from step 2
                return checkpoint.get("result")
            
            # Do step 1
            result1 = await self.do_step1()
            checkpoint.save("step_1_complete", True)
            
            # Do step 2
            result2 = await self.do_step2(result1)
            checkpoint.save("step_2_complete", True)
            checkpoint.save("result", result2)
            
            return result2

Team Collaboration Pattern
--------------------------

Multiple agents working together.

.. mermaid::

   flowchart TD
      subgraph Team
         R["Researcher"]
         W["Writer"]
         E["Editor"]
         RV["Reviewer"]
      end
      R --> RP["Research Phase"]
      RP --> WP["Write Phase"]
      W --> WP
      WP --> EP["Edit Phase"]
      E --> EP

.. code-block:: python

    from fabricatio_team import Team

    class Researcher(Role):
        pass

    class Writer(Role):
        pass

    class Editor(Role):
        pass

    async def collaborative_writing(topic: str) -> str:
        team = Team(name="writing_team")
        
        researcher = Researcher(name="researcher")
        writer = Writer(name="writer")
        editor = Editor(name="editor")
        
        # Add agents to team
        team.add_agent(researcher, role="research")
        team.add_agent(writer, role="writing")
        team.add_agent(editor, role="editing")
        
        # Research phase
        research = await team.delegate("research", f"Research: {topic}")
        
        # Writing phase (depends on research)
        draft = await team.delegate("writing", f"Write article about {topic}")
        
        # Editing phase
        final = await team.delegate("editing", f"Edit: {draft}")
        
        return final

EventEmitter Wildcard Pattern
-----------------------------

Using wildcards for flexible event routing.

.. mermaid::

   flowchart TD
      subgraph EE["EventEmitter (sep='::')"]
         H1["user::* \u2192 user_activity_handler"]
         H2["user::login \u2192 login_handler"]
         H3["user::logout \u2192 logout_handler"]
         H4["system::* \u2192 system_handler"]
      end
      subgraph E1["Emit: user::login"]
         direction LR
         LH["login_handler"]
         UAH["user_activity_handler"]
      end
      subgraph E2["Emit: system::alert"]
         SH["system_handler"]
      end

.. code-block:: python

    from fabricatio import EventEmitter

    # Create an event emitter with custom separator
    emitter = EventEmitter(sep="::")

    # Register handlers for exact events
    def login_handler(data):
        print(f"User logged in: {data}")

    def logout_handler(data):
        print(f"User logged out: {data}")

    def user_activity_handler(data):
        print(f"User activity: {data}")

    def system_handler(data):
        print(f"System event: {data}")

    # Exact event matching
    emitter.on("user::login", login_handler)
    emitter.on("user::logout", logout_handler)

    # Wildcard matching - catches all user::* events
    emitter.on("user::*", user_activity_handler)

    # Wildcard matching for system events
    emitter.on("system::*", system_handler)

    # Emit events
    emitter.emit("user::login", {"user_id": 123})
    # Both login_handler and user_activity_handler are called

    emitter.emit("user::update", {"user_id": 123})
    # Only user_activity_handler is called

    emitter.emit("system::restart", {"reason": "maintenance"})
    # system_handler is called

Task Lifecycle Pattern
----------------------

Task states and transitions.

.. mermaid::

   flowchart TD
      TC["Task Created\n(pending)"] -->|"task.start()"| TR["Task Running\n(active)"]
      TR -->|"task.fail(e)"| TF["Task Failed\n(error)"]
      TR -->|"task.finish()"| TFI["Task Finished\n(success)"]
      TR -->|"task.cancel()"| TCA["Task Cancelled\n(aborted)"]

      subgraph Events["Event Emission"]
         direction LR
         E1["publish('work') \u2192 Pending"]
         E2["start() \u2192 Running"]
         E3["finish(r) \u2192 Finished"]
         E4["fail(e) \u2192 Failed"]
         E5["cancel() \u2192 Cancelled"]
      end

.. code-block:: python

    from fabricatio import Task

    # Task state transitions emit events
    task = Task(name="process_data")
    
    # Emits "work::process_data::Pending"
    task.publish("work")
    
    # Emits "work::process_data::Running" 
    await task.start()
    
    # Emits "work::process_data::Finished"
    await task.finish(result)

    # Or handle failure
    await task.fail(error)

Role and Skill Registration Pattern
-----------------------------------

How roles register and handle skills.

.. mermaid::

   flowchart TD
      subgraph Role["Role (name='assistant')"]
         direction LR
         S1["greet \u2192 WorkFlow(Hello)"]
         S2["analyze \u2192 WorkFlow(Parse, Analyze, Report)"]
         S3["help \u2192 WorkFlow(Help)"]
      end
      Role -->|"role.dispatch()"| ER["EventEmitter\nRegistration"]
      ER --> R1["greet registered"]
      ER --> R2["analyze registered"]
      ER --> R3["help registered"]

.. code-block:: python

    from fabricatio import Role, Event, WorkFlow

    role = Role(
        name="assistant",
        description="A helpful assistant",
        skills={
            Event.quick_instantiate("greet").collapse(): WorkFlow(
                name="greet",
                steps=(HelloAction,)
            ),
            Event.quick_instantiate("analyze").collapse(): WorkFlow(
                name="analyze",
                steps=(ParseAction, AnalyzeAction, ReportAction)
            ),
            Event.quick_instantiate("help").collapse(): WorkFlow(
                name="help",
                steps=(HelpAction,)
            )
        }
    )

    # Register all skills with the event emitter
    role.dispatch()

    # Now tasks can delegate to registered events
    task = Task(name="demo")
    result = await task.delegate_blocking("greet")

Capability Mixin Pattern
------------------------

Combining capabilities with actions.

.. mermaid::

   flowchart TD
      A["Action\n(base class)"] --> ULLM["UseLLM"]
      A --> RV["Review"]
      A --> EX["Extract"]
      A --> PT["ProposeTask"]
      A --> IMP["Improve"]
      ULLM --> CA["Combined Action\nclass MyAction(\n  Action, UseLLM, Review\n)"]
      RV --> CA

.. code-block:: python

    from fabricatio import Action, Task
    from fabricatio.capabilities import UseLLM, Review

    class AnalyzeAndReview(Action, UseLLM, Review):
        """Action that analyzes content and can review it."""
        
        output_key: str = "analysis"
        
        async def _execute(self, task_input: Task[str], **_) -> str:
            # Use LLM capability to analyze
            analysis = await self.aask(f"Analyze: {task_input.briefing}")
            
            # Use Review capability to score
            review_result = await self.review_string(
                analysis,
                criteria="accuracy and clarity"
            )
            
            return f"{analysis}\n\nReview score: {review_result.score}"

Role Inheritance Pattern
------------------------

Creating specialized roles through inheritance.

.. mermaid::

   flowchart TD
      R1["Role\n(base class)"] --> SR["SpecializedRole\nCustom name, skills,\ncapabilities"]

      subgraph Chain["Example Inheritance Chain"]
         R2["Role"] --> ULLM2["UseLLM (mixin)"]
         ULLM2 --> CR1["Role (combined)"]
         CR1 --> PT2["ProposeTask (mixin)"]
         PT2 --> CR2["Role (combined)"]
         CR2 --> PL["Planner Role (concrete)\ncan propose_task, can aask"]
      end

.. code-block:: python

    from fabricatio import Role, Event, WorkFlow
    from fabricatio.capabilities import UseLLM, ProposeTask

    # Simple inherited role with LLM capability
    class LLMAssistant(Role, UseLLM):
        def __init__(self):
            super().__init__(
                name="llm_assistant",
                description="Assistant with LLM capabilities"
            )

    # Complex inherited role with multiple capabilities
    class Planner(Role, UseLLM, ProposeTask):
        def __init__(self):
            super().__init__(
                name="planner",
                description="Task planning assistant"
            )
            
            # Add specialized planning workflow
            self.register_workflow(
                Event.quick_instantiate("plan").collapse(),
                WorkFlow(name="plan", steps=(PlanningAction,))
            )

    # Usage
    planner = Planner()
    tasks = await planner.propose_task("Build a web app")

Best Practices Summary
----------------------

1. **Keep Actions Single-Purpose**
   Small, focused actions are easier to test and reuse.

2. **Use Structured Output**
   ``aask_structured()`` provides reliable, typed responses.

3. **Handle Errors Explicitly**
   Use try/except and fallback workflows.

4. **Log Appropriately**
   Use ``logger`` for debugging and monitoring.

5. **Profile in Development**
   Use ``viztracer`` to identify bottlenecks.

6. **Configure Timeouts**
   Set reasonable timeouts for LLM calls.

7. **Test Workflows Independently**
   Unit test actions, integration test workflows.

8. **Use EventEmitter Wildcards Wisely**
   Wildcard patterns like ``user::*`` enable flexible routing but avoid
   overly broad matches that could cause unexpected behavior.

9. **Leverage Capability Mixins**
   Combine capabilities to create powerful actions without code duplication.

10. **Design for Concurrency**
    Use ``asyncio.gather()`` for parallel action execution when actions
    are independent.
