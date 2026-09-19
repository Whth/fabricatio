# `fabricatio-skill`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-skill)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-skill)](https://pypi.org/project/fabricatio-skill/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-skill/week)](https://pepy.tech/projects/fabricatio-skill)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-skill)](https://pepy.tech/projects/fabricatio-skill)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)



An extension of fabricatio.

---

## Installation


This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[skill]

# or with uv
# uv pip install fabricatio[skill]
```

Or install `fabricatio-skill` along with all other components of `fabricatio`:

```bash
pip install fabricatio[full]

# or with uv
# uv pip install fabricatio[full]
```

## Overview

A text-based skill system for fabricatio agents. Skills are plain markdown files
(YAML frontmatter `name`/`description`/`tags` + markdown body) that inject
just-in-time, task-relevant context into LLM prompts through **progressive
disclosure**: cheap metadata first, LLM-powered selection next, distilled
essence last — never the full corpus.

Exclusion is just as progressive: a deterministic Rust keyword pre-filter
thins oversized pools before any LLM sees them, selection admits only
catalog-validated candidates (capped), and distillation drops everything the
question does not need. Content that fails an earlier stage never reaches a
later prompt.

## Key Features

- **Markdown-native skills** — author skills as `.md` files with YAML frontmatter; no schema lock-in beyond three metadata keys.
- **Two library layouts** — per root, skills resolve either by the agent-skills convention (`<name>/SKILL.md`) or as flat files (`<name>.md`); the default roots include the user-level `~/.agents/skills` library.
- **By-name gathering** — `gather_skills(names, dirs=None)` resolves skills straight from the lookup roots by name (direct path reads, no corpus scan), loads them into the library, and tracks them on the role.
- **Progressive pipeline** — Level 0 (library): the process-wide `SkillRegistry` — recursive scanning (`load_scanned`), by-name resolution (`load_by_name`), keyword search (`SkillRegistry.search`, also the deterministic pre-filter for huge libraries); Level 1 (Python): LLM-powered relevance selection (`select_skills`, delegated to the framework `UseLLM.achoose` chooser over skill briefings — set-validated, auto-retried, SMOL tier, capped) and essence distillation (`distill_skills`); Level 2: the composed `consult_skills` pipeline (select -> distill -> consulted knowledge). Consultation only — answering stays in your Action.
- **Progressive disclosure dial** — every call trades fidelity for tokens via `select=` / `distill=` / forced `names=`.
- **Lightweight composition** — heavy `Skill` objects live in the process-wide library (`SkillRegistry.instance()`, reachable from a role as `role.skill_library`); your roles/actions carry only a list of name handles, and the loaders (`scan_skills`, `gather_skills`, `add_skills`) chain on the role.
- **Rust-backed performance** — parsing, lookup, and keyword matching are PyO3 (`fabricatio_skill.rust`).

## Usage

### 1. Author skill files

Drop markdown files into a skill directory (default roots: `skills/`,
`extra/skills/`, `~/.agents/skills`). Each root supports both layouts — the
agent-skills convention and flat files:

```
skills/
├── rust-async/SKILL.md      # <name>/SKILL.md layout
└── code_review.md           # <name>.md layout
```

```markdown
---
name: rust-async
description: "How to write async Rust with tokio correctly"
tags: [rust, async]
---
Markdown body with the actual instructions...
```

Frontmatter notes:

- `name` is the unique catalog id (the LLM selects by it); `description` is the
  whole selection surface — keep it a dense one-liner; `tags` help the Rust
  keyword pre-filter.
- YAML rules apply: quote string values that contain `: ` (e.g. descriptions),
  or the field silently parses as empty.

### 2. Consult — zero-config (canonical path)

Nothing to load. On the **first** `consult_skills()` call of a role that has no
skills yet, the default directories (`skills/`, `extra/skills/` relative to
the process working directory, plus the user-level `~/.agents/skills`) are
auto-scanned once and their skills registered. Authoring files and consulting
is the whole loop:

```python
from fabricatio import Action, Event, Role, Task, WorkFlow
from fabricatio_skill import UseSkill


