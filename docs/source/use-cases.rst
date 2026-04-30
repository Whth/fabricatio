Use Cases & Examples
====================

This guide covers common use cases with detailed examples.

Basic Chat Agent
----------------

The simplest Fabricatio application - a role that responds to user input.

.. code-block:: python

    """Simple chat example."""

    import asyncio

    from fabricatio import Action, Event, Role, Task, WorkFlow, logger
    from fabricatio.capabilities import UseLLM
    from questionary import text


    class Talk(Action, UseLLM):
        """Action that says hello to the world."""

        output_key: str = "task_output"

        async def _execute(self, task_input: Task[str], **_) -> int:
            counter = 0
            try:
                while True:
                    # Prompt user for input - questionary provides async text input
                    user_say = await text("User: ").ask_async()
                    # Use aask (async ask) to get LLM response with task briefing context
                    gpt_say = await self.aask(
                        f"You have to answer to user obeying task assigned to you:\n{task_input.briefing}\n{user_say}",
                    )
                    print(f"GPT: {gpt_say}")
                    counter += 1
            except KeyboardInterrupt:
                # Log how many times the action was executed before exiting
                logger.info(f"executed talk action {counter} times")
            return counter


    async def main() -> None:
        """Main function."""
        # Create a role with a name, description, and registered skills
        role = Role(
            name="talker",
            description="talker role",
            # Skills map events to workflows - Event.quick_instantiate creates a trigger,
            # WorkFlow sequences the actions to execute
            skills={Event.quick_instantiate("talk").collapse(): WorkFlow(name="talk", steps=(Talk,))},
        )

        # Propose a task - the LLM generates a briefing from this objective
        task = await role.propose_task(
            "you have to act as a helpful assistant, answer to all user questions properly and patiently"
        )
        # Delegate sends the task to the workflow registered for the "talk" event
        _ = await task.delegate("talk")


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- ``Role`` wraps the agent with skills
- ``Event.quick_instantiate()`` creates a trigger event
- ``WorkFlow`` sequences the actions to execute
- ``Task`` carries input and can be proposed or created directly
- ``delegate()`` sends task to the workflow registered for that event

Retrieval-Augmented Generation (RAG)
------------------------------------

Combine LLM with your document knowledge base using Milvus vector search.

.. code-block:: python

    """Simple RAG example."""

    import asyncio

    from fabricatio import Action, Event, Task, WorkFlow, logger
    from fabricatio import Role as BaseRole
    from fabricatio_capabilities.capabilities.task import ProposeTask
    from fabricatio_milvus.capabilities.milvus import MilvusRAG
    from questionary import text


    class Role(ProposeTask, BaseRole):
        """basic role."""


    class Talk(Action, MilvusRAG):
        """Action with RAG capabilities - combines LLM with vector search."""

        output_key: str = "task_output"

        async def _execute(self, task_input: Task[str], **_) -> int:
            counter = 0

            # Initialize Milvus client - connects to the vector database
            self.init_client().view("test_collection", create=True)

            # Load documents into the knowledge base for retrieval
            # consume_string ingests text and creates embeddings
            await self.consume_string(
                [
                    "Company policy: all employees must arrive at headquarters before 9 AM daily.",
                    "Health guidelines: employees must wear company-provided athletic gear in gym.",
                    "Employee handbook: pets are not allowed in the office area.",
                    # ... more documents
                ]
            )
            try:
                while True:
                    user_say = await text("User: ").ask_async()
                    if user_say is None:
                        break
                    # aask_retrieved combines retrieval with generation:
                    # - First argument: query for retrieval
                    # - Second argument: user message for generation
                    # - extra_system_message: additional context for the LLM
                    gpt_say = await self.aask_retrieved(
                        user_say,
                        user_say,  # query for retrieval
                        extra_system_message=f"You have to answer to user obeying task assigned to you:\n{task_input.briefing}",
                    )
                    print(f"GPT: {gpt_say}")
                    counter += 1
            except KeyboardInterrupt:
                logger.info(f"executed talk action {counter} times")
            return counter


    async def main() -> None:
        """Main function."""
        role = Role(
            name="talker",
            description="talker role but with rag",
            skills={Event.quick_instantiate("talk").collapse(): WorkFlow(name="talk", steps=(Talk,))},
        )

        task = await role.propose_task(
            "you have to act as a helpful assistant, answer to all user questions properly and patiently"
        )
        _ = await task.delegate("talk")


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- Inherit ``MilvusRAG`` capability for vector search
- ``init_client()`` initializes the Milvus connection
- ``view()`` creates or opens a collection
- ``consume_string()`` ingests documents
- ``aask_retrieved()`` combines retrieval with generation

