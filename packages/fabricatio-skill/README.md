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

## Key Features

- **Markdown-native skills** — author skills as `.md` files with YAML frontmatter; no schema lock-in beyond three metadata keys.
- **Three-level pipeline** — Level 1 (Rust): free file scanning (`scan_skills`) and keyword search (`search_skills`); Level 2 (Python): LLM-powered relevance selection (`select_skills`) and essence distillation (`distill_skills`); Level 3: the composed `consult_skills` pipeline (select → distill → consulted knowledge). Consultation only — answering stays in your Action.
- **Progressive disclosure dial** — every call trades fidelity for tokens via `select=` / `distill=` / forced `names=`.
- **Lightweight composition** — heavy `Skill` objects live in a process-wide `SkillRegistry`; your roles/actions carry only a list of name handles.
- **Rust-backed performance** — parsing, lookup, and keyword matching are PyO3 (`fabricatio_skill.rust`).

## Usage

### 1. Author skill files

Drop markdown files into a skill directory (default roots: `skills/`, `extra/skills/`):

```markdown
---
name: rust-async
description: How to write async Rust with tokio correctly
tags: [rust, async]
---
Markdown body with the actual instructions...
```

### 2. Load them

```python
from fabricatio_skill import scan_skills

skills = scan_skills("skills")   # parse all .md files → Skill objects
```

### 3. Compose the capability onto an Action (aligned style)

`fabricatio-skill` is a **skill consultant**: it selects relevant skills and
distills what they say about a question, then stops — answering is your
Action's job. Mix `UseSkill` into an `Action`, register the skill names at
composition time, consult the library inside `_execute`, then feed the
returned knowledge into your own LLM call, all behind a
`Role` / `Event` / `WorkFlow`:

```python
from fabricatio_core import Action, Event, Role, WorkFlow
from fabricatio_skill import UseSkill, scan_skills


class AnswerWithSkills(Action, UseSkill):
    """Answer the task briefing grounded in consulted skill knowledge."""

    output_key: str = "task_output"

    async def _execute(self, task_input: str, **_) -> str:
        knowledge = await self.consult_skills(task_input)   # select → distill (pkg ends here)
        prompt = f"{knowledge}\n\n---\n\n{task_input}" if knowledge else task_input
        return await self.aask(prompt)                      # the actual job — yours


skills = scan_skills("skills")
AnswerWithSkills.skill_names = [s.name for s in skills]

role = (
    Role.with_bio(name="skilled", description="answers using the skill library")
    .subscribe(
        Event.quick_instantiate("ask"),
        WorkFlow(name="skill_qa", steps=(AnswerWithSkills,)),
    )
    .dispatch()
)
# then dispatch a Task whose briefing is the question to Event "ask"
```

### 4. Tune the disclosure level per call

`consult_skills()` is the progressive-disclosure dial; it returns what the
relevant skills say (or `""` when nothing is relevant):

| Call | Returns |
|---|---|
| `await self.consult_skills(q)` | Distilled essence of LLM-selected skills (2 extra LLM calls). |
| `await self.consult_skills(q, names=["rust-async"])` | Forced skills — skips LLM selection. |
| `await self.consult_skills(q, distill=False)` | Full bodies of selected skills — no compression call. |
| `await self.consult_skills(q, select=False, distill=False)` | All registered skills verbatim. |

For finer control, step through the levels manually:

```python
picked = await agent.select_skills(question)             # LLM relevance over metadata
essence = await agent.distill_skills(question, picked)   # LLM compression of bodies
answer = await agent.aask(f"{essence}\n\n---\n\n{question}")
```

## Configuration

All options below are read through the fabricatio configuration chain (see the
Configuration Guide at ../../docs/source/configuration.rst). Set them under the
`[ext.skill]` table in `fabricatio.toml`, equivalently under
`[tool.fabricatio.ext.skill]` in `pyproject.toml`, or via
`FABRICATIO_EXT__SKILL__<FIELD_UPPER>` environment variables.

```
# fabricatio.toml
[ext.skill]
select_skills_template = "built-in/select_skills"
distill_skills_template = "built-in/distill_skills"
default_skill_dirs = ["skills", "extra/skills"]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `select_skills_template` | `str` | `"built-in/select_skills"` | Template name for the LLM prompt that selects relevant skills from a question. |
| `distill_skills_template` | `str` | `"built-in/distill_skills"` | Template name for the LLM prompt that distills skill content to its essence. |
| `default_skill_dirs` | `List[str]` | `["skills", "extra/skills"]` | Default directories to scan for skill files. |

Access at runtime: `from fabricatio_skill.config import skill_config`.

## Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities
...

## License

This project is licensed under the MIT License.
