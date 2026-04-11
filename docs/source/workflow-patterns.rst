Workflow Patterns
================

This guide documents common workflow patterns and best practices for building Fabricatio applications.

Event Flow Overview
------------------

Fabricatio's event-driven architecture follows a consistent flow pattern:

.. code-block:: text

    ┌─────────────────────────────────────────────────────────────────────┐
    │                         EVENT FLOW                                   │
    └─────────────────────────────────────────────────────────────────────┘
    
    Task Created
         │
         ▼
    ┌─────────────┐      ┌──────────────┐      ┌─────────────────────────┐
    │   Task      │─────▶│   Event      │─────▶│   WorkFlow Registry      │
    │  .delegate  │      │  Emitter     │      │   (Role.skills)          │
    └─────────────┘      └──────────────┘      └─────────────────────────┘
                                                          │
                                                          ▼
                                                   ┌─────────────┐
                                                   │   Match     │
                                                   │   Event     │
                                                   └─────────────┘
                                                          │
                                                          ▼
                                                   ┌─────────────────┐
                                                   │  WorkFlow.serve │
                                                   │   (executes)    │
                                                   └─────────────────┘
                                                          │
                         ┌────────────────────────────────┴────────────────────────────────┐
                         ▼                                ▼                                ▼
                  ┌──────────────┐                  ┌──────────────┐                  ┌──────────────┐
                  │   Action 1   │                  │   Action 2   │                  │   Action N   │
                  │  ._execute() │                  │  ._execute() │                  │  ._execute() │
                  └──────────────┘                  └──────────────┘                  └──────────────┘
                         │                                │                                │
                         └────────────────────────────────┴────────────────────────────────┘
                                              │
                                              ▼
                                      ┌──────────────┐
                                      │ Task.output  │
                                      │  (result)   │
                                      └──────────────┘

Simple Action Workflow
---------------------

The most basic pattern - a single action responding to an event.

.. code-block:: text

    ┌─────────────────────────────────────────────────────────────────┐
    │                    SIMPLE ACTION WORKFLOW                        │
    └─────────────────────────────────────────────────────────────────┘
    
    Event: "greet"
         │
         ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      WorkFlow("greet")                          │
    │  ┌───────────────────────────────────────────────────────────┐  │
    │  │                      HelloAction                          │  │
    │  │                      _execute() ──▶ "Hello, World!"       │  │
    │  └───────────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────┘
         │
         ▼
      Result

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
------------------

Chain multiple actions where each step's output feeds into the next.

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                       MULTI-STEP PIPELINE                              │
    └────────────────────────────────────────────────────────────────────────┘
    
    workflow_results = {}
    
         │
         ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                        Fetch Action                                │
    │  _execute(task_input) ──▶ workflow_results["Fetch"] = "Fetched: X" │
    └────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                        Process Action                              │
    │  _execute(task_input, workflow_results)                            │
    │       │                         │
    │       │ workflow_results["Fetch"]                                 │
    │       ▼                                                         │
    │  workflow_results["Process"] = "Processed: Fetched: X"           │
    └────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                        Format Action                               │
    │  _execute(task_input, workflow_results)                           │
    │       │                         │
    │       │ workflow_results["Process"]                               │
    │       ▼                                                         │
    │  workflow_results["Format"] = "Formatted: Processed: Fetched: X"  │
    └────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                               Result

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

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                       PARALLEL ACTIONS                                 │
    └────────────────────────────────────────────────────────────────────────┘
    
    workflow_results = {}
    
         │
         ▼
    ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
    │   FetchUser Action │  │ FetchHistory Action│  │  Other Action       │
    │   (async)          │  │   (async)          │  │   (async)          │
    └────────┬───────────┘  └────────┬───────────┘  └────────┬───────────┘
             │                        │                        │
             ▼                        ▼                        ▼
    workflow_results      workflow_results              workflow_results
    ["FetchUser"] = {}    ["FetchHistory"] = {}         ["Other"] = {}
             │                        │                        │
             └────────────────────────┴────────────────────────┘
                                  │
                                  ▼
                         ┌────────────────────┐
                         │  Aggregate Action  │
                         │  Combines all      │
                         └────────────────────┘

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
--------------------