Code Review
-----------

Automated code review with structured output.

.. code-block:: python

    """Example of review usage."""

    import asyncio

    from fabricatio import Role, logger
    from fabricatio.capabilities import Review


    class Reviewer(Role, Review):
        """Reviewer role."""


    async def main() -> None:
        """Main function."""
        role = Reviewer(
            name="Reviewer",
            description="A role that reviews the code.",
        )

        # Generate some code using the role's LLM capability
        code = await role.aask(
            "write a cli app using rust with clap which can generate a basic manifest of a standard rust project, output code only"
        )

        logger.info(f"Code: \n{code}")

        # review_string returns a structured review result with display()
        res = await role.review_string(code, "If the cli app is of good design")
        logger.info(f"Review: \n{res.display()}")

        # supervisor_check adds LLM validation layer for additional confidence
        await res.supervisor_check()
        logger.info(f"Review: \n{res.display()}")


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- ``Review`` capability provides structured review methods
- ``review_string()`` returns a structured review result
- ``supervisor_check()`` adds LLM validation layer
- Results have ``display()`` for formatted output

Code Correction
---------------

Review code and automatically apply corrections based on review feedback.

.. code-block:: python

    """Example of code review with automatic correction."""

    import asyncio

    from fabricatio import Role as BaseRole
    from fabricatio import logger
    from fabricatio.capabilities import Correct, Review
    from fabricatio_core.utils import ok


    class Role(BaseRole, Review, Correct):
        """Role that can both review and correct code."""


    async def main() -> None:
        """Main function."""
        role = Role(
            name="Correction Officer",
            description="A role that reviews and corrects code.",
        )

        # Generate code to review
        code = await role.aask(
            "write a cli app using rust with clap which can generate a basic manifest of a standard rust project, output code only,no extra explanation"
        )

        logger.info(f"Original Code: \n{code}")

        # First, get a structured review with specific topic
        imp = ok(await role.review_string(code, topic="If the cli app is build with the derive feat enabled"))

        # Then apply corrections based on the review
        corrected = await role.correct_string(code, improvement=imp)
        logger.info(f"Corrected Code: \n{corrected}")


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- Combine ``Review`` and ``Correct`` capabilities for review-correction workflow
- ``review_string()`` with topic parameter for focused reviews
- ``correct_string()`` applies improvements identified in review

Task Proposal
-------------

Let the LLM propose tasks based on objectives.

.. code-block:: python

    """Example of task proposal."""

    import asyncio

    from fabricatio import Role
    from fabricatio.capabilities import ProposeTask


    class Planner(Role, ProposeTask):
        """Planner role that proposes tasks."""


    async def main() -> None:
        """Main function."""
        role = Planner(
            name="Planner",
            description="A role that proposes tasks.",
        )

        # Let the LLM propose tasks for a goal
        # mode="agentic" for more autonomous task decomposition
        # mode="standard" for simpler task proposals
        tasks = await role.propose_task(
            "Write a CLI tool that manages todo lists",
            mode="agentic",
        )

        for task in tasks:
            print(f"Proposed: {task.briefing}")
            # Execute the task using the default workflow
            result = await task.delegate("default")


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- ``ProposeTask`` capability lets LLM decompose objectives into tasks
- ``mode="agentic"`` for complex autonomous decomposition
- ``mode="standard"`` for simpler task proposals
- Iterate over proposed tasks and delegate each

Structured Output
-----------------

Get type-safe responses from LLM using Pydantic models.

.. code-block:: python

    """Structured output example."""

    import asyncio
    from pydantic import BaseModel

    from fabricatio import Role


    class Translation(BaseModel):
        original: str
        translated: str
        language: str


    class Translator(Role):
        """Translator role."""


    async def main() -> None:
        """Main function."""
        role = Translator(
            name="Translator",
            description="A role that translates text.",
        )

        # aask_structured returns a typed Pydantic instance
        result = await role.aask_structured(
            "Translate 'Hello, world!' to French",
            response_format=Translation,
        )

        print(f"Original: {result.original}")
        print(f"Translated: {result.translated}")
        print(f"Language: {result.language}")


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- Define Pydantic model with expected fields
- ``aask_structured()`` returns typed instance
- Automatic validation of LLM response