class AnswerWithSkills(Action, UseSkill):
    """Answer the task briefing grounded in consulted skill knowledge."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> str:
        # select relevant skills -> distill what they say (both SMOL tier);
        # "" when nothing is relevant. Answering stays YOUR job.
        knowledge = await self.consult_skills(task_input.briefing)
        if not knowledge:
            return task_input.briefing
        return await self.aask(f"{knowledge}\n\n---\n\n{task_input.briefing}")


role = (
    Role.with_bio(name="skilled", description="answers using the skill library")
    .subscribe(
        Event.quick_instantiate("ask"),
        WorkFlow(name="skill_qa", steps=(AnswerWithSkills,)),
    )
    .dispatch()
)
# dispatch a Task whose briefing is the question to Event "ask" — done
```

### 3. Tune the disclosure level per call

`consult_skills()` is the progressive-disclosure dial; it returns what the
relevant skills say (or `""` when nothing is relevant — a `"[]"` selection
from the LLM, an exhausted selection retry, or an empty library all mean the
same thing: there is nothing to consult):

| Call | Returns |
|---|---|
| `await self.consult_skills(q)` | Distilled essence of LLM-selected skills (2 extra LLM calls on the `SMOL` tier). |
| `await self.consult_skills(q, k=3)` | Same, but this call fetches at most 3 skills (`k=0` = no limit, `k=None` = the `max_selected_skills` config). |
| `await self.consult_skills(q, names=["rust-async"])` | Forced skills — skips LLM selection entirely. |
| `await self.consult_skills(q, distill=False)` | Full bodies of selected skills — no compression call. |
| `await self.consult_skills(q, select=False, distill=False)` | Every registered skill verbatim — zero LLM calls. |

For finer control, step through the levels manually:

```python
picked = await agent.select_skills(question)              # metadata-only chooser
if picked:                                                # None = LLM never answered validly
    essence = await agent.distill_skills(question, picked)  # compress only selected bodies
    answer = await agent.aask(f"{essence}\n\n---\n\n{question}")
else:
    answer = question                                     # nothing relevant: no skill context
```

**What the LLM sees at each stage** (progressive exclusion in action):

- *SELECT* — the framework `UseLLM.achoose` chooser lists every candidate by
  its **briefing** (`name: description`; bodies never enter this prompt) and
  asks for a JSON array of catalog names. The reply is parsed as a set:
  unknown names are ignored, duplicates collapse, unparseable replies are
  retried automatically (up to 3 attempts). A deterministic keyword search
  (`SkillRegistry.search(..., names=<the role's pool>)`) pre-filters the pool
  first when it exceeds `prefilter_threshold`, and the result is trimmed to
  `max_selected_skills` (or the per-call `k`).
- *DISTILL* — only the selected skills' **bodies** enter this prompt, with the
  instruction to extract just the parts relevant to the question and discard
  everything else.

### 4. Explicit loading — custom directories & the registry

Skip the auto-load by loading skills yourself. The loaders chain, and re-running
one is safe: a name already in the library keeps its first copy, and the loader
reports it again rather than re-reading the file, so the role tracks it either
way:

```python
from fabricatio import Action, Task
from fabricatio_skill import UseSkill


class AnswerWithTeamSkills(Action, UseSkill):
    """Answer using skills from a non-default directory."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> str:
        # scan the custom root, then resolve two names against it
        self.scan_skills("team-skills").gather_skills(["security", "review"], dirs=["team-skills"])
        knowledge = await self.consult_skills(task_input.briefing)
        ...
```

`add_skills(skills)` registers `Skill` objects you parsed yourself.

### 5. Gather directly by name

When you already know which skills you want, skip scanning entirely:
`gather_skills` resolves each name through the lookup roots — trying
`<dir>/<name>/SKILL.md` first, then `<dir>/<name>.md` (direct path reads, no
directory walk) — registers the hits, and tracks them on the role.
Unresolvable names are logged and skipped. The last default root is
`~/.agents/skills`, so the user-level agent-skills library is available with
zero configuration:

```python
from fabricatio import Action, Task
from fabricatio_skill import UseSkill


class AnswerWithNamedSkills(Action, UseSkill):
    """Answer using two explicitly gathered skills."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> str:
        self.gather_skills(["rust-async", "code_review"])   # by name, no scan
        knowledge = await self.consult_skills(task_input.briefing)
        return await self.aask(f"{knowledge}\n\n---\n\n{task_input.briefing}")
```

Pass `dirs=[...]` to resolve against custom libraries instead of the configured
roots (`~` is expanded). Without a role, the same resolution goes straight
through the library: `load_by_name` returns the names it made available.

On a role or action, the library is the `skill_library` property, so
`role.skill_library.search("async", names=role.skill_names)` searches exactly
the pool the role consults.

The library is also exposed for framework-free pipelines — get the singleton
via `SkillRegistry.instance()` (the constructor raises `TypeError`):

```python
from fabricatio_skill import SkillRegistry

library = SkillRegistry.instance()                       # process-wide: one copy per name
scanned = library.load_scanned(["skills"])               # parse every .md file under a root
wanted = library.load_by_name(["rust-async"], ["skills"])  # resolve by name (no walk)
library.search("async", names=wanted, in_content=True)   # keyword search over that pool
library.get("rust-async")                                # one loaded skill, or None
library.remove(["rust-async"])                           # free the name; next load re-reads it
```

Both loaders return the names they made available — a name already in the
library is reported too, never read a second time — which is how the role-level
`scan_skills`/`gather_skills` track what they loaded. `load_scanned` is strict
(a missing root raises `FileNotFoundError`), while `load_by_name` is lenient
(unresolved names are skipped); `add`, `remove`, and `clear` return the library
for chaining.

## Configuration

All options below are read through the fabricatio configuration chain (see the
Configuration Guide at ../../docs/source/configuration.rst). Set them under the
`[ext.skill]` table in `fabricatio.toml`, equivalently under
`[tool.fabricatio.ext.skill]` in `pyproject.toml`, or via
`FABRICATIO_EXT__SKILL__<FIELD_UPPER>` environment variables.

```
# fabricatio.toml
[ext.skill]
distill_skills_template = "built-in/distill_skills"
max_selected_skills = 8
prefilter_threshold = 100
default_skill_dirs = ["skills", "extra/skills", "~/.agents/skills"]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `distill_skills_template` | `str` | `"built-in/distill_skills"` | Template name for the LLM prompt that distills skill content to its essence. |
| `max_selected_skills` | `int` | `8` | Maximum number of skills the LLM may select per call (`0` = unlimited). Caps how many bodies reach distillation. |
| `prefilter_threshold` | `int` | `100` | Pool size above which selection keyword-prefilters with the library's `SkillRegistry.search` before the LLM stage (`0` disables the prefilter). |
| `default_skill_dirs` | `List[str]` | `["skills", "extra/skills", "~/.agents/skills"]` | Default directories auto-scanned on first consult, and the lookup roots for by-name gathering (`~` is expanded at use time). |

Access at runtime: `from fabricatio_skill.config import skill_config`.

## Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities
...

## License

This project is licensed under the MIT License.