Use different workflows based on task characteristics.

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                    CONDITIONAL BRANCHING                               │
    └────────────────────────────────────────────────────────────────────────┘
    
                          Task
                            │
                            ▼
                    ┌───────────────┐
                    │  LLM Router   │
                    │ (aask_struct) │
                    └───────┬───────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
         "simple"                     "complex"
              │                           │
              ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐
    │ SimpleAction    │         │ ComplexAction   │
    │ _execute()      │         │ _execute()      │
    └─────────────────┘         └─────────────────┘
              │                           │
              └─────────────┬───────────────┘
                            │
                            ▼
                         Result

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

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                       TASK PROPOSAL PATTERN                             │
    └────────────────────────────────────────────────────────────────────────┘
    
         ┌─────────────────────────────────────────────────────────────────┐
         │                         Planner Role                            │
         │  ┌───────────────────────────────────────────────────────────┐  │
         │  │  Role + ProposeTask Capability                           │  │
         │  │  propose_task("Build REST API") ──▶ [Task1, Task2, ...]  │  │
         │  └───────────────────────────────────────────────────────────┘  │
         └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │  Proposed Task List   │
                        │  [Task("endpoint 1"), │
                        │   Task("endpoint 2"), │
                        │   Task("tests"), ...] │
                        └───────────────────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  ▼                 ▼                 ▼
         ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
         │  Executor    │   │  Executor    │   │  Executor    │
         │  Task 1     │   │  Task 2     │   │  Task N     │
         └──────────────┘   └──────────────┘   └──────────────┘
                  │                 │                 │
                  └─────────────────┴─────────────────┘
                                    │
                                    ▼
                              All Results

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
---------------------

Graceful error handling with fallback actions.

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                      ERROR HANDLING PATTERN                             │
    └────────────────────────────────────────────────────────────────────────┘
    
                    ┌──────────────────────────────────────┐
                    │           PrimaryAction               │
                    │           _execute()                 │
                    └──────────────────┬───────────────────┘
                                         │
                          ┌──────────────┴──────────────┐
                          │                             │
                     Success                          Exception
                          │                             │
                          ▼                             ▼
              ┌─────────────────────┐       ┌──────────────────────────────────┐
              │  Return Result     │       │  Log Warning (logger.warning)   │
              │  to WorkFlow       │       │  Re-raise to trigger fallback   │
              └─────────────────────┘       └──────────────────┬───────────────┘
                                                             │
                                                             ▼
                                                  ┌─────────────────────┐
                                                  │   FallbackAction    │
                                                  │   _execute()        │
                                                  └─────────────────────┘
                                                             │
                                                             ▼
                                                  ┌─────────────────────┐
                                                  │  Return Fallback     │
                                                  │  Result             │
                                                  └─────────────────────┘

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
-------------------

Retrieval-augmented generation with document ingestion and query.

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                         RAG WORKFLOW PATTERN                             │
    └────────────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────┐    ┌─────────────────────────────────┐
    │         INIT KNOWLEDGE BASE      │    │         QUERY KNOWLEDGE BASE     │
    └─────────────────────────────────┘    └─────────────────────────────────┘
    
         │                                        │
         ▼                                        ▼
    ┌─────────────┐                         ┌─────────────┐
    │InitKBAction │                         │QueryKBAction│
    │             │                         │             │
    │ 1. init_    │                         │ 1. query    │
    │    client() │                         │    (similarity│
    │ 2. view()   │                         │    search)   │
    │ 3. consume_ │                         │             │
    │    string() │                         │ 2. aask_    │
    └─────────────┘                         │    retrieved│
         │                                  │    (RAG)    │
         ▼                                  └─────────────┘
    ┌─────────────┐                              │
    │ Milvus      │                              ▼
    │ Vector DB   │                         ┌─────────────┐
    │             │                         │ LLM Response│
    └─────────────┘                         │ (grounded)  │
                                           └─────────────┘

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

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                      STRUCTURED OUTPUT PATTERN                         │
    └────────────────────────────────────────────────────────────────────────┘
    
         │
         ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                     aask_structured()                               │
    │                                                                      │
    │  Prompt: "Analyze this code:\n<code>"                                │
    │                   │                                                  │
    │                   ▼                                                  │
    │  ┌──────────────────────────────────────────────────────────────┐   │
    │  │                    LLM Response                               │   │
    │  │  {                                                             │   │
    │  │    "language": "python",                                       │   │
    │  │    "complexity": "medium",                                    │   │
    │  │    "issues": [...],                                           │   │
    │  │    "suggestions": [...]                                       │   │
    │  │  }                                                             │   │
    │  └──────────────────────────────────────────────────────────────┘   │
    │                              │                                        │
    │                              ▼                                        │
    │  ┌──────────────────────────────────────────────────────────────┐   │
    │  │              Pydantic Model Validation                       │   │
    │  │                  CodeAnalysis instance                        │   │
    │  └──────────────────────────────────────────────────────────────┘   │
    └────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │ Typed result with  │
                    │ .language, .issues, │
                    │ .suggestions        │
                    └─────────────────────┘

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
----------------------