Extracting Structured Data
--------------------------

Extract information from unstructured text.

.. code-block:: python

    """Extraction example."""

    import asyncio
    from pydantic import BaseModel

    from fabricatio import Role
    from fabricatio.capabilities import Extract


    class PersonInfo(BaseModel):
        name: str
        age: int | None = None
        occupation: str | None = None
        skills: list[str] = []


    class Extractor(Role, Extract):
        """Extractor role."""


    async def main() -> None:
        """Main function."""
        role = Extractor(
            name="Extractor",
            description="A role that extracts information.",
        )

        text = """
        John Doe is a 35-year-old software engineer at Google.
        He has 10 years of experience and specializes in Python and Rust.
        """

        # extract_string parses unstructured text into typed model
        result = await role.extract_string(text, PersonInfo)
        print(f"Name: {result.name}")
        print(f"Age: {result.age}")
        print(f"Skills: {result.skills}")


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- ``Extract`` capability for structured extraction from text
- ``extract_string()`` parses text into Pydantic model
- Support for optional fields with defaults

Diff Editing
------------

Automatically fix spelling, wording, and other text issues with diff-based editing.

.. code-block:: python

    """Example of DiffEdit capability to fix spelling and wording in text."""

    from fabricatio import Action, Event, Role, Task, WorkFlow, logger
    from fabricatio.capabilities import DiffEdit
    from fabricatio_core.utils import ok

    # Example essay with spelling mistakes to correct
    essay_to_fix = """
    In my learn jorney, there is many teacher taht tought me, but the most i respect is our class moniter, Miss Li. She not only teach very carefull, but also care about every student very much.
    """


    class TweakEssay(Action, DiffEdit):
        """Action that fixes spelling mistakes and word usage using diff editing."""

        async def _execute(self, essay: str, **cxt) -> str:
            # diff_edit analyzes text and produces corrected version with changes
            return ok(
                await self.diff_edit(
                    essay,
                    "fix all spelling mistakes and typo or wrong usage of words in the essay."
                )
            )


    # Configure role workflow for essay tweaking
    Role(name="writer").add_skill(
        Event.quick_instantiate("tweak"),
        WorkFlow(name="tweak flow", steps=(TweakEssay().to_task_output(),))
    ).dispatch()


    # Create and execute the essay correction task
    new_essay = Task(name="tweak essay").update_init_context(essay=essay_to_fix).delegate_blocking("tweak")
    logger.info(f"Corrected essay:\n{new_essay}")

Key patterns:

- ``DiffEdit`` capability for automatic text correction
- ``diff_edit()`` applies fixes while preserving meaning
- ``to_task_output()`` converts action result to task output
- ``delegate_blocking()`` for synchronous execution

Rule-Based Processing
---------------------

Apply structured rules to content.

.. code-block:: python

    """Rule processing example."""

    import asyncio

    from fabricatio import Role
    from fabricatio.capabilities import Rule
    from fabricatio_rule.ruleset import RuleSet


    class Processor(Role, Rule):
        """Rule-based processor role."""


    async def main() -> None:
        """Main function."""
        role = Processor(
            name="Processor",
            description="A role that processes content with rules.",
        )

        # Define a rule set with multiple rules
        ruleset = RuleSet.parse_obj({
            "rules": [
                {
                    "name": "no-unsafe-html",
                    "pattern": r"<script|javascript:",
                    "action": "reject",  # reject: block content with match
                    "message": "Unsafe content detected"
                },
                {
                    "name": "sanitize-whitespace",
                    "pattern": r"\s+",
                    "action": "replace",  # replace: substitute matched text
                    "replacement": " "
                }
            ]
        })

        result = await role.apply_rules(
            "Some <script>alert('xss')</script>   text",
            ruleset
        )
        print(f"Processed: {result}")


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- Define rules with ``RuleSet`` - each rule has pattern, action, and message
- Actions: ``reject`` blocks content, ``replace`` substitutes text
- ``apply_rules()`` processes content through all matching rules
- Rules are executed in order, first match determines action

Content Improvement
-------------------

Improve writing quality with style and clarity enhancements.

