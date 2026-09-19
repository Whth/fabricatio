r"""Progressive skill disclosure with fabricatio-skill on a real LLM. A Role subscribes a WorkFlow whose Action mixes UseSkill: consult_skills shows the LLM only name+description briefings to pick relevant skills, distills the picked bodies into a question-focused essence, and only that essence joins the answering prompt - the full bodies never reach the answerer. Needs a configured LLM (FABRICATIO_* env / user config)."""

import asyncio
import tempfile
from pathlib import Path

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio_skill import UseSkill

QUESTION = "How do I spawn concurrent tasks in tokio?"

SKILL_FILES: dict[str, str] = {
    "tokio.md": (
        "---\n"
        "name: rust-async\n"
        'description: "Write async Rust with tokio: runtime, spawn, cancellation"\n'
        "tags: [rust, async]\n"
        "---\n"
        "# tokio runtime\n"
        "Always build the runtime explicitly with tokio::runtime::Builder.\n"
        "## Spawning tasks\n"
        "Use tokio::spawn(future); it returns a JoinHandle you can await to join.\n"
        "## Cancellation\n"
        "Drop the JoinHandle to detach; use CancellationToken for cooperative cancel.\n"
    ),
    "sql.md": (
        "---\n"
        "name: sql-style\n"
        'description: "SQL naming conventions"\n'
        "tags: [sql]\n"
        "---\n"
        "Use snake_case for columns, UPPER_SNAKE for enum values.\n"
    ),
}


def make_skill_dir() -> Path:
    """Write the demo library to a throwaway dir; skill files are plain markdown with YAML frontmatter."""
    tmp = Path(tempfile.mkdtemp(prefix="skill_demo_"))
    for fname, text in SKILL_FILES.items():
        (tmp / fname).write_text(text, encoding="utf-8", newline="\n")
    return tmp


class ConsultSkills(Action, UseSkill):
    """Consult the skill library, then answer grounded in the distilled knowledge."""

    output_key: str = "task_output"
    skill_dir: str  # gather from here; the library loads ./.agents/skills when it is created

    async def _execute(self, task_input: Task[str], **_) -> str:
        self.scan_skills(self.skill_dir)  # one in-memory copy per skill; idempotent
        question = task_input.briefing
        knowledge = await self.consult_skills(question)  # select (briefings only) -> distill (picked bodies)
        if not knowledge:
            return question  # nothing relevant: fall back to the bare question
        logger.info(f"knowledge fed to the answerer:\n{knowledge}")
        return await self.aask(f"{knowledge}\n\n---\n\n{question}")


async def main() -> None:
    """Register the skill-consulting workflow, delegate a question, print the grounded answer."""
    Role.with_bio(name="skilled", description="answers questions grounded in its skill library").subscribe(
        Event.quick_instantiate("skillqa"),
        WorkFlow(name="skill qa", steps=(ConsultSkills(skill_dir=str(make_skill_dir())),)),
    ).dispatch()

    answer = await Task(name="tokio question", goals=[QUESTION], description=QUESTION).delegate("skillqa")
    assert isinstance(answer, str), "delegate resolves to the Action's task_output"
    assert answer.strip(), "answer should be non-empty"
    print(f"Q: {QUESTION}\nA: {answer}")


if __name__ == "__main__":
    asyncio.run(main())