Iterative refinement through review cycles.

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                     REVIEW-IMPROVEMENT LOOP                             │
    └────────────────────────────────────────────────────────────────────────┘
    
         │
         ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                      Initial Content                                │
    │                   improve_string(briefing)                          │
    └────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
              ┌─────▼─────┐                   ┌─────▼─────┐
              │ Iteration 1│                   │ Iteration 2│
              │            │                   │            │
              │ Review     │                   │ Review     │
              │ score: 6   │                   │ score: 7  │
              └─────┬──────┘                   └─────┬──────┘
                    │                               │
              score < 8                      score < 8
                    │                               │
                    ▼                               │
              ┌─────────────┐                       │
              │ Improve     │                       │
              │ with        │                       │
              │ feedback    │                       │
              └─────────────┘                       │
                    │                               │
                    └───────────────┴───────────────┘
                                            │
                                      score >= 8
                                            │
                                            ▼
                                    ┌─────────────┐
                                    │ Final       │
                                    │ Content     │
                                    └─────────────┘

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
-----------------

Save workflow state for recovery.

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                        CHECKPOINT PATTERN                               │
    └────────────────────────────────────────────────────────────────────────┘
    
                    Workflow Start
                          │
                          ▼
                    ┌───────────────┐
                    │ Load Checkpoint│
                    │ (if exists)   │
                    └───────┬───────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
         has state                  no state
         "step_2_complete"               │
              │                           │
              ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐
    │ Skip to Step 2  │         │ Execute Step 1  │
    │ Return cached   │         │ Save checkpoint │
    │ result          │         │ "step_1_complete"│
    └─────────────────┘         └────────┬────────┘
                                          │
                                          ▼
                                 ┌─────────────────┐
                                 │ Execute Step 2  │
                                 │ Save checkpoint │
                                 │ "step_2_complete"│
                                 │ Save result     │
                                 └─────────────────┘
                                          │
                                          ▼
                                    ┌───────────┐
                                    │ Return    │
                                    │ result    │
                                    └───────────┘

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

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                      TEAM COLLABORATION PATTERN                         │
    └────────────────────────────────────────────────────────────────────────┘
    
         ┌─────────────────────────────────────────────────────────────────┐
         │                            Team                                  │
         │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
         │  │Researcher│  │  Writer  │  │  Editor  │  │ Reviewer │        │
         │  │  Role    │  │   Role   │  │   Role   │  │   Role   │        │
         │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
         └───────┼─────────────┼─────────────┼─────────────┼──────────────┘
                 │             │             │             │
                 ▼             │             │             │
         ┌─────────────┐      │             │             │
         │   Research  │      │             │             │
         │   Phase      │      │             │             │
         └──────┬──────┘      │             │             │
                │             │             │             │
                └─────────────┼─────────────┼─────────────┘
                              │             │
                              ▼             │
                      ┌─────────────┐      │
                      │    Write    │      │
                      │   Phase     │      │
                      └──────┬──────┘      │
                             │             │
                             └─────────────┤
                                           │
                                           ▼
                                   ┌─────────────┐
                                   │    Edit     │
                                   │   Phase     │
                                   └─────────────┘

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

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                      EVENTEMITTER WILDCARD PATTERN                      │
    └────────────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │                         EventEmitter                                 │
    │                                                                      │
    │  emitter = EventEmitter(sep="::")                                    │
    │                                                                      │
    │  Registered Handlers:                                                │
    │  ┌──────────────────────────────────────────────────────────────┐    │
    │  │ "user::*"        ──▶ user_activity_handler(data)            │    │
    │  │ "user::login"   ──▶ login_handler(data)                     │    │
    │  │ "user::logout"  ──▶ logout_handler(data)                     │    │
    │  │ "system::*"     ──▶ system_handler(data)                     │    │
    │  └──────────────────────────────────────────────────────────────┘    │
    └─────────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │                        Event Emission                                │
    │                                                                      │
    │  emitter.emit("user::login", user_data)                             │
    │                              │                                       │
    │              ┌───────────────┼───────────────┐                      │
    │              ▼               ▼               ▼                      │
    │       ┌───────────┐   ┌───────────┐   ┌───────────┐                │
    │       │ login_    │   │ user_     │   │ (no match)│                │
    │       │ handler   │   │ activity_ │   │           │                │
    │       │           │   │ handler   │   │           │                │
    │       └───────────┘   └───────────┘   └───────────┘                │
    │                                                                      │
    │  emitter.emit("system::alert", alert_data)                          │
    │                              │                                       │
    │                              ▼                                       │
    │                       ┌───────────┐                                 │
    │                       │ system_   │                                 │
    │                       │ handler   │                                 │
    │                       └───────────┘                                 │
    └─────────────────────────────────────────────────────────────────────┘

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
---------------------

