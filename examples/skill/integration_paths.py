r"""Five ways to integrate fabricatio-skill into a system - one runnable tour.

A skill is a markdown file: YAML frontmatter (`name`, `description`, `tags`) plus a body.
This package only ever *consults* skills - every path below ends with your own LLM call.

1. drop-in capability - mix the capability in, ship a `skills/` directory, done. Zero wiring.
2. explicit library   - keep your own directory and file layout, register it yourself.
3. by name            - you know the skills already: no scan, no LLM selection, no guesswork.
4. manual stages      - call SELECT and DISTILL yourself and own the prompt assembly.
5. framework-free     - `SkillRegistry` as a plain library: no Role, Task or WorkFlow.

Paths 1-4 use the LLM (selection/distillation run on the SMOL tier); path 5 is deterministic.
Needs a configured LLM (FABRICATIO_* env / user config).
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import TypedDict, Unpack

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio_skill import SkillRegistry, UseSkill


class ActionContextKwargs(TypedDict, total=False):
    """Keyword context a workflow injects besides `task_input`.

    The shared context dict is open-ended - earlier actions may have stored anything in it -
    so this names the keys the framework itself defines; unknown keys are ignored here.
    """

    task_output: str


QUESTION = "How do I spawn concurrent tasks in tokio, and how do I cancel one?"

# The demo library: both supported layouts in one directory.
SKILLS: dict[str, str] = {
    "rust-async/SKILL.md": (
        "---\n"
        "name: rust-async\n"
        'description: "Write async Rust with tokio: runtime, spawn, cancellation"\n'
        "tags: [rust, async]\n"
        "---\n"
        "# tokio\n"
        "Build the runtime explicitly with tokio::runtime::Builder.\n"
        "Spawn work with tokio::spawn(future); it returns a JoinHandle you can await to join.\n"
        "Cancel cooperatively with a CancellationToken, or drop the JoinHandle to detach.\n"
    ),
    "sql-style.md": (
        "---\n"
        "name: sql-style\n"
        'description: "SQL naming conventions used in this repo"\n'
        "tags: [sql]\n"
        "---\n"
        "Columns are snake_case; enum values are UPPER_SNAKE.\n"
    ),
}


def write_library(root: Path) -> Path:
    """Write the demo skills under `root`: `<name>/SKILL.md` and `<name>.md` are equally valid."""
    for relative, text in SKILLS.items():
        file = root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8", newline="\n")
    return root


def show(label: str, text: str, width: int = 180) -> None:
    """Print one compact line, so the whole tour stays readable in a scrollback."""
    flat = " ".join(text.split())
    print(f"   {label}: {flat[:width]}{'...' if len(flat) > width else ''}")


async def path_1_drop_in_capability() -> None:
    """Ship a `skills/` directory next to your entrypoint and mix `UseSkill` into an Action.

    Nothing is loaded by hand: the default roots (`skills/` and `extra/skills/`, resolved
    against the process working directory, plus `~/.agents/skills`) are scanned on the first
    `consult_skills()` call, and only the skill names are tracked on the action.
    """

    class AnswerFromDefaultRoots(Action, UseSkill):
        """Answer the task briefing from the auto-loaded skill library."""

        output_key: str = "task_output"

        async def _execute(self, task_input: Task[str], **_: Unpack[ActionContextKwargs]) -> str:
            knowledge = await self.consult_skills(task_input.briefing)
            if not knowledge:
                return task_input.briefing
            show(f"consulted knowledge ({len(knowledge)} chars)", knowledge)
            return await self.aask(f"{knowledge}\n\n---\n\n{task_input.briefing}")

    action = AnswerFromDefaultRoots()
    Role.with_bio(name="skill:drop-in", description="answers from the default skill roots").subscribe(
        Event.quick_instantiate("skill_drop_in"), WorkFlow(name="skill drop in", steps=(action,))
    ).dispatch()

    project = Path(tempfile.mkdtemp(prefix="skill_project_"))
    write_library(project / "skills")
    cwd = Path.cwd()
    os.chdir(project)  # the relative default roots resolve against the working directory
    try:
        answer = await Task(name="tokio question", goals=[QUESTION], description=QUESTION).delegate("skill_drop_in")
    finally:
        os.chdir(cwd)

    assert isinstance(answer, str), "delegate resolves to the action's task_output"
    assert answer.strip(), "the answer should not be empty"
    print(f"   auto-loaded from ./skills: {action.skill_names}")
    show("answer", answer)


async def path_2_explicit_library(library: Path) -> None:
    """Keep your own directory layout: load the library yourself before consulting.

    `scan_skills` is the bulk loader - it walks a directory, parses every `.md` into a
    `Skill`, and tracks only the names on this action. Skills already in the process-wide
    library keep their first copy and are not read again, so calling it on every execution
    is safe.
    """

    class AnswerFromOwnLibrary(Action, UseSkill):
        """Consult one explicit library directory instead of the default roots."""

        output_key: str = "task_output"
        skill_dir: str  # ctor-injected: where this deployment keeps its skills

        async def _execute(self, task_input: Task[str], **_: Unpack[ActionContextKwargs]) -> str:
            self.scan_skills(self.skill_dir)  # one in-memory copy per skill name; idempotent
            knowledge = await self.consult_skills(task_input.briefing)
            if not knowledge:
                return task_input.briefing
            show(f"consulted knowledge ({len(knowledge)} chars)", knowledge)
            return await self.aask(f"{knowledge}\n\n---\n\n{task_input.briefing}")

    print(f"   library holds: {SkillRegistry.instance().names()}")

    Role.with_bio(name="skill:own-library", description="answers from one registered directory").subscribe(
        Event.quick_instantiate("skill_own_library"),
        WorkFlow(name="skill own library", steps=(AnswerFromOwnLibrary(skill_dir=str(library)),)),
    ).dispatch()

    answer = await Task(name="tokio question", goals=[QUESTION], description=QUESTION).delegate("skill_own_library")
    assert isinstance(answer, str), "delegate resolves to the action's task_output"
    print(f"   library now holds: {SkillRegistry.instance().names()}")
    show("answer", answer)


async def path_3_by_name(library: Path) -> None:
    """Gather by name: the skills are known, so nothing has to be scanned or selected.

    `gather_skills` resolves each name straight under the lookup roots (`<root>/<name>/SKILL.md`
    first, then `<root>/<name>.md` - direct path reads, no directory walk) and loads the hits
    into the process-wide library. Passing `names=` to `consult_skills` skips LLM selection,
    and `distill=False` skips distillation: the bodies reach your own answering call verbatim,
    with zero LLM stages in between.
    """
    wanted = ["rust-async", "sql-style", "does-not-exist"]
    resolved = SkillRegistry.instance().load_by_name(wanted, [str(library)])
    print(f"   load_by_name({wanted}) -> {resolved} (missing names are skipped)")

    class AnswerFromNamedSkills(Action, UseSkill):
        """Answer from a fixed, named skill set: deterministic context, no chooser prompt."""

        output_key: str = "task_output"
        skill_dir: str
        names: list[str]

        async def _execute(self, task_input: Task[str], **_: Unpack[ActionContextKwargs]) -> str:
            self.gather_skills(self.names, dirs=[self.skill_dir])
            knowledge = await self.consult_skills(task_input.briefing, names=self.names, distill=False)
            if not knowledge:
                return task_input.briefing
            show(f"verbatim knowledge ({len(knowledge)} chars, 0 LLM stages)", knowledge)
            return await self.aask(f"{knowledge}\n\n---\n\n{task_input.briefing}")

    Role.with_bio(name="skill:by-name", description="answers from an explicitly named skill set").subscribe(
        Event.quick_instantiate("skill_by_name"),
        WorkFlow(name="skill by name", steps=(AnswerFromNamedSkills(skill_dir=str(library), names=["rust-async"]),)),
    ).dispatch()

    answer = await Task(name="tokio question", goals=[QUESTION], description=QUESTION).delegate("skill_by_name")
    assert isinstance(answer, str), "delegate resolves to the action's task_output"
    show("answer", answer)


async def path_4_manual_stages(library: Path) -> None:
    """Take only the two LLM stages and build the prompt yourself.

    `select_skills` presents the chooser with briefings only (`name: description`);
    `distill_skills` compresses only the bodies it is handed. Everything between and
    after them is yours - here the distilled guidance becomes part of your own prompt.
    """

    class AnswerFromStages(Action, UseSkill):
        """Drive SELECT and DISTILL by hand, then assemble a custom prompt."""

        output_key: str = "task_output"
        skill_dir: str

        async def _execute(self, task_input: Task[str], **_: Unpack[ActionContextKwargs]) -> str:
            self.scan_skills(self.skill_dir)
            question = task_input.briefing
            # `available=[...]` would narrow the pool; `k=` caps the selection.
            # None means the LLM never produced a valid selection, [] means nothing matched.
            picked = await self.select_skills(question, k=1)
            if not picked:
                logger.warn("No skill selected; answering unaided.")
                return await self.aask(question)
            logger.info(f"selected: {[skill.name for skill in picked]}")
            guidance = await self.distill_skills(question, picked)
            show(f"distilled guidance ({len(guidance)} chars)", guidance)
            return await self.aask(f"{question}\n\nAnswer using only this guidance:\n{guidance}")

    Role.with_bio(name="skill:stages", description="drives the select/distill stages by hand").subscribe(
        Event.quick_instantiate("skill_stages"),
        WorkFlow(name="skill stages", steps=(AnswerFromStages(skill_dir=str(library)),)),
    ).dispatch()

    answer = await Task(name="tokio question", goals=[QUESTION], description=QUESTION).delegate("skill_stages")
    assert isinstance(answer, str), "delegate resolves to the action's task_output"
    show("answer", answer)


def path_5_framework_free(library: Path) -> str:
    """Use the skill library as a plain library: no Role, no Task, no WorkFlow, no LLM.

    Everything here is a synchronous call you can drop into an agent loop you already
    have (or a plain service): `Skill` owns the parsed markdown, `SkillMeta` is the
    content-free view for cheap menus, and the library is process-wide - the same one
    the capability mixin above resolves through.
    """
    registry = SkillRegistry.instance()
    catalog_names = registry.load_scanned([str(library)])  # walk + parse every .md
    one = registry.get("rust-async")  # exact-name lookup in the parsed copy
    hits = registry.search("tokio", names=catalog_names, in_content=True)  # keyword search, no LLM

    assert one is not None, "the demo library defines rust-async"
    catalog = registry.get_many(catalog_names)
    menu = "\n".join(f"- {meta.name}: {meta.description}" for meta in (skill.meta() for skill in catalog))
    system_prompt = f"Available skills:\n{menu}\n\n--- skill: {one.name} ---\n{one.content}"

    print(f"   library ({len(catalog_names)} entries): {catalog_names}")
    print(f"   keyword hits for 'tokio': {[skill.name for skill in hits]}")
    return system_prompt


async def main() -> None:
    """Run all five integration paths over one throwaway library and print what each assembled."""
    library = write_library(Path(tempfile.mkdtemp(prefix="skill_demo_")) / "skills")
    print(f"demo library: {library}")

    print("\n1/5 drop-in capability - mix UseSkill in, ship ./skills")
    await path_1_drop_in_capability()

    print("\n2/5 explicit library - register your own directory")
    await path_2_explicit_library(library)

    print("\n3/5 by name - gather_skills by name, zero LLM stages")
    await path_3_by_name(library)

    print("\n4/5 manual stages - select_skills + distill_skills, your own prompt")
    await path_4_manual_stages(library)

    print("\n5/5 framework-free - the library in your own loop")
    show("assembled prompt", path_5_framework_free(library))


if __name__ == "__main__":
    asyncio.run(main())