.. code-block:: python

    """Content improvement example."""

    import asyncio

    from fabricatio import Role
    from fabricatio.capabilities import Improve


    class Improver(Role, Improve):
        """Improver role."""


    async def main() -> None:
        """Main function."""
        role = Improver(
            name="Improver",
            description="A role that improves content.",
        )

        original = """
        The quick brown fox jumped over the lazy dog.
        This is a old way to test typewriters.
        """

        # improve_string enhances content with specified style and focus
        improved = await role.improve_string(
            original,
            style="formal",  # or "casual", "technical", etc.
            focus="clarity"  # or "conciseness", "grammar", etc.
        )
        print(f"Improved: {improved}")


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- ``Improve`` capability for content enhancement
- ``improve_string()`` with style and focus parameters
- Multiple improvement dimensions supported

Task Handling with File Operations
----------------------------------

Write and save generated content to files using tool execution.

.. code-block:: python

    """Example of task handling with file operations."""

    import asyncio
    from typing import Any, Set

    from fabricatio import Action, Event, Task, WorkFlow, logger
    from fabricatio import Role as RoleBase
    from fabricatio.capabilities import HandleTask, ProposeTask
    from fabricatio.models import ToolBox, fs_toolbox
    from fabricatio_core.capabilities.usages import UseLLM
    from fabricatio_core.utils import ok
    from pydantic import Field


    class Role(RoleBase, ProposeTask):
        """Role that can propose tasks."""


    class WriteCode(Action, UseLLM):
        """Action that generates Python code."""

        output_key: str = "dump_text"

        async def _execute(self, task_input: Task[str], **_) -> str:
            # acode_string generates code with specified language
            return ok(await self.acode_string(f"{task_input.dependencies_prompt}\n\n{task_input.briefing}", "python"))


    class DumpText(Action, HandleTask):
        """Action that writes text content to a file using fs_toolbox."""

        # fs_toolbox provides file system operations (read, write, etc.)
        toolboxes: Set[ToolBox] = Field(default_factory=lambda: {fs_toolbox})
        output_key: str = "task_output"

        # Key used to capture the file path from tool execution result
        save_key: str = "save_path"

        async def _execute(self, task_input: Task, dump_text: str, **_) -> Any:
            logger.debug(f"Dumping text: \n{dump_text}")
            # handle() executes a skill with given context and output schema
            collector = ok(
                await self.handle(
                    task_input.briefing,
                    {"text_to_dump": dump_text},
                    {self.save_key: "the pathstr of the written file"}
                )
            )
            # Extract the saved file path from collector
            return collector.take(self.save_key, str)


    async def main() -> None:
        """Main function."""
        role = Role(
            name="Coder",
            description="A python coder who writes and saves code",
            skills={
                # Workflow: generate code, then dump to file
                Event.quick_instantiate("coding").collapse(): WorkFlow(
                    name="write code", steps=(WriteCode, DumpText)
                ),
            },
        ).dispatch()

        # Propose a task and delegate to "coding" workflow
        proposed_task: Task[str] = ok(
            await role.propose_task(
                "write a cli app implemented with python, which can calculate the sum to a given n, all write to a single file named `cli.py`, put it in `output` folder."
            )
        )
        path = ok(await proposed_task.delegate("coding"))
        logger.info(f"Code saved to: {path}")


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- ``HandleTask`` capability enables tool execution within actions
- ``fs_toolbox`` provides file system operations (write, read, etc.)
- ``handle()`` executes skills with input/output schema
- Chain multiple actions in a WorkFlow for pipeline execution
- ``dependencies_prompt`` passes data between workflow steps

Task Cancellation and Checkpoint
--------------------------------

Cancel long-running tasks and retrieve partial outputs.