Task states and transitions.

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                         TASK LIFECYCLE                                 │
    └────────────────────────────────────────────────────────────────────────┘
    
                              ┌─────────────────┐
                              │     Task        │
                              │     Created     │
                              │   (pending)     │
                              └────────┬────────┘
                                       │
                                       │ task.start()
                                       ▼
                              ┌─────────────────┐
                              │     Task        │
                              │     Running     │
                              │   (active)     │
                              └────────┬────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    │ task.fail(e)     │ task.finish()    │ task.cancel()
                    ▼                  ▼                  ▼
           ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
           │     Task        │ │     Task        │ │     Task        │
           │     Failed      │ │    Finished     │ │   Cancelled     │
           │   (error)       │ │   (success)     │ │   (aborted)     │
           └─────────────────┘ └─────────────────┘ └─────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │                        Event Emission                               │
    │                                                                      │
    │  task.publish("work")     ──▶ Emits "work::{task_name}::Pending"   │
    │  await task.start()       ──▶ Emits "work::{task_name}::Running"   │
    │  await task.finish(r)    ──▶ Emits "work::{task_name}::Finished"  │
    │  await task.fail(e)      ──▶ Emits "work::{task_name}::Failed"     │
    │  await task.cancel()     ──▶ Emits "work::{task_name}::Cancelled" │
    └─────────────────────────────────────────────────────────────────────┘

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

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                    ROLE & SKILL REGISTRATION PATTERN                    │
    └────────────────────────────────────────────────────────────────────────┘
    
         ┌───────────────────────────────────────────────────────────────┐
         │                           Role                                 │
         │                                                                │
         │  name: "assistant"                                            │
         │  description: "A helpful assistant"                          │
         │                                                                │
         │  ┌─────────────────────────────────────────────────────────┐  │
         │  │              Skill Registry (dict)                       │  │
         │  │                                                          │  │
         │  │  "greet"  ──▶ WorkFlow(name="greet", steps=(Hello,))   │  │
         │  │  "analyze" ──▶ WorkFlow(name="analyze", steps=(Parse,  │  │
         │  │                                        Analyze, Report))│  │
         │  │  "help"    ──▶ WorkFlow(name="help", steps=(Help,))     │  │
         │  └─────────────────────────────────────────────────────────┘  │
         └───────────────────────────────────────────────────────────────┘
                                      │
                                      │ role.dispatch()
                                      ▼
                              ┌─────────────────┐
                              │  EventEmitter   │
                              │  Registration   │
                              └─────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
            ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
            │ "greet"     │   │ "analyze"   │   │ "help"      │
            │ registered  │   │ registered  │   │ registered  │
            └─────────────┘   └─────────────┘   └─────────────┘

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

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                       CAPABILITY MIXIN PATTERN                         │
    └────────────────────────────────────────────────────────────────────────┘
    
         ┌─────────────────┐
         │     Action      │
         │   (base class)  │
         └────────┬────────┘
                  │ inherits
                  │
      ┌───────────┼───────────┬───────────────┬───────────────┐
      │           │           │               │               │
      ▼           ▼           ▼               ▼               ▼
    ┌──────┐  ┌────────┐  ┌─────────┐    ┌──────────┐   ┌──────────┐
    │UseLLM│  │Review  │  │Extract  │    │ProposeTask│  │Improve   │
    │      │  │        │  │         │    │          │   │          │
    └──────┘  └────────┘  └─────────┘    └──────────┘   └──────────┘
      │           │           │               │               │
      └───────────┴───────────┴───────────────┴───────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  Combined Action    │
                    │                      │
                    │  class MyAction(    │
                    │      Action,         │
                    │      UseLLM,         │
                    │      Review          │
                    │  ):                  │
                    │                      │
                    │  # Has aask()        │
                    │  # Has review_string()│
                    │  # Has _execute()    │
                    └─────────────────────┘

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

.. code-block:: text

    ┌────────────────────────────────────────────────────────────────────────┐
    │                      ROLE INHERITANCE PATTERN                           │
    └────────────────────────────────────────────────────────────────────────┘
    
              ┌─────────────────┐
              │     Role        │
              │   (base class)  │
              └────────┬────────┘
                       │ inherits
                       ▼
              ┌─────────────────┐
              │  SpecializedRole│
              │  - Custom name  │
              │  - Custom skills│
              │  - Extended     │
              │    capabilities │
              └─────────────────┘
    
    Example Inheritance Chain:
    
              ┌─────────────────┐
              │     Role        │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  UseLLM (mixin) │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │     Role        │ (combined)
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   ProposeTask   │
              │    (mixin)     │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │     Role        │ (combined)
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Planner Role   │ (concrete)
              │                  │
              │ can propose_task │
              │ can aask         │
              └─────────────────┘

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
---------------------

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