.. code-block:: python

    """Example of task cancellation and checkpoint."""

    import asyncio

    from fabricatio import Action, Event, Task, WorkFlow, logger
    from fabricatio import Role as RoleBase
    from fabricatio.capabilities import HandleTask, ProposeTask
    from fabricatio.models import ToolBox, fs_toolbox
    from fabricatio_core.capabilities.usages import UseLLM
    from fabricatio_core.utils import ok
    from pydantic import Field


    class Role(RoleBase, ProposeTask):
        """Role that can propose tasks."""


    class WriteToOutput(Action):
        """Simple action that returns static output."""

        output_key: str = "task_output"

        async def _execute(self, **_) -> str:
            return "hi, this is the output"


    class TestCancel(Action):
        """Action that increments counter - used to test cancellation."""

        output_key: str = "counter"

        async def _execute(self, counter: int, **_) -> int:
            logger.info(f"Counter: {counter}")
            await asyncio.sleep(5)  # Simulate long-running work
            counter += 1
            return counter


    async def main() -> None:
        """Main function."""
        role = Role(
            name="Coder",
            description="Test cancellation",
            skills={
                Event.quick_instantiate("cancel_test").collapse(): WorkFlow(
                    name="cancel_test",
                    # Multiple steps - some will be skipped on cancel
                    steps=(TestCancel, TestCancel, TestCancel, TestCancel, TestCancel, TestCancel, WriteToOutput),
                    # Initialize counter to 0 for this workflow
                    extra_init_context={"counter": 0},
                ),
            },
        ).dispatch()

        proposed_task = ok(
            await role.propose_task("test cancellation workflow")
        )

        # Publish and immediately cancel the task
        proposed_task.publish("cancel_test")
        await proposed_task.cancel()

        # get_output retrieves the output up to the point of cancellation
        out = await proposed_task.get_output()
        logger.info(f"Canceled Task Output: {out}")


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- ``publish()`` triggers a workflow without waiting
- ``cancel()`` stops task execution
- ``get_output()`` retrieves partial results after cancellation
- ``extra_init_context`` provides initial state for workflows

Diary Generation from Commit History
------------------------------------

Generate diaries from structured data like git commits.

.. code-block:: python

    """Example of diary generation from commit messages."""

    import asyncio
    from datetime import datetime
    from typing import Any, Dict, Optional, Set

    from fabricatio import Action, Event, Task, WorkFlow, logger
    from fabricatio import Role as RoleBase
    from fabricatio.capabilities import Handle
    from fabricatio.models import ToolBox
    from fabricatio_capabilities.capabilities.task import ProposeTask
    from fabricatio_core.capabilities.usages import UseLLM
    from fabricatio_core.utils import ok
    from fabricatio_tool import toolboxes
    from fabricatio_tool.fs import safe_json_read
    from pydantic import Field


    class WriteDiary(Action, UseLLM):
        """Action that generates diary entries from commit messages."""

        output_key: str = "dump_text"

        async def _execute(self, task_input: Task[str], **_) -> str:
            # Set goals for the LLM to follow when generating diary
            task_input.goals.clear()
            task_input.goals.extend(
                [
                    "write a Internship Diary according to the given commit messages",
                    "the diary should include the main dev target of the day, and the exact content",
                    "make a summary of the day, what have been learned, and what had felt",
                    "diary should be written in markdown format, using Chinese",
                    "write dev target and exact content under `# 实习主要项目和内容`",
                    "write summary under `# 主要收获和总结`",
                ]
            )

            # Read dependency file (commits.json) using registered reader
            json_data = task_input.read_dependency(reader=safe_json_read)
            # Sort by date
            seq = sorted(json_data.items(), key=lambda x: datetime.strptime(x[0], "%Y-%m-%d"))

            # Generate diary entries for each day
            res = await self.aask(
                [
                    f"{task_input.briefing}\n{c}\nWrite a diary for {d}, based on the commits. 不要太流水账,着重于高级的设计抉择和设计思考,保持日记整体200字左右。"
                    for d, c in seq
                ],
                temperature=1.5,
                top_p=1.0,
            )

            return "\n\n\n".join(res)


    class DumpText(Action, Handle):
        """Dump the text to a file using fs_toolbox."""

        toolboxes: Set[ToolBox] = Field(default_factory=lambda: {toolboxes.fs_toolbox})
        output_key: str = "task_output"

        async def _execute(self, task_input: Task, dump_text: str, **_: Any) -> Optional[str]:
            task_input.update_task(
                goal=["dump the text contained in `text_to_dump` to a file", "only return the path of the written file"]
            )

            resc = await self.handle_fine_grind(
                task_input.assembled_prompt,
                {"text_to_dump": dump_text},
                {"written_file_path": "path of the written file"}
            )
            if resc:
                return resc.take("written_file_path")
            return None


    class Coder(RoleBase, ProposeTask):
        """A role that generates diaries from commit history."""

        skills: Dict[EventPattern, WorkFlow] = Field(
            default={
                Event.quick_instantiate("doc").collapse(): WorkFlow(
                    name="write documentation", steps=(WriteDiary, DumpText)
                ),
            }
        )


    async def main() -> None:
        """Main function."""
        role = Coder()

        task = ok(
            await role.propose_task(
                "Write a diary according to the given commit messages in json format. "
                "dump to `diary.md` at `output` dir. "
                "In the json the key is the day in which the commit messages in value was committed."
            )
        )
        # Override dependencies to point to actual commit file
        task.override_dependencies("./commits.json")
        await task.move_to("doc").delegate()


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- ``read_dependency()`` reads external files with a registered reader
- ``goals`` list guides LLM behavior for structured output
- ``override_dependencies()`` replaces dependency source
- ``move_to()`` redirects task to a different event/workflow

Article Extraction and Storage
------------------------------

Extract key essence from articles and store in vector database.

.. code-block:: python

    """Example of article essence extraction and injection."""

    import asyncio
    from pathlib import Path
    from typing import Optional

    from fabricatio import Event, Task, WorkFlow, logger
    from fabricatio import Role as BaseRole
    from fabricatio.actions import ExtractArticleEssence, FixArticleEssence, InjectToDB, PersistentAll
    from fabricatio_core.capabilities.usages import UseLLM
    from fabricatio_core.rust import tokens_of
    from fabricatio_tool.fs import gather_files
    from fabricatio_typst.rust import BibManager


    MAX_TOKEN = 64000


    def _reader(path: str) -> Optional[str]:
        """Custom reader that loads and validates article files."""
        string = Path(path).read_text(encoding="utf-8")
        # Split at references section
        string = string.split("References\n")[0]
        string = string.split("参考文献\n")[0]
        # Check token limit
        if (leng := tokens_of(text=string)) > MAX_TOKEN:
            logger.warn(f"{path} is too long, got {leng} tokens, skip.")
            return None
        logger.info(f"Read {path} get {leng} tokens.")
        return string


    class Role(BaseRole, UseLLM):
        """Role class for article processing."""


    async def main() -> None:
        """Main function."""
        Role(
            name="Researcher",
            description="Extract article essence",
            llm_send_to="openai/deepseek-v3-250324",
            skills={
                Event.quick_instantiate("article").collapse(): WorkFlow(
                    name="extract",
                    # Multi-step pipeline: extract -> fix -> persist -> inject
                    steps=(
                        ExtractArticleEssence(output_key="article_essence"),
                        FixArticleEssence(output_key="to_inject"),
                        PersistentAll,
                        InjectToDB(output_key="task_output"),
                    ),
                ).update_init_context(
                    override_inject=True,
                    collection_name="article_essence_0324",
                    persist_dir="output_0324",
                    bib_mgr=BibManager("ref.bib"),
                    reader=_reader,  # Custom file reader
                )
            },
        )

        # Create task with dependencies (gather all markdown files)
        task: Task[str] = Task(
            name="Extract Article Essence",
            description="Extract the essence of the article from the files in './bpdf_out'",
            dependencies=gather_files("bpdf_out", "md"),
        )

        # Delegate to article workflow
        col_name = await task.delegate("article")

        if col_name is None:
            logger.error("No essence found")
            return
        logger.info(f"Injected to collection: {col_name}")


    if __name__ == "__main__":
        asyncio.run(main())

Key patterns:

- ``ExtractArticleEssence`` extracts key content from articles
- ``FixArticleEssence`` post-processes extracted content
- ``PersistentAll`` saves extracted data to disk
- ``InjectToDB`` stores processed data in vector database
- ``gather_files`` collects files matching pattern
- Custom ``reader`` function for domain-specific file handling

Anki Deck Generation
--------------------

Generate Anki flashcards from CSV question banks.

.. code-block:: python

    """Example of Anki deck generation from CSV data."""

    from pathlib import Path

    from fabricatio import Action, Event, Role, Task, WorkFlow
    from fabricatio.capabilities import GenerateDeck
    from fabricatio.models import Deck
    from fabricatio_anki.actions.topic_analysis import AppendTopicAnalysis
    from fabricatio_anki.rust import add_csv_data, compile_deck
    from fabricatio_core import logger
    from fabricatio_core.utils import ok


    def get_column_names(csv_file_path: Path | str) -> list[str]:
        """Extract column names from a CSV file."""
        import csv

        with Path(csv_file_path).open(newline="", encoding="utf-8-sig") as csv_file:
            csv_reader = csv.reader(csv_file)
            return next(csv_reader)  # First row is column names


    class DeckGen(Action, GenerateDeck):
        """Action that generates an Anki deck from CSV data."""

        async def _execute(self, source: Path, req: str, output: Path, **cxt) -> Deck:
            # Get column names from CSV for deck generation
            names = get_column_names(source)
            logger.info(f"Column names: {names}")

            # Generate deck with specified requirements
            # km/kt control model configuration
            gen_deck = ok(await self.generate_deck(req, names, km=1, kt=1))

            # Save deck definition
            gen_deck.save_to(output)
            # Add CSV data to deck models
            add_csv_data(output, gen_deck.models[0].name, source)

            return gen_deck


    # Configure role with deck generation and topic analysis skills
    (
        Role()
        .add_skill(Event.quick_instantiate(ns := "generate_deck"), WorkFlow(steps=(DeckGen().to_task_output(),)))
        .add_skill(
            Event.quick_instantiate(ns2 := "topic_analyze"),
            WorkFlow(steps=(AppendTopicAnalysis(csv_file="topics.csv").to_task_output(),)),
        )
        .dispatch()
    )

    # Define requirements for deck generation
    requirement = (
        "Generate an Anki Deck for this question bank. The users are college students. "
        "The deck should have a modern UI design and interactive features, "
        "including animations when cards are clicked. Additionally, "
        "it should display the time taken to answer each question and the accuracy rate. "
        "You Must use github-dark coloring for the UI design."
    )

    # Generate initial deck
    deck: Deck = ok(
        Task(name="gen deck")
        .update_init_context(source="topics.csv", req=requirement, output="here")
        .delegate_blocking(ns)
    )

    # Compile deck to .apkg format for Anki
    compile_deck("here", f"{deck.name}.apkg")
    logger.info(f"Compiled deck saved to {deck.name}.apkg")

Key patterns:

- ``GenerateDeck`` capability for flashcard generation
- ``generate_deck()`` creates deck from CSV column names and requirements
- ``add_csv_data()`` associates question bank data with deck
- ``compile_deck()`` produces .apkg package for Anki import
- ``AppendTopicAnalysis`` provides topic analysis on CSV data

Example Categories
------------------

The repository includes the following example directories:

+-----------------------+-------------------------------------------------------+
| Category              | Contents                                              |
+=======================+=======================================================+
| ``basics``            | Hello world, basic workflow, simple interactive chat  |
+-----------------------+-------------------------------------------------------+
| ``generation``        | Content generation: poems, articles, novels, songs,   |
|                       | diaries, outlines                                     |
+-----------------------+-------------------------------------------------------+
| ``rag``               | Retrieval-Augmented Generation: extraction, injection,|
|                       | chunking, Milvus Q&A                                  |
+-----------------------+-------------------------------------------------------+
| ``review``            | Code review, correction, diff editing, quality        |
+-----------------------+-------------------------------------------------------+
| ``task_management``   | Task proposal, delegation, handling, cancellation,    |
|                       | LLM-driven code generation                            |
+-----------------------+-------------------------------------------------------+
| ``rating``            | Multi-criteria rating and composite scoring           |
+-----------------------+-------------------------------------------------------+
| ``integrations``      | Anki deck generation, BibTeX search, ruleset drafting |
+-----------------------+-------------------------------------------------------+

Running Examples
----------------

.. code-block:: bash

    # Basics — hello world and simple chat
    python examples/basics/hello_fabricatio.py
    python examples/basics/simple_chat.py

    # Generation — content creation
    python examples/generation/write_outline.py
    python examples/generation/write_outline_corrected.py
    python examples/generation/write_article.py
    python examples/generation/write_novel.py
    python examples/generation/generate_diary.py

    # RAG — retrieval-augmented generation
    python examples/rag/simple_rag.py
    python examples/rag/extract_article.py
    python examples/rag/extract_and_inject.py

    # Review — code review and correction
    python examples/review/review.py
    python examples/review/correct.py
    python examples/review/correct_loop.py
    python examples/review/diff_edit.py

    # Task management — delegation and cancellation
    python examples/task_management/propose_task.py
    python examples/task_management/task_with_cancellation.py

    # Rating — multi-criteria evaluation
    python examples/rating/rate_food.py

    # Integrations — tools and plugins
    python examples/integrations/anki_deck_gen.py
    python examples/integrations/bibtex_search.py
    python examples/integrations/draft_ruleset.py
